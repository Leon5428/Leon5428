"""Refresh README contribution and repository cards with public GitHub data."""

from datetime import date, timedelta
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit, urlencode
from urllib.request import Request, urlopen


USERNAME = "Leon5428"
SOURCE = f"https://github.com/users/{USERNAME}/contributions"
OUTPUT = Path(__file__).resolve().parent / "assets/images/contributions.svg"
COLORS = ("#161b22", "#003d29", "#006d32", "#26a641", "#39d353")
REPOSITORY = "Leon5428/Leon5428"
REPO_OUTPUT = OUTPUT.with_name("repository.svg")


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
    language = escape(repo.get("language") or "Mixed")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="224" viewBox="0 0 800 224" role="img" aria-labelledby="title desc">
  <title id="title">{name} repository</title>
  <desc id="desc">{stars} stars, {forks} forks, {commits} commits on the default branch {branch}. Snapshot refreshed {date.today().isoformat()}.</desc>
  <rect x="1" y="1" width="798" height="222" rx="12" fill="#0d1117" stroke="#30363d"/>
  <g font-family="Segoe UI, Arial, sans-serif">
    <path d="M29 29h17v22H29z M33 29v22 M37 34h5" fill="none" stroke="#8b949e" stroke-width="1.5"/>
    <text x="58" y="48" font-size="23" font-weight="600" fill="#79c0ff">{name}</text>
    <rect x="694" y="27" width="75" height="25" rx="12" fill="none" stroke="#30363d"/>
    <text x="731" y="44" text-anchor="middle" font-size="12" fill="#8b949e">Public</text>
    <text x="29" y="84" font-size="16" fill="#c9d1d9">LeonBlog · 数学、密码学与个人知识笔记</text>
    <text x="29" y="109" font-size="13" fill="#8b949e">LaTeX notes · Python builds · A static home for learning</text>
    <path d="M29 128h740" stroke="#21262d"/>
    <text x="29" y="162" font-size="17" fill="#e3b341">★ {stars} Stars</text>
    <text x="209" y="162" font-size="17" fill="#bc8cff">⑂ {forks} Forks</text>
    <text x="389" y="162" font-size="17" fill="#7ee787">◷ {commits} Commits</text>
    <circle cx="665" cy="156" r="5" fill="#3d6117"/>
    <text x="679" y="162" font-size="15" fill="#c9d1d9">{language}</text>
    <text x="29" y="201" font-size="12" fill="#8b949e">Default branch: {branch} · Refreshed {date.today().isoformat()}</text>
  </g>
</svg>
'''


def fetch_repository() -> str:
    headers = {"User-Agent": "LeonBlog-profile", "Accept": "application/vnd.github+json"}
    api = f"https://api.github.com/repos/{REPOSITORY}"
    with urlopen(Request(api, headers=headers), timeout=30) as response:
        repo = json.load(response)
    query = urlencode({"per_page": 1, "sha": repo["default_branch"]})
    with urlopen(Request(f"{api}/commits?{query}", headers=headers), timeout=30) as response:
        commits = commit_count(json.load(response), response.headers.get("Link", ""))
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
    repository_svg = fetch_repository()
    OUTPUT.write_text(svg, encoding="utf-8", newline="\r\n")
    REPO_OUTPUT.write_text(repository_svg, encoding="utf-8", newline="\r\n")
    print(f"Updated {OUTPUT}")
    print(f"Updated {REPO_OUTPUT}")


if __name__ == "__main__":
    main()
