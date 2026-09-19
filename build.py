#!/usr/bin/env python3
"""Build LeonBlog's static site. See WebCode/BUILD.md for usage."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from functools import partial
from html import escape
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from urllib.parse import quote, unquote, urlsplit


ROOT = Path(__file__).resolve().parent
MATHJAX_URL = "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js"
MANIFEST = ".build-manifest.json"
TOKEN = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
# Presentation assets from the existing homepage, not a content discovery list.
ICONS = {"Math": "pi", "Crypto": "lock-keyhole", "Research": "file-text",
         "Project": "cuboid", "Tool": "wrench", "Diary": "pencil-line"}


class BuildError(Exception):
    """An actionable error in content, metadata, templates, or conversion."""


@dataclass
class Chapter:
    source: Path
    title: str
    order: int
    output: str


@dataclass
class Subject:
    directory: Path
    title: str
    order: int
    chapters: list[Chapter]


@dataclass
class Category:
    directory: Path
    title: str
    order: int
    description: str
    subtitle: str = ""
    subjects: list[Subject] = field(default_factory=list)

    @property
    def output(self) -> str:
        return f"{self.directory.name}/index.html"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise BuildError(f"{path}: cannot read UTF-8 text: {exc}") from exc


def read_metadata(path: Path) -> dict:
    try:
        value = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise BuildError(f"{path}:{exc.lineno}: invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise BuildError(f"{path}: expected a JSON object")
    return value


def require(value: dict, key: str, kind: type, path: Path, prefix: str = ""):
    result = value.get(key)
    if type(result) is not kind or (kind is str and not result.strip()):
        raise BuildError(f"{path}: {prefix}{key} must be a non-empty {kind.__name__}")
    return result


def within(base: Path, path: Path) -> Path:
    """Check resolved paths before copying, replacing, or removing files."""
    resolved = path.resolve()
    if not resolved.is_relative_to(base.resolve()) or resolved == base.resolve():
        raise BuildError(f"{path}: path must stay inside {base}")
    return resolved


def path_component(name: str, context: Path) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        raise BuildError(f"{context}: expected an English filename/directory, got {name!r}")


def discover(root: Path, warnings: list[str]) -> list[Category]:
    categories = []
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        if directory.name in {"WebCode", "Output", "__pycache__"}:
            continue
        within(root, directory)
        path_component(directory.name, directory)
        category_meta = directory / "meta.json"
        if not category_meta.is_file():
            warnings.append(f"{category_meta}: missing; category has no generated content")
            continue
        within(directory, category_meta)
        meta = read_metadata(category_meta)
        title = require(meta, "title", str, category_meta)
        order = require(meta, "order", int, category_meta)
        description = meta.get("description", "")
        if not isinstance(description, str):
            raise BuildError(f"{category_meta}: description must be a string")
        subtitle = meta.get("subtitle", "")
        if not isinstance(subtitle, str):
            raise BuildError(f"{category_meta}: subtitle must be a string")
        subject_entries = require(meta, "subjects", list, category_meta)
        category = Category(directory, title, order, description, subtitle)
        if list(directory.glob("*.tex")):
            raise BuildError(f"{directory}: place article sources in subject directories")
        nested_metadata = sorted(directory.glob("*/meta.json"))
        if nested_metadata:
            raise BuildError(f"{nested_metadata[0]}: nested metadata is not supported; merge it into {category_meta}")
        subject_directories, subject_orders = set(), set()
        for subject_index, subject_entry in enumerate(subject_entries):
            subject_prefix = f"subjects[{subject_index}]."
            if not isinstance(subject_entry, dict):
                raise BuildError(f"{category_meta}: subjects[{subject_index}] must be an object")
            subject_name = require(subject_entry, "directory", str, category_meta, subject_prefix)
            path_component(subject_name, category_meta)
            if subject_name.casefold() in subject_directories:
                raise BuildError(f"{category_meta}: {subject_prefix}duplicate directory")
            subject_directories.add(subject_name.casefold())
            subject_dir = within(directory, directory / subject_name)
            if not subject_dir.is_dir():
                raise BuildError(f"{category_meta}: {subject_prefix}directory does not exist: {subject_name}")
            subject_title = require(subject_entry, "title", str, category_meta, subject_prefix)
            subject_order = require(subject_entry, "order", int, category_meta, subject_prefix)
            if subject_order in subject_orders:
                raise BuildError(f"{category_meta}: {subject_prefix}duplicate order")
            subject_orders.add(subject_order)
            entries = require(subject_entry, "chapters", list, category_meta, subject_prefix)
            chapters, files, orders = [], set(), set()
            for index, entry in enumerate(entries):
                prefix = f"{subject_prefix}chapters[{index}]."
                if not isinstance(entry, dict):
                    raise BuildError(f"{category_meta}: {prefix[:-1]} must be an object")
                filename = require(entry, "file", str, category_meta, prefix)
                path_component(filename, category_meta)
                if Path(filename).suffix != ".tex":
                    raise BuildError(f"{category_meta}: {prefix}file must be a .tex filename")
                chapter_title = require(entry, "title", str, category_meta, prefix)
                chapter_order = require(entry, "order", int, category_meta, prefix)
                if filename.casefold() in files or chapter_order in orders:
                    raise BuildError(f"{category_meta}: {prefix}duplicate file or order")
                files.add(filename.casefold())
                orders.add(chapter_order)
                source = within(subject_dir, subject_dir / filename)
                if not source.is_file():
                    raise BuildError(f"{category_meta}: {prefix}file does not exist: {filename}")
                output = f"{directory.name}/{subject_dir.name}/{Path(filename).stem}.html"
                if Path(filename).stem.casefold() == "index":
                    raise BuildError(f"{category_meta}: {prefix}index.tex conflicts with the subject index")
                chapters.append(Chapter(source, chapter_title, chapter_order, output))
            for source in sorted(subject_dir.rglob("*.tex")):
                if source.parent != subject_dir or source.name.casefold() not in files:
                    warnings.append(f"{source}: not listed in {category_meta}; not included")
            if not chapters:
                warnings.append(f"{category_meta}: {subject_prefix}chapters is empty; subject not included")
                continue
            category.subjects.append(Subject(subject_dir, subject_title, subject_order,
                                              sorted(chapters, key=lambda c: c.order)))
        for subject_dir in sorted(path for path in directory.iterdir()
                                  if path.is_dir() and path.name != "icon"):
            if subject_dir.name.casefold() not in subject_directories and any(subject_dir.rglob("*.tex")):
                warnings.append(f"{subject_dir}: not listed in {category_meta}; not included")
        # Diary is a timeline: newer month metadata orders appear first.
        # Academic and other categories retain the normal ascending order.
        category.subjects.sort(
            key=lambda s: (s.order, s.directory.name),
            reverse=directory.name == "Diary",
        )
        categories.append(category)
    return sorted(categories, key=lambda c: (c.order, c.directory.name))


def find_pandoc(root: Path, explicit: str | None = None) -> str:
    if explicit:
        candidate = shutil.which(explicit) or explicit
        if Path(candidate).is_file():
            return str(Path(candidate).resolve())
        raise BuildError(f"Pandoc executable not found: {explicit}")
    if found := shutil.which("pandoc"):
        return found
    candidates = [root / ".venv/Lib/site-packages/pypandoc/files/pandoc.exe"]
    candidates.extend(sorted((root / ".venv/lib").glob("python*/site-packages/pypandoc/files/pandoc")))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    try:
        import pypandoc
        return pypandoc.get_pandoc_path()
    except (ImportError, OSError):
        raise BuildError("Pandoc is required. Install it or run: python -m venv .venv; "
                         ".venv/Scripts/python -m pip install -r requirements-build.txt") from None


def run_pandoc(pandoc: str, arguments: list[str], source: str, context: Path) -> str:
    try:
        result = subprocess.run([pandoc, *arguments, "--sandbox", "--fail-if-warnings"],
                                input=source, capture_output=True, encoding="utf-8",
                                cwd=context.parent, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BuildError(f"{context}: Pandoc could not run: {exc}") from exc
    if result.returncode:
        raise BuildError(f"{context}: Pandoc failed:\n{result.stderr.strip()}")
    return result.stdout


def nodes(value):
    if isinstance(value, dict):
        if "t" in value:
            yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


def inline_text(inlines: list) -> str:
    parts = []
    for node in inlines:
        kind, content = node.get("t"), node.get("c")
        if kind == "Str":
            parts.append(content)
        elif kind in {"Space", "SoftBreak", "LineBreak"}:
            parts.append(" ")
        elif kind in {"Code", "Math"}:
            parts.append(content[1])
        elif kind in {"Link", "Image", "Span"}:
            parts.append(inline_text(content[1]))
        elif kind in {"Emph", "Strong", "Strikeout", "Superscript", "Subscript", "SmallCaps"}:
            parts.append(inline_text(content))
        elif kind == "Quoted":
            parts.append(inline_text(content[1]))
    return "".join(parts)


def relative_url(page: str, destination: str) -> str:
    return quote(posixpath.relpath(destination, posixpath.dirname(page) or "."), safe="/-._~")


def copy_resource(subject: Subject, chapter: Chapter, url: str, stage: Path) -> str:
    parsed = urlsplit(url)
    if parsed.scheme in {"http", "https", "mailto"}:
        return url
    if parsed.scheme or parsed.netloc or parsed.path.startswith(("/", "\\")):
        raise BuildError(f"{chapter.source}: unsupported resource URL: {url}")
    source = within(subject.directory, subject.directory / unquote(parsed.path))
    if not source.suffix and not source.is_file():
        candidates = [source.with_suffix(ext) for ext in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif")]
        source = next((p for p in candidates if p.is_file()), source)
        source = within(subject.directory, source)
    if not source.is_file():
        raise BuildError(f"{chapter.source}: missing referenced resource: {url}")
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".pdf", ".avif"}:
        raise BuildError(f"{chapter.source}: unsupported attachment type: {source.name}")
    target = PurePosixPath(chapter.output).parent / source.relative_to(subject.directory).as_posix()
    destination = within(stage, stage / str(target))
    destination.parent.mkdir(parents=True, exist_ok=True)
    copy_static_file(source, destination)
    suffix = (f"?{parsed.query}" if parsed.query else "") + (f"#{parsed.fragment}" if parsed.fragment else "")
    return relative_url(chapter.output, str(target)) + suffix


def convert(pandoc: str, chapter: Chapter, subject: Subject, stage: Path,
            warnings: list[str]) -> tuple[str, str, bool]:
    document = json.loads(run_pandoc(pandoc, ["-f", "latex+raw_tex", "-t", "json"],
                                     read_text(chapter.source), chapter.source))
    if not document["blocks"]:
        warnings.append(f"{chapter.source}: no article body; generated an explicit placeholder")
        return '<p class="article-lead">本章内容尚在整理中。</p>', "", False
    headings, ids = [], {}
    has_math = False
    all_nodes = list(nodes(document["blocks"]))
    for node in all_nodes:
        kind, content = node["t"], node.get("c")
        if kind in {"RawBlock", "RawInline"}:
            raise BuildError(f"{chapter.source}: unsupported raw {content[0]}: {content[1][:100]}")
        if kind == "Header":
            # The page owns h1; source sections start at h2. IDs cannot collide with layout IDs.
            identifier = f"section-{len(headings) + 1}"
            ids[content[1][0]] = identifier
            content[1][0] = identifier
            content[0] = min(content[0] + 1, 6)
            headings.append((content[0], identifier, inline_text(content[2])))
        elif kind == "Math":
            has_math = True
        elif kind == "Image":
            if urlsplit(content[2][0]).path.lower().endswith(".pdf"):
                raise BuildError(f"{chapter.source}: browser images must use PNG, SVG, JPEG, etc., not PDF")
            content[2][0] = copy_resource(subject, chapter, content[2][0], stage)
    for node in all_nodes:
        if node["t"] != "Link":
            continue
        target = node["c"][2]
        if target[0].startswith("#"):
            target[0] = "#" + ids.get(target[0][1:], target[0][1:])
        elif not urlsplit(target[0]).scheme:
            target[0] = copy_resource(subject, chapter, target[0], stage)
        elif urlsplit(target[0]).scheme not in {"https", "http", "mailto"}:
            raise BuildError(f"{chapter.source}: unsupported link: {target[0]}")
    body = run_pandoc(pandoc, ["-f", "json", "-t", "html5", "--mathjax", "--wrap=none"],
                      json.dumps(document, ensure_ascii=False), chapter.source)
    toc = "\n".join(f'<a href="#{identifier}"' + (' class="toc-subitem"' if level > 2 else '')
                    + f'>{escape(title)}</a>' for level, identifier, title in headings)
    return body, toc, has_math


def render(template: str, values: dict[str, str]) -> str:
    def replace(match):
        key = match[1]
        if key not in values:
            raise BuildError(f"Template contains an unknown placeholder: {key}")
        return values[key]
    return TOKEN.sub(replace, template)


def main_navigation(categories: list[Category], page: str, active: Category | None) -> str:
    links = [f'<a href="{relative_url(page, "index.html")}"'
             + (' class="active" aria-current="page"' if active is None else '') + '>Home</a>']
    for category in categories:
        state = ' class="active"' if category is active else ''
        links.append(f'<a href="{relative_url(page, category.output)}"{state}>{escape(category.title)}</a>')
    return "\n".join(links)


def sidebar(category: Category, page: str, current: Chapter | None = None) -> str:
    parts = []
    for subject in category.subjects:
        if len(subject.chapters) == 1:
            chapter = subject.chapters[0]
            state = ' aria-current="page"' if chapter is current else ''
            parts.append(f'<a class="subject-link" href="{relative_url(page, chapter.output)}"{state}>'
                         f'{escape(subject.title)}</a>')
            continue
        selected = any(chapter is current for chapter in subject.chapters)
        state = ' current-subject' if selected else ''
        parts.append(f'<details class="subject-group{state}" name="subjects"'
                     + (' open' if selected else '') + '>')
        parts.append(f'<summary class="subject-heading"><span>{escape(subject.title)}</span></summary>')
        parts.append('<ol class="chapter-list">')
        for chapter in subject.chapters:
            number = re.match(r"(\d+)[-_]", chapter.source.stem)
            number_html = (f'<span class="chapter-number" aria-hidden="true">{number[1]}</span>'
                           if number else '')
            state = ' aria-current="page"' if chapter is current else ''
            parts.append(f'<li><a class="chapter-link" href="{relative_url(page, chapter.output)}"{state}>'
                         f'{number_html}<span>{escape(chapter.title)}</span></a></li>')
        parts.append('</ol></details>')
    return "\n".join(parts)


def pagination(subject: Subject, chapter: Chapter) -> str:
    index = subject.chapters.index(chapter)
    parts = []
    for offset, css, label in [(-1, "previous-article", "上一篇"), (1, "next-article", "下一篇")]:
        if 0 <= index + offset < len(subject.chapters):
            neighbour = subject.chapters[index + offset]
            parts.append(f'<a class="pagination-card {css}" href="{relative_url(chapter.output, neighbour.output)}">'
                         f'<span class="pagination-label">{label}</span><strong>{escape(neighbour.title)}</strong></a>')
    return '<nav class="article-pagination" aria-label="相邻章节">' + "".join(parts) + '</nav>' if parts else ''


def write_page(stage: Path, path: str, text: str) -> None:
    destination = within(stage, stage / path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8", newline="\r\n")


def copy_static_file(source: Path, destination: Path) -> None:
    """Copy static assets while keeping generated text files in CRLF format."""
    if source.suffix.lower() in {".css", ".html", ".js", ".json", ".md", ".svg", ".txt", ".xml"}:
        destination.write_text(read_text(source), encoding="utf-8", newline="\r\n")
    else:
        shutil.copyfile(source, destination)


def page_values(categories: list[Category], category: Category, page: str, title: str) -> dict[str, str]:
    return {"page_title": escape(f"{title} | LeonBlog"), "title": escape(title),
            "home_url": relative_url(page, "index.html"),
            "stylesheet_url": relative_url(page, "css/article.css"),
            "base_stylesheet_url": relative_url(page, "css/base.css"),
            "favicon_url": relative_url(page, "assets/icons/favicon.svg"),
            "main_navigation": main_navigation(categories, page, category),
            "breadcrumbs": f'<a href="{relative_url(page, category.output)}">{escape(category.title)}</a>',
            "sidebar": sidebar(category, page), "body": "", "pagination": "", "toc": "", "math_script": "",
            "toc_visibility": " hidden", "article_layout_class": " no-toc"}


def subject_card(category: Category, subject: Subject) -> str:
    """Render a subject with the same card component used by the homepage."""
    subject_icon = category.directory / "icon" / f"{subject.order}.svg"
    icon_path = (f"{category.directory.name}/icon/{subject.order}.svg"
                 if subject_icon.is_file()
                 else f"assets/icons/{ICONS[category.directory.name]}.svg")
    icon_html = (f'<div class="category-icon {category.directory.name.lower()}-icon">'
                 f'<img src="{relative_url(category.output, icon_path)}" alt=""></div>')
    return (f'<a class="category-card" href="{relative_url(category.output, subject.chapters[0].output)}">'
            f'{icon_html}<h2>{escape(subject.title)}</h2>'
            f'<p>{len(subject.chapters)} 篇文章</p>'
            '<span class="category-arrow" aria-hidden="true">→</span></a>')


def generate(root: Path, stage: Path, categories: list[Category], pandoc: str,
             warnings: list[str], mathjax_url: str) -> int:
    article_template = read_text(root / "WebCode/templates/article.html")
    home_template = read_text(root / "WebCode/templates/index.html")
    category_template = read_text(root / "WebCode/templates/category.html")
    for name in ("css", "assets"):
        source = root / "WebCode" / name
        if not source.is_dir():
            raise BuildError(f"{source}: required static resource directory is missing")
        for path in sorted(source.rglob("*")):
            if path.is_file():
                within(source, path)
                destination = stage / name / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                copy_static_file(path, destination)
    count, cards = 0, []
    for category in categories:
        icon_source = category.directory / "icon"
        if icon_source.is_dir():
            for path in sorted(icon_source.iterdir()):
                if not path.is_file() or path.suffix.lower() not in {".svg", ".txt"}:
                    continue
                within(icon_source, path)
                destination = stage / category.directory.name / "icon" / path.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                copy_static_file(path, destination)
        for subject in category.subjects:
            subject_index = f"{category.directory.name}/{subject.directory.name}/index.html"
            subject_values = page_values(categories, category, subject_index, subject.title)
            subject_values["body"] = '<ol class="subject-index-list">' + ''.join(
                f'<li><a href="{relative_url(subject_index, c.output)}">{escape(c.title)}</a></li>'
                for c in subject.chapters) + '</ol>'
            write_page(stage, subject_index, render(article_template, subject_values))
            for chapter in subject.chapters:
                body, toc, math = convert(pandoc, chapter, subject, stage, warnings)
                values = page_values(categories, category, chapter.output, chapter.title)
                values.update(body=body, toc=toc,
                              sidebar=sidebar(category, chapter.output, chapter), pagination=pagination(subject, chapter))
                if toc:
                    values.update(toc_visibility="", article_layout_class="")
                values["breadcrumbs"] += ('<span class="meta-divider" aria-hidden="true">/</span>'
                                          f'<a href="{relative_url(chapter.output, subject_index)}">{escape(subject.title)}</a>')
                values["page_title"] = escape(f"{chapter.title} · {subject.title} | LeonBlog")
                if math:
                    script_url = mathjax_url if urlsplit(mathjax_url).scheme else relative_url(chapter.output, mathjax_url)
                    values["math_script"] = f'<script defer src="{escape(script_url, quote=True)}"></script>'
                write_page(stage, chapter.output, render(article_template, values))
                count += 1
        values = page_values(categories, category, category.output, category.title)
        hero_image = f"assets/images/hero-{category.directory.name.lower()}.jpg"
        if not (root / "WebCode" / hero_image).is_file():
            hero_image = "assets/images/background.jpg"
        subject_count = len(category.subjects)
        chapter_count = sum(len(subject.chapters) for subject in category.subjects)
        collection_title = "日记归档" if category.directory.name == "Diary" else "科目与笔记"
        collection_summary = (f"{subject_count} 个月份 · {chapter_count} 篇记录"
                              if category.directory.name == "Diary"
                              else f"{subject_count} 个科目 · {chapter_count} 篇文章")
        empty_card = ('<div class="category-empty"><span aria-hidden="true">✧</span>'
                      '<h3>留一处空白，等待新的思考。</h3><p>这里的内容正在慢慢整理，敬请期待。</p>'
                      f'<a href="{relative_url(category.output, "index.html")}">探索其他分类 <span aria-hidden="true">→</span></a></div>')
        values.update(
            stylesheet_url=relative_url(category.output, "css/style.css"),
            category_stylesheet_url=relative_url(category.output, "css/category.css"),
            hero_image_url=relative_url(category.output, hero_image),
            category_description=escape(category.subtitle or category.description or "按主题整理，循章节阅读。", quote=True),
            collection_title=collection_title,
            collection_summary=collection_summary if subject_count else "持续记录，慢慢积累",
            subject_cards=''.join(subject_card(category, subject) for subject in category.subjects)
                          or empty_card,
        )
        write_page(stage, category.output, render(category_template, values))
        icon = ICONS.get(category.directory.name)
        icon_html = (f'<div class="category-icon {category.directory.name.lower()}-icon">'
                     f'<img src="assets/icons/{icon}.svg" alt=""></div>') if icon else ''
        cards.append(f'<a class="category-card" href="{quote(category.output)}">{icon_html}'
                     f'<h2>{escape(category.title)}</h2>'
                     + (f'<p>{escape(category.description)}</p>' if category.description else '')
                     + '<span class="category-arrow" aria-hidden="true">→</span></a>')
    write_page(stage, "index.html", render(home_template,
               {"main_navigation": main_navigation(categories, "index.html", None),
                "category_cards": "\n".join(cards)}))
    return count


class PageLinks(HTMLParser):
    """Collect links and IDs without requiring a browser or third-party HTML parser."""

    def __init__(self):
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if identifier := attributes.get("id"):
            if identifier in self.ids:
                raise BuildError(f"Duplicate HTML id: {identifier}")
            self.ids.add(identifier)
        for name in ("href", "src"):
            if name in attributes:
                self.links.append(attributes[name])


def validate_output(stage: Path) -> None:
    pages = {}
    for path in sorted(stage.rglob("*.html")):
        parser = PageLinks()
        try:
            parser.feed(read_text(path))
        except BuildError as exc:
            raise BuildError(f"{path.relative_to(stage)}: {exc}") from exc
        pages[path.resolve()] = parser
    for path, parser in pages.items():
        for link in parser.links:
            url = urlsplit(link)
            if url.scheme in {"https", "http", "mailto"}:
                continue
            if url.scheme or url.netloc:
                raise BuildError(f"{path.relative_to(stage)}: unsupported URL {link}")
            target = within(stage, path.parent / unquote(url.path)) if url.path else path
            if not target.is_file():
                raise BuildError(f"{path.relative_to(stage)}: broken local link {link}")
            if url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                raise BuildError(f"{path.relative_to(stage)}: missing anchor {link}")
    for path in stage.rglob("*.css"):
        for match in re.finditer(r'url\(\s*[\'"]?([^\s\)\'"]+)', read_text(path)):
            url = urlsplit(match[1])
            if not url.scheme and url.path:
                target = within(stage, path.parent / unquote(url.path))
                if not target.is_file():
                    raise BuildError(f"{path.relative_to(stage)}: missing CSS asset {match[1]}")


def publish_file(source: Path, destination: Path) -> None:
    """Copy bytes into a sibling file, then atomically replace the destination.

    Windows temporary directories may have owner-only ACLs. Moving a staged
    file directly preserves those ACLs, making output unreadable to other
    project users. A regular new file here inherits the output directory ACL.
    Do not use tempfile or copy2 for this destination-side file.
    """
    temporary = destination.with_name(f".build-{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as target, source.open("rb") as original:
            shutil.copyfileobj(original, target)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def publish(stage: Path, output: Path) -> None:
    """Replace only build-owned files; leave unrelated files untouched."""
    if output.is_symlink():
        raise BuildError(f"{output}: output directory must not be a symlink")
    output.mkdir(exist_ok=True)
    manifest = output / MANIFEST
    within(output, manifest)
    previous = set()
    if manifest.exists():
        data = read_metadata(manifest)
        if data.get("generator") != "LeonBlog" or not isinstance(data.get("files"), list):
            raise BuildError(f"{manifest}: invalid build manifest")
        for entry in data["files"]:
            if not isinstance(entry, str) or "\\" in entry or ".." in PurePosixPath(entry).parts:
                raise BuildError(f"{manifest}: invalid file path {entry!r}")
            within(output, output / entry)
            previous.add(entry)
    files = sorted(p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file())
    # Complete all path/collision checks before making changes to existing output.
    for name in set(files) | previous:
        target = output / name
        within(output, target)
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise BuildError(f"{target}: expected a regular generated file")
        if name in files and target.exists() and name not in previous:
            raise BuildError(f"{target}: exists but is not owned by this build; refusing to overwrite")
    for name in files:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        publish_file(stage / name, destination)
    for name in sorted(previous - set(files)):
        (output / name).unlink(missing_ok=True)
    write_page(stage, MANIFEST, json.dumps({"generator": "LeonBlog", "files": files}, indent=2) + "\n")
    publish_file(stage / MANIFEST, manifest)


def build(root: Path = ROOT, *, strict: bool = False, check: bool = False,
          pandoc: str | None = None, mathjax_url: str = MATHJAX_URL) -> tuple[int, list[str]]:
    warnings: list[str] = []
    categories = discover(root, warnings)
    executable = find_pandoc(root, pandoc)
    with tempfile.TemporaryDirectory(prefix=".build-", dir=root) as directory:
        stage = Path(directory)
        count = generate(root, stage, categories, executable, warnings, mathjax_url)
        validate_output(stage)
        if strict and warnings:
            raise BuildError("Strict build stopped:\n" + "\n".join(warnings))
        if not check:
            within(root, root / "Output")
            publish(stage, root / "Output")
    return count, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="convert and validate without updating Output")
    parser.add_argument("--strict", action="store_true", help="treat unfinished/unconfigured content as errors")
    parser.add_argument("--pandoc", help="path to a Pandoc executable")
    parser.add_argument("--mathjax-url", default=MATHJAX_URL,
                        help="MathJax URL or Output-relative asset path (default: pinned CDN)")
    parser.add_argument("--serve", action="store_true", help="build, then preview on localhost")
    parser.add_argument("--port", type=int, default=8000, help="local preview port (default: 8000)")
    args = parser.parse_args()
    if args.check and args.serve:
        parser.error("--check and --serve cannot be combined")
    try:
        count, warnings = build(strict=args.strict, check=args.check, pandoc=args.pandoc, mathjax_url=args.mathjax_url)
        for warning in warnings:
            print(f"WARNING: {warning}", file=sys.stderr)
        print(f"{'Validated' if args.check else 'Built'} {count} articles; {len(warnings)} warnings.")
        if not args.check:
            print(f"Output: {ROOT / 'Output/index.html'}")
        if args.serve:
            handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT / "Output"))
            with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
                print(f"Preview: http://127.0.0.1:{args.port}/ (Ctrl+C to stop)", flush=True)
                server.serve_forever()
    except (BuildError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nPreview stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
