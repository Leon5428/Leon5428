"""Refresh README contribution and repository cards with public GitHub data."""

from datetime import date, timedelta
from html import escape
from html.parser import HTMLParser
from collections import Counter
import math
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
        if width + size > 56:
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
    owner, project = (escape(part) for part in repo["full_name"].split("/", 1))
    branch = escape(repo["default_branch"])
    language = escape(repo.get("language") or "Not detected")
    description = repo.get("description") or "No repository description provided."
    if repo["full_name"] == "Leon5428/Leon5428":
        description = "LeonBlog · 数学、密码学与个人知识笔记。用 LaTeX 记录，用静态网站分享。"
    first_line, second_line = description_lines(description)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="280" viewBox="0 0 480 280" role="img" aria-labelledby="title desc">
  <title id="title">{name} repository</title>
  <desc id="desc">{stars} stars, {forks} forks, {commits} commits on the default branch {branch}. Public repository snapshot.</desc>
  <rect x="1" y="1" width="478" height="278" rx="10" fill="#0d1117" stroke="#30363d"/>
  <g font-family="Segoe UI, Microsoft YaHei, Arial, sans-serif">
    <path d="M27 20h13v16H27z M31 20v16 M34 24h3" fill="none" stroke="#8b949e" stroke-width="1.5"/>
    <text x="49" y="33" font-size="13" fill="#8b949e">{owner}</text>
    <rect x="392" y="18" width="60" height="23" rx="11" fill="none" stroke="#30363d"/>
    <text x="422" y="34" text-anchor="middle" font-size="11" fill="#8b949e">Public</text>
    <text x="27" y="69" font-size="25" font-weight="600" fill="#58a6ff">{project}</text>
    <text x="27" y="100" font-size="14" fill="#b1bac4">{first_line}</text>
    <text x="27" y="123" font-size="14" fill="#b1bac4">{second_line}</text>
    <path d="M27 143h426" stroke="#21262d"/>
    <path d="M169 161v46 M311 161v46" stroke="#21262d"/>
    <text x="27" y="182" font-size="27" font-weight="600" fill="#e3b341">{stars}</text>
    <text x="27" y="204" font-size="12" fill="#8b949e">Stars</text>
    <text x="191" y="182" font-size="27" font-weight="600" fill="#bc8cff">{forks}</text>
    <text x="191" y="204" font-size="12" fill="#8b949e">Forks</text>
    <text x="333" y="182" font-size="27" font-weight="600" fill="#7ee787">{commits}</text>
    <text x="333" y="204" font-size="12" fill="#8b949e">Commits</text>
    <path d="M27 225h426" stroke="#21262d"/>
    <circle cx="32" cy="250" r="4" fill="#79c0ff"/>
    <text x="45" y="254" font-size="12" fill="#b1bac4">{language}</text>
    <text x="453" y="254" text-anchor="end" font-size="11" fill="#8b949e">Default branch: {branch}</text>
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


def api_json(path: str):
    request = Request("https://api.github.com/" + path, headers={
        "User-Agent": "LeonBlog-profile", "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def search_total(kind: str, query: str) -> int:
    result = api_json(f"search/{kind}?" + urlencode({"q": query, "per_page": 1}))
    if result.get("incomplete_results"):
        raise ValueError(f"GitHub returned incomplete {kind} statistics; images unchanged")
    return result["total_count"]


def public_repositories() -> list[dict]:
    repositories = []
    page = 1
    while True:
        batch = api_json(f"users/{USERNAME}/repos?type=owner&per_page=100&page={page}")
        repositories.extend(batch)
        if len(batch) < 100:
            return repositories
        page += 1


def daily_counts(html: str) -> dict[date, int]:
    """Match tooltip counts to cell IDs, never estimate counts from color levels."""
    calendar = ContributionCalendar()
    calendar.feed(html)
    cells = {}
    for tag in re.findall(r'<td\b[^>]*>', html):
        day = re.search(r'data-date="([^" ]+)"', tag)
        identifier = re.search(r'\bid="([^" ]+)"', tag)
        if day and identifier:
            cells[identifier[1]] = date.fromisoformat(day[1])
    counts = {}
    for attrs, body in re.findall(r'<tool-tip\b([^>]*)>(.*?)</tool-tip>', html, re.S):
        target = re.search(r'\bfor="([^" ]+)"', attrs)
        if target and target[1] in cells:
            match = re.match(r'\s*(No|[\d,]+) contributions? on ', body)
            if not match:
                raise ValueError("Unrecognized GitHub contribution tooltip")
            counts[cells[target[1]]] = 0 if match[1] == "No" else int(match[1].replace(",", ""))
    if set(counts) != set(calendar.days) or not 300 <= len(counts) <= 371:
        raise ValueError("Incomplete daily contribution counts; images unchanged")
    return dict(sorted(counts.items()))


def text(x, y, value, size=15, color="#b1bac4", anchor="start") -> str:
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'text-anchor="{anchor}">{escape(str(value))}</text>')


def card(title: str, body: str, width=480, height=280) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">'
            f'<title id="title">{escape(title)}</title>'
            f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="10" '
            'fill="#0d1117" stroke="#30363d"/>'
            '<g font-family="Segoe UI, Microsoft YaHei, Arial, sans-serif">'
            + body + '</g></svg>\n')


def render_profile(user: dict, repos: list[dict], counts: dict[date, int]) -> str:
    first, last = min(counts), max(counts)
    monthly = Counter()
    for day, count in counts.items():
        monthly[day.strftime("%Y-%m")] += count
    months = sorted(monthly)
    ceiling = max(1, max(monthly.values()))
    body = text(28, 46, user["login"] + (" · " + user["name"] if user.get("name") else ""), 26, "#58a6ff")
    body += text(28, 96, f"{sum(counts.values()):,} contributions", 21, "#7ee787")
    body += text(28, 130, f"{len(repos)} public repositories", 17)
    body += text(28, 164, "Joined " + user["created_at"][:10], 17)
    body += text(28, 244, f"{first} — {last}", 12, "#8b949e")
    body += text(916, 40, "Contributions by month", 13, "#8b949e", "end")
    points = [(390 + i * 526 / max(1, len(months)-1), 214 - monthly[m] / ceiling * 145) for i, m in enumerate(months)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x,y in points)
    body += f'<polygon points="390,214 {line} 916,214" fill="#238636" opacity="0.35"/>'
    body += f'<polyline points="{line}" fill="none" stroke="#3fb950" stroke-width="2.5"/>'
    for fraction in (0, .5, 1):
        y = 214 - 145*fraction
        body += f'<path d="M390 {y}H916" stroke="#30363d" stroke-dasharray="3 5"/>'
        body += text(934, y+4, f"{ceiling*fraction:g}", 10, "#8b949e", "end")
    for i,m in enumerate(months):
        if i % 2 == 0 or i == len(months)-1:
            body += text(round(points[i][0]), 239, m[2:].replace("-", "/"), 11, "#8b949e", "middle")
    return card("GitHub contribution overview", body, 960)


def render_stats(repos: list[dict], commits: int, prs: int, issues: int) -> str:
    owned = [r for r in repos if not r["fork"]]
    rows = [("Stars · owned non-fork repos", sum(r["stargazers_count"] for r in owned)),
            ("Authored commits · public index", commits),
            ("Pull requests opened", prs), ("Issues opened", issues),
            ("Public repositories", len(repos))]
    body = text(27, 44, "Stats", 25, "#58a6ff")
    for i,(label,value) in enumerate(rows):
        y = 84 + 34*i
        body += text(27,y,label,14) + text(450,y,f"{value:,}",20,"#7ee787","end")
    body += text(27,258,"Public GitHub data · all-time indexed activity",11,"#8b949e")
    return card("Public GitHub statistics", body)


def render_languages(repos: list[dict]) -> str:
    counts = Counter(r.get("language") or "Not detected" for r in repos if not r["fork"])
    entries = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    if len(entries) > 5:
        entries = entries[:4] + [("Other", sum(n for _,n in entries[4:]))]
    colors = ["#58a6ff", "#3fb950", "#bc8cff", "#e3b341", "#f78166"]
    total = sum(counts.values())
    body = text(27,44,"Top Languages by Repo",24,"#58a6ff")
    body += '<circle cx="350" cy="152" r="69" fill="none" stroke="#21262d" stroke-width="24"/>'
    offset = 0.0
    circumference = 2*math.pi*69
    for i,(language,count) in enumerate(entries):
        length = count/total*circumference
        body += (f'<circle cx="350" cy="152" r="69" fill="none" stroke="{colors[i]}" stroke-width="24" '
                 f'stroke-dasharray="{length:.4f} {circumference-length:.4f}" stroke-dashoffset="{-offset:.4f}" transform="rotate(-90 350 152)"/>')
        offset += length
        body += f'<circle cx="32" cy="{87+i*30}" r="4" fill="{colors[i]}"/>'
        body += text(45,92+i*30,f"{language} · {count}",13)
    body += text(350,153,total,28,"#e6edf3","middle") + text(350,175,"repositories",11,"#8b949e","middle")
    body += text(27,258,"Primary language per repository · excludes forks",11,"#8b949e")
    return card("Repository primary language distribution",body)


def write_changed(path: Path, content: str) -> bool:
    data = content.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n").encode("utf-8")
    if path.exists() and path.read_bytes() == data:
        return False
    path.write_bytes(data)
    return True


def main() -> None:
    request = Request(SOURCE, headers={"User-Agent": "LeonBlog-profile-calendar"})
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8")
        svg = render_calendar(html)
    # Finish network requests before modifying any local files.
    images = {OUTPUT: svg}
    for repository, filename in REPOSITORIES.items():
        images[OUTPUT.with_name(filename)] = fetch_repository(repository)
    user = api_json(f"users/{USERNAME}")
    repos = public_repositories()
    images[OUTPUT.with_name("profile-overview.svg")] = render_profile(user, repos, daily_counts(html))
    images[OUTPUT.with_name("profile-stats.svg")] = render_stats(
        repos, search_total("commits", f"author:{USERNAME}"),
        search_total("issues", f"author:{USERNAME} is:pr"),
        search_total("issues", f"author:{USERNAME} is:issue"))
    images[OUTPUT.with_name("profile-languages.svg")] = render_languages(repos)
    readme = README.read_text(encoding="utf-8")
    for path, image in images.items():
        changed = write_changed(path, image)
        # A content-based version changes the URL only when the image changes.
        version = hashlib.sha256(image.encode("utf-8")).hexdigest()[:12]
        source = f"./WebCode/assets/images/{path.name}"
        readme = re.sub(r'(src="' + re.escape(source) + r')(?:\?[^"\s]*)?"',
                        lambda match: f'{match[1]}?v={version}"', readme)
        print(f"{'Updated' if changed else 'Unchanged'} {path}")
    write_changed(README, readme)


if __name__ == "__main__":
    main()
