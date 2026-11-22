import argparse
from datetime import date, timedelta
from html.parser import HTMLParser
from math import cos, pi, sin
from pathlib import Path
from random import Random
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "ContributionCalendar-day" in attrs.get("class", "").split():
            day = date.fromisoformat(attrs["data-date"])
            level = int(attrs["data-level"])
            if level not in range(5):
                raise ValueError(f"Unknown activity level: {level}")
            self.days[day] = level


cli = argparse.ArgumentParser()
cli.add_argument("--from-html", type=Path)
args = cli.parse_args()
parser = CalendarParser()
if args.from_html:
    parser.feed(args.from_html.read_text())
else:
    request = Request(
        "https://github.com/users/hindkhial/contributions",
        headers={"User-Agent": "hindkhial-contribution-garden"},
    )
    with urlopen(request, timeout=30) as response:
        parser.feed(response.read().decode("utf-8"))
days = parser.days
if not 360 <= len(days) <= 370 or (max(days) - min(days)).days + 1 != len(days):
    raise ValueError("GitHub did not return a complete year of contribution cells")

first_day = min(days)
sunday = first_day - timedelta(days=(first_day.weekday() + 1) % 7)
positions = {}
for day, level in days.items():
    week, weekday = divmod((day - sunday).days, 7)
    positions[week, weekday] = level

columns = max(week for week, _ in positions) + 1
clusters = []
for position in sorted(position for position, level in positions.items() if level > 0):
    week, weekday = position
    if clusters and clusters[-1][-1] == (week, weekday - 1):
        clusters[-1].append(position)
    else:
        clusters.append([position])

# Start with a sweep across the calendar, then return toward the middle.
if len(clusters) >= 3:
    first = clusters[0]
    far = clusters[-1]
    middle = clusters[len(clusters) // 2]
    remaining = [cluster for cluster in clusters if cluster not in (first, far, middle)]
    Random(17).shuffle(remaining)
    clusters = [first, far, middle, *remaining]
route = [position for cluster in clusters for position in cluster]
colors = ["#c8529a", "#9362c4", "#e077a1"]
palette = ["#f3dfe9", "#e3c8ef", "#cb9fdf", "#ab72c7", "#854a9b"]
def center(x, y):
    return 22 + 14*x, 21 + 14*y


def drift(origin, target, bend, begin, end):
    x, y = origin
    tx, ty = target
    direction = -1 if bend < 60 else 1
    upper_lane, lower_lane = 11, 115
    for sample in range(1, 37):
        t = sample / 36
        eased = (1 - cos(pi * t)) / 2
        px = x + (tx - x) * eased
        baseline = y + (ty - y) * eased
        wave = direction * sin(2.5 * pi * t) * sin(pi * t)
        room = lower_lane - baseline if wave > 0 else baseline - upper_lane
        py = baseline + wave * room * 1.22
        py = min(lower_lane, max(upper_lane, py))
        yield begin + (end - begin) * t, (px, py)


origin = (16, 50)
width = 30 + columns * 14
frames = [(0, origin)]
landings = {}
blooms = []
for index, position in enumerate(route):
    begin, previous = frames[-1]
    target = center(*position)
    bend = (4, 114, 12, 104)[index % 4]
    travel = 1.30 + min(abs(target[0] - previous[0]) / 155, 1.25)
    adjacent = index > 0 and route[index - 1] == (position[0], position[1] - 1)
    if adjacent:
        leg = [(begin + .34, target)]
        blooms.extend(leg)
    else:
        leg = list(drift(previous, target, bend, begin, begin + travel))
        blooms.extend(leg[i] for i in (2, 6, 10, 14, 18, 22, 26, 30, 34, 35))
    frames.extend(leg)
    landings[position] = leg[-1][0]
    frames.append((leg[-1][0] + .08, target))
begin, previous = frames[-1]
if route:
    exit_leg = list(drift(previous, origin, 118, begin, begin + 3.5))
else:
    edge = (width - 17, 62)
    outbound = list(drift(origin, edge, 10, 0, 3.8))
    frames.extend(outbound)
    blooms.extend(outbound[i] for i in (8, 17, 26, 35))
    exit_leg = list(drift(edge, origin, 117, 3.8, 7.6))
frames.extend(exit_leg)
blooms.extend(exit_leg[i] for i in (4, 10, 16, 22, 28, 34))
duration = frames[-1][0] + .5
frames.append((duration, origin))


def fraction(seconds):
    return f"{seconds / duration:.7f}"


svg = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="126" viewBox="0 0 {width} 126" role="img" aria-labelledby="title desc">',
    '<title id="title">Bubble Garden</title>',
    f'<desc id="desc">Public GitHub contribution calendar for hindkhial, {min(days)} through {max(days)}. Darker lilac cells indicate more activity. A plum butterfly wanders through the garden leaving pink and lilac blooms. When it lands on an active day, that square turns pastel pink.</desc>',
    f'<rect width="{width}" height="126" rx="14" fill="#faf0f8"/>',
]
for (week, weekday), level in sorted(positions.items()):
    cx, cy = center(week, weekday)
    cell = f'<rect x="{cx-5}" y="{cy-5}" width="10" height="10" rx="2.5" fill="{palette[level]}"'
    if level:
        landing = fraction(landings[week, weekday])
        svg.append(cell + f'><animate attributeName="fill" values="{palette[level]};{palette[0]};{palette[0]}" keyTimes="0;{landing};1" calcMode="discrete" dur="{duration}s" repeatCount="indefinite"/></rect>')
    else:
        svg.append(cell + '/>')

for index, (landing, (cx, cy)) in enumerate(blooms):
    times = ";".join(fraction(t) for t in (0, landing, landing + .08, min(landing + 1.85, duration - .02), duration))
    svg.append(f'<g transform="translate({cx:.2f} {cy:.2f})" fill="{colors[index % len(colors)]}" opacity="0">')
    svg.append(f'<animate attributeName="opacity" values="0;0;1;0;0" keyTimes="{times}" dur="{duration}s" repeatCount="indefinite"/>')
    svg.extend(f'<circle cx="{dx}" cy="{dy}" r="2.6"/>' for dx, dy in [(0,-3),(3,0),(0,3),(-3,0)])
    svg.append('<circle r="1.4" fill="#fff2bc"/></g>')

svg.append(f'<g transform="translate({origin[0]} {origin[1]})"><g transform="scale(.72)"><path fill="#814668" stroke="#fff0fb" stroke-width="1.3" d="M0 -2 C-17 -17 -16 0 -8 3 C-14 11 -3 13 0 4 C3 13 14 11 8 3 C16 0 17 -17 0 -2Z"/><path d="M0 5V-4m0 1 -3 -5m3 5 3 -5" fill="none" stroke="#663556" stroke-width="1.6" stroke-linecap="round"/></g>')
translations = ";".join(f"{x:.2f} {y:.2f}" for _, (x, y) in frames)
keytimes = ";".join(fraction(t) for t, _ in frames)
svg.append(f'<animateTransform attributeName="transform" type="translate" values="{translations}" keyTimes="{keytimes}" dur="{duration}s" repeatCount="indefinite"/>')
svg.append('</g></svg>')
svg = "\n".join(svg)
ET.fromstring(svg)
Path("bubble-garden.svg").write_text(svg + "\n")

print(f"Rendered {len(days)} calendar days and {len(route)} landings from {min(days)} through {max(days)}.")
