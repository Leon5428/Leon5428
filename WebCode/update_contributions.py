"""Refresh README contribution and repository cards with public GitHub data."""

from datetime import date, timedelta
from html import escape
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit, urlencode
from urllib.request import Request, urlopen


USERNAME = "Leon5428"
SOURCE = f"https://github.com/users/{USERNAME}/contributions"
OUTPUT = Path(__file__).resolve().parent / "assets/images/contributions.svg"
COLORS = ("#161b22", "#003d29", "#006d32", "#26a641", "#39d353")
REPOSITORIES = {
    "Leon5428/Leon5428": "repository.svg",
    "Leon5428/PQSecure": "repository-pqsecure.svg",
    "Leon5428/AgentArmor": "repository-agentarmor.svg",
}
README = Path(__file__).resolve().parent.parent / "README.md"


def description_lines(description: str) -> tuple[str, str]:
    """Fit two lines, allowing twice the width for Chinese characters."""
    lines, current, width = [], "", 0
    for char in " ".join(description.split()):
        size = 2 if unicodedata.east_asian_width(char) in "WF" else 1
        if width + size > 84:
            lines.append(current)
            current, width = "", 0
        current += char
        width += size
    lines.append(current)
    if len(lines) > 2:
        lines[1] = lines[1][:-1] + "…"
    return escape(lines[0]), escape(lines[1]) if len(lines) > 1 else ""


def commit_count(entries: list, link: str) -> int:
    """With one commit per page, the last page number is the total count."""
    last = re.search(r'<([^>]+)>;\s*rel="last"', link)
    if last:
        count = int(parse_qs(urlsplit(last[1]).query)["page"][0])
        if count < 1:
            raise ValueError("Invalid commit pagination")
        return count
    if link:
        raise ValueError("Missing last-page link; cannot determine commit count")
    if len(entries) > 1:
        raise ValueError("Expected one commit per page")
    return len(entries)


def render_repository(repo: dict, commits: int) -> str:
    stars, forks = repo["stargazers_count"], repo["forks_count"]
    if any(type(value) is not int or value < 0 for value in (stars, forks, commits)):
        raise ValueError("Invalid repository statistics")
    name = escape(repo["full_name"])
    branch = escape(repo["default_branch"])
    language = escape(repo.get("language") or "Not detected")
    description = repo.get("description") or "No repository description provided."
    first_line, second_line = description_lines(description)
    if repo["full_name"] == "Leon5428/Leon5428":
        first_line = "LeonBlog · 数学、密码学与个人知识笔记"
        second_line = "LaTeX notes · Python builds · A static home for learning"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="224" viewBox="0 0 800 224" role="img" aria-labelledby="title desc">
  <title id="title">{name} repository</title>
  <desc id="desc">{stars} stars, {forks} forks, {commits} commits on the default branch {branch}. Snapshot refreshed {date.today().isoformat()}.</desc>
  <rect x="1" y="1" width="798" height="222" rx="12" fill="#0d1117" stroke="#30363d"/>
  <g font-family="Segoe UI, Arial, sans-serif">
    <path d="M29 29h17v22H29z M33 29v22 M37 34h5" fill="none" stroke="#8b949e" stroke-width="1.5"/>
    <text x="58" y="48" font-size="23" font-weight="600" fill="#79c0ff">{name}</text>
    <rect x="694" y="27" width="75" height="25" rx="12" fill="none" stroke="#30363d"/>
    <text x="731" y="44" text-anchor="middle" font-size="12" fill="#8b949e">Public</text>
    <text x="29" y="84" font-size="16" fill="#c9d1d9">{first_line}</text>
    <text x="29" y="109" font-size="13" fill="#8b949e">{second_line}</text>
    <path d="M29 128h740" stroke="#21262d"/>
    <text x="29" y="162" font-size="17" fill="#e3b341">★ {stars} Stars</text>
    <text x="209" y="162" font-size="17" fill="#bc8cff">⑂ {forks} Forks</text>
    <text x="389" y="162" font-size="17" fill="#7ee787">◷ {commits} Commits</text>
    <circle cx="635" cy="156" r="5" fill="#79c0ff"/>
    <text x="649" y="162" font-size="15" fill="#c9d1d9">{language}</text>
    <text x="29" y="201" font-size="12" fill="#8b949e">Default branch: {branch} · Refreshed {date.today().isoformat()}</text>
  </g>
</svg>
'''


def fetch_repository(repository: str) -> str:
    headers = {"User-Agent": "LeonBlog-profile", "Accept": "application/vnd.github+json"}
    api = f"https://api.github.com/repos/{repository}"
    with urlopen(Request(api, headers=headers), timeout=30) as response:
        repo = json.load(response)
    query = urlencode({"per_page": 1, "sha": repo["default_branch"]})
    try:
        with urlopen(Request(f"{api}/commits?{query}", headers=headers), timeout=30) as response:
            commits = commit_count(json.load(response), response.headers.get("Link", ""))
    except HTTPError as exc:
        if exc.code != 409 or json.load(exc).get("message") != "Git Repository is empty.":
            raise
        commits = 0
    return render_repository(repo, commits)


class ContributionCalendar(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.days: dict[date, int] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        day = attributes.get("data-date")
        level = attributes.get("data-level")
        if day and level is not None:
            value = int(level)
            if value not in range(len(COLORS)):
                raise ValueError(f"Unexpected contribution level: {value}")
            self.days[date.fromisoformat(day)] = value


def render_calendar(html: str) -> str:
    calendar = ContributionCalendar()
    calendar.feed(html)
    days = calendar.days
    if not 300 <= len(days) <= 371:
        raise ValueError("GitHub did not return a complete yearly calendar; image unchanged.")
    first, last = min(days), max(days)
    if (last - first).days + 1 != len(days):
        raise ValueError("GitHub returned an incomplete date range; image unchanged.")
    # GitHub calendars start each column on Sunday.
    start = first - timedelta(days=(first.weekday() + 1) % 7)
    columns = (last - start).days // 7 + 1
    step, size, padding = 19, 14, 25
    width = 2 * padding + (columns - 1) * step + size
    height = 2 * padding + 6 * step + size
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{USERNAME} GitHub contribution calendar</title>',
        f'<desc id="desc">Public GitHub contribution levels, {first} to {last}. '
        'Darker squares indicate less activity; bright green indicates more activity.</desc>',
        f'<!-- Source: {SOURCE}. Refresh: python WebCode/update_contributions.py -->',
        f'<rect width="{width}" height="{height}" rx="8" fill="#0d1117"/>',
    ]
    for day, level in sorted(days.items()):
        offset = (day - start).days
        x, y = padding + (offset // 7) * step, padding + (offset % 7) * step
        lines.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" '
                     f'rx="2" fill="{COLORS[level]}"><title>{day}: level {level}/4</title></rect>')
    lines.append('</svg>')
    return '\n'.join(lines) + '\n'


def main() -> None:
    request = Request(SOURCE, headers={"User-Agent": "LeonBlog-profile-calendar"})
    with urlopen(request, timeout=30) as response:
        svg = render_calendar(response.read().decode("utf-8"))
    # Finish network requests before modifying any local files.
    images = {OUTPUT: svg}
    for repository, filename in REPOSITORIES.items():
        images[OUTPUT.with_name(filename)] = fetch_repository(repository)
    readme = README.read_text(encoding="utf-8")
    for path, image in images.items():
        path.write_text(image, encoding="utf-8", newline="\r\n")
        # A content-based version changes the URL only when the image changes.
        version = hashlib.sha256(image.encode("utf-8")).hexdigest()[:12]
        source = f"./WebCode/assets/images/{path.name}"
        readme = re.sub(r'(src="' + re.escape(source) + r')(?:\?[^"\s]*)?"',
                        lambda match: f'{match[1]}?v={version}"', readme)
        print(f"Updated {path}")
    README.write_text(readme, encoding="utf-8", newline="\r\n")


if __name__ == "__main__":
    main()
