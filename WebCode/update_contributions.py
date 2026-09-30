"""Refresh the README heatmap: python WebCode/update_contributions.py."""

from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


USERNAME = "Leon5428"
SOURCE = f"https://github.com/users/{USERNAME}/contributions"
OUTPUT = Path(__file__).resolve().parent / "assets/images/contributions.svg"
COLORS = ("#161b22", "#003d29", "#006d32", "#26a641", "#39d353")


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
    OUTPUT.write_text(svg, encoding="utf-8", newline="\r\n")
    print(f"Updated {OUTPUT}")


if __name__ == "__main__":
    main()
