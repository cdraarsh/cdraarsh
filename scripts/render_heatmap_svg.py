#!/usr/bin/env python3
"""Render data/contributions.json into a self-contained animated contrib-heatmap.svg.

Fully self-contained: CSS @keyframes inline, no external fonts/scripts/images.
Width is fixed at 860px (370 + 490) to line up with a two-column table in the README.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = REPO_ROOT / "data" / "contributions.json"
OUT_PATH = REPO_ROOT / "contrib-heatmap.svg"

PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

SVG_WIDTH = 860
CELL = 11
GAP = 3
RADIUS = 2
LEFT_MARGIN = 32
GRID_TOP = 44
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAY_LABELS = {1: "Mon", 3: "Wed", 5: "Fri"}  # row -> label (Sun=0 .. Sat=6)


def grid_position(date: datetime, anchor_sunday: datetime) -> tuple[int, int]:
    """Return (row, col): row = day-of-week with Sunday=0, col = weeks since anchor."""
    row = (date.weekday() + 1) % 7  # Mon=0..Sun=6 -> Sun=0..Sat=6
    col = (date - anchor_sunday).days // 7
    return row, col


def main() -> None:
    if not DATA_PATH.exists():
        raise SystemExit(f"render_heatmap_svg: FATAL: {DATA_PATH} not found — run fetch_contributions.py first")

    data = json.loads(DATA_PATH.read_text())
    days = data["days"]
    if not days:
        raise SystemExit("render_heatmap_svg: FATAL: contributions.json has zero days")

    parsed = [(datetime.strptime(d["date"], "%Y-%m-%d"), d["level"], d["count"]) for d in days]
    parsed.sort(key=lambda t: t[0])

    min_date = parsed[0][0]
    anchor_sunday = min_date - timedelta(days=(min_date.weekday() + 1) % 7)

    # 90th-percentile threshold over nonzero days -> promotes a day to level 5.
    nonzero_counts = sorted(c for _, _, c in parsed if c > 0)
    if nonzero_counts:
        idx = 0.9 * (len(nonzero_counts) - 1)
        lo, hi = int(idx), min(int(idx) + 1, len(nonzero_counts) - 1)
        frac = idx - lo
        p90 = nonzero_counts[lo] + (nonzero_counts[hi] - nonzero_counts[lo]) * frac
    else:
        p90 = 0

    cells = []
    max_col = 0
    for date, level, count in parsed:
        row, col = grid_position(date, anchor_sunday)
        max_col = max(max_col, col)
        effective_level = 5 if (count > 0 and count > p90) else max(0, min(level, 4))
        cells.append({"date": date, "row": row, "col": col, "count": count, "level": effective_level})

    num_cols = max_col + 1
    grid_width = num_cols * CELL + (num_cols - 1) * GAP
    grid_height = 7 * CELL + 6 * GAP

    legend_y = GRID_TOP + grid_height + 34
    footer_y1 = legend_y + 30
    footer_y2 = footer_y1 + 20
    footer_y3 = footer_y2 + 20
    svg_height = footer_y3 + 24

    bg = "#0d1117"
    fg = "#c9d1d9"
    muted = "#8b949e"

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{svg_height}" '
        f'viewBox="0 0 {SVG_WIDTH} {svg_height}" font-family="-apple-system, BlinkMacSystemFont, '
        f'\'Segoe UI\', Helvetica, Arial, sans-serif">'
    )
    parts.append(f'<rect width="{SVG_WIDTH}" height="{svg_height}" fill="{bg}" rx="6"/>')

    # One-shot diagonal reveal: staggered by (week + day), plays once, freezes at full opacity.
    parts.append(
        "<style>"
        "@keyframes revealCell{0%{opacity:0;transform:translateY(-8px);}100%{opacity:1;transform:translateY(0);}}"
        ".cell{opacity:0;animation-name:revealCell;animation-duration:0.4s;"
        "animation-timing-function:ease-out;animation-fill-mode:forwards;animation-iteration-count:1;}"
        "</style>"
    )

    # Title
    parts.append(
        f'<text x="{LEFT_MARGIN}" y="20" fill="{fg}" font-size="14" font-weight="600">'
        f"cdraarsh &#8226; GitHub contributions</text>"
    )

    # Month labels: label the first new month seen at the top of each column.
    # Skip a label that would overlap the previous one (columns are only 14px apart;
    # a 3-letter label needs ~24px, so require enough pixel gap since the last label).
    last_month = None
    last_label_col = None
    for col in range(num_cols):
        col_dates = [c["date"] for c in cells if c["col"] == col]
        if not col_dates:
            continue
        first_date = min(col_dates)
        if first_date.month == last_month:
            continue
        if last_label_col is not None and (col - last_label_col) * (CELL + GAP) < 24:
            continue
        last_month = first_date.month
        last_label_col = col
        x = LEFT_MARGIN + col * (CELL + GAP)
        parts.append(
            f'<text x="{x}" y="{GRID_TOP - 8}" fill="{muted}" font-size="10">'
            f"{MONTH_ABBR[first_date.month - 1]}</text>"
        )

    # Weekday labels
    for row, label in WEEKDAY_LABELS.items():
        y = GRID_TOP + row * (CELL + GAP) + CELL - 2
        parts.append(f'<text x="0" y="{y}" fill="{muted}" font-size="10">{label}</text>')

    # Day cells, diagonal stagger by (week + day)
    STEP = 0.02
    for c in cells:
        x = LEFT_MARGIN + c["col"] * (CELL + GAP)
        y = GRID_TOP + c["row"] * (CELL + GAP)
        delay = (c["col"] + c["row"]) * STEP
        color = PALETTE[c["level"]]
        date_str = c["date"].strftime("%b %-d, %Y")
        count = c["count"]
        contrib_word = "contribution" if count == 1 else "contributions"
        parts.append(
            f'<rect class="cell" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" ry="{RADIUS}" '
            f'fill="{color}" style="animation-delay:{delay:.2f}s">'
            f"<title>{count} {contrib_word} on {date_str}</title></rect>"
        )

    # Legend: Less -> More, six swatches, right-aligned
    legend_swatch = 10
    legend_gap = 3
    legend_total_w = len("Less") * 6 + 8 + 6 * legend_swatch + 5 * legend_gap + 8 + len("More") * 6
    legend_x = SVG_WIDTH - 15 - legend_total_w
    lx = legend_x
    parts.append(f'<text x="{lx}" y="{legend_y + 9}" fill="{muted}" font-size="10">Less</text>')
    lx += 30
    for i, color in enumerate(PALETTE):
        sx = lx + i * (legend_swatch + legend_gap)
        parts.append(
            f'<rect x="{sx}" y="{legend_y}" width="{legend_swatch}" height="{legend_swatch}" '
            f'rx="{RADIUS}" ry="{RADIUS}" fill="{color}"/>'
        )
    lx += 6 * (legend_swatch + legend_gap) + 4
    parts.append(f'<text x="{lx}" y="{legend_y + 9}" fill="{muted}" font-size="10">More</text>')

    # Stats footer
    year_total = data["year_total"]
    current_streak = data["current_streak"]
    longest_streak = data["longest_streak"]
    best_day = data["best_day"]

    parts.append(
        f'<text x="{LEFT_MARGIN}" y="{footer_y1}" fill="{fg}" font-size="13" font-weight="600">'
        f"{year_total} contributions in the last year</text>"
    )
    parts.append(
        f'<text x="{LEFT_MARGIN}" y="{footer_y2}" fill="{muted}" font-size="11">'
        f"Current streak: {current_streak} day{'s' if current_streak != 1 else ''} &#8226; "
        f"Longest streak: {longest_streak} day{'s' if longest_streak != 1 else ''}</text>"
    )
    if best_day["count"] > 0:
        best_date_str = datetime.strptime(best_day["date"], "%Y-%m-%d").strftime("%b %-d, %Y")
        parts.append(
            f'<text x="{LEFT_MARGIN}" y="{footer_y3}" fill="{muted}" font-size="11">'
            f"Best day: {best_date_str} &#8226; {best_day['count']} contributions</text>"
        )

    parts.append("</svg>")

    OUT_PATH.write_text("\n".join(parts) + "\n")
    print(f"wrote {OUT_PATH} — {SVG_WIDTH}x{svg_height}, {len(cells)} cells, "
          f"{num_cols} weeks, p90 threshold={p90:.2f}")


if __name__ == "__main__":
    main()
