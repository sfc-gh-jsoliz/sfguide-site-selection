"""WCAG AA contrast check for the design tokens in docs/DESIGN.md. Exit 1 if any pair fails."""
import sys


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


LIGHT = {"canvas": "#F4F5FA", "paper": "#FFFFFF", "paper-2": "#F8F8FC"}
TEXT = {"ink": "#16163A", "muted": "#565873", "indigo-600": "#4F46C8", "apricot-ink": "#A44A12",
        "saturated": "#5E6A85", "good": "#1F7A4D", "bad": "#B23A2E", "west": "#0E7C86", "south": "#B34F12", "midwest": "#7A6A1F"}
PAIRS = [(f"{n} on {b}", fg, bg) for n, fg in TEXT.items() for b, bg in LIGHT.items()]
PAIRS += [
    ("apricot-ink on apricot-50", "#A44A12", "#FDEBDD"), ("indigo-600 on indigo-50", "#4F46C8", "#EEF0FB"),
    ("saturated on #ECEEF3", "#5E6A85", "#ECEEF3"), ("good on #E1F2E8", "#1F7A4D", "#E1F2E8"), ("bad on #F8E3E0", "#B23A2E", "#F8E3E0"),
    ("sample text on sample bg", "#7A5200", "#FFF2D6"), ("white on indigo-950", "#FFFFFF", "#1C1A4A"),
    ("#C9C7F2 nav on indigo-950", "#C9C7F2", "#1C1A4A"), ("white on indigo-800", "#FFFFFF", "#2E2A78"),
    ("white on indigo-600", "#FFFFFF", "#4F46C8"), ("apricot on indigo-950", "#F29A4A", "#1C1A4A"),
    ("dark text on dark card", "#E9E9F7", "#1A1A3D"), ("dark muted on dark card", "#A9AACB", "#1A1A3D"),
    ("dark muted on dark canvas", "#A9AACB", "#11112B"), ("#B7B4F0 link on dark card", "#B7B4F0", "#1A1A3D"),
    ("white on heat-3", "#FFFFFF", "#6A5FD8"), ("ink on heat-1", "#16163A", "#B7B4F0"),
]
bad = 0
for name, fg, bg in PAIRS:
    r = ratio(fg, bg)
    ok = r >= 4.5
    bad += not ok
    print(f"{'PASS' if ok else 'FAIL'} {r:5.2f}  {name}")
sys.exit(1 if bad else 0)
