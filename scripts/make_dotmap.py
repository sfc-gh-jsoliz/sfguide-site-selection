"""Generate the dot-map of the contiguous US used by the app, the hosted example and the guide.

A coarse hand-traced outline (about 50 vertices) is sampled on a regular lon/lat grid; each grid
point inside the outline becomes one dot. Deterministic, no downloads. Writes
app/static/dotmap.json and docs/try/data/dotmap.json as [[lon, lat], ...].
"""
import json
from pathlib import Path

OUTLINE = [(-124.7, 48.4), (-123.9, 46.2), (-124.2, 42.0), (-124.4, 40.3), (-122.4, 37.2), (-120.6, 34.5),
           (-117.1, 32.5), (-114.7, 32.7), (-111.0, 31.3), (-108.2, 31.3), (-106.5, 31.8), (-104.5, 29.6),
           (-103.0, 29.0), (-101.4, 29.8), (-99.5, 27.5), (-97.4, 25.9), (-97.2, 27.8), (-94.7, 29.4),
           (-93.8, 29.7), (-90.0, 29.1), (-89.4, 30.2), (-85.1, 29.7), (-83.0, 29.1), (-82.7, 27.5),
           (-81.2, 25.2), (-80.1, 25.8), (-80.6, 28.4), (-81.4, 30.7), (-79.2, 33.2), (-75.5, 35.2),
           (-76.0, 37.0), (-75.0, 38.8), (-74.0, 40.6), (-71.9, 41.3), (-70.0, 41.7), (-70.7, 43.1),
           (-67.0, 44.8), (-67.8, 47.1), (-69.2, 47.4), (-71.5, 45.0), (-74.9, 45.0), (-76.5, 44.2),
           (-79.2, 43.4), (-79.0, 42.8), (-82.4, 41.7), (-83.1, 42.1), (-82.5, 45.3), (-84.6, 46.4),
           (-88.4, 48.3), (-89.6, 48.0), (-95.2, 49.0), (-123.3, 49.0)]


def inside(x, y, poly):
    hit, j = False, len(poly) - 1
    for i, (xi, yi) in enumerate(poly):
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


STEP = 0.95
dots = []
lat = 24.6
while lat <= 49.2:
    lon = -125.0
    while lon <= -66.5:
        if inside(lon, lat, OUTLINE):
            dots.append([round(lon, 2), round(lat, 2)])
        lon += STEP * 1.25  # wider in longitude so dots look evenly spaced at mid latitudes
    lat += STEP
root = Path(__file__).resolve().parents[1]
for p in (root / "app" / "static" / "dotmap.json", root / "docs" / "try" / "data" / "dotmap.json"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dots))
print(len(dots), "dots")
