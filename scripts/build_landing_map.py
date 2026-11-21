"""Write the dot-map inside docs/index.html (landing hero); paste its output over the existing <svg> there from app/static/dotmap.json and the captured metros/cells."""
import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
dots = json.loads((R / "app/static/dotmap.json").read_text())
metros = json.loads((R / "app/sample/metros.json").read_text())
cells = json.loads((R / "app/sample/cells.json").read_text())
best = {}
for i, c in enumerate(sorted(cells, key=lambda c: (-c["max_opportunity_score"], -c["total_white_space_usd"]))):
    best.setdefault(c["metro_id"], i + 1)
W, H = 640, 360


def x(lon):
    return 10 + (W - 20) * (lon + 125) / 58.5


def y(lat):
    return 10 + (H - 20) * (1 - (lat - 24.3) / 25.2)


out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="Dot map of the contiguous US with ten metros; Houston and Phoenix, the top two targets, pulse in apricot">',
       '<style>.p{animation:pl 2.4s ease-out infinite;transform-box:fill-box;transform-origin:center}.p2{animation-delay:1.2s}'
       '@keyframes pl{0%{transform:scale(.6);opacity:.9}100%{transform:scale(2.6);opacity:0}}'
       '@media (prefers-reduced-motion:reduce){.p{animation:none;opacity:.4}}</style>']
out += [f'<circle cx="{x(a):.1f}" cy="{y(b):.1f}" r="2.1" fill="#4A45A8"/>' for a, b in dots]
for m in metros:
    cx, cy, rank = x(m["longitude"]), y(m["latitude"]), best[m["metro_id"]]
    if rank <= 2:
        cls = "p" if rank == 1 else "p p2"
        out.append(f'<circle class="{cls}" cx="{cx:.1f}" cy="{cy:.1f}" r="9" fill="none" stroke="#F29A4A" stroke-width="2"/>')
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="#F29A4A"/>')
        out.append(f'<text x="{cx + 12:.1f}" y="{cy + 4:.1f}" fill="#FFFFFF" font-size="13" font-weight="700" font-family="Figtree, sans-serif">#{rank} {m["metro_name"]}</text>')
    else:
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" fill="#B7B4F0"/>')
out.append("</svg>")
(Path("/tmp/hero-map.svg")).write_text("\n".join(out))
print("ok", len(dots))
