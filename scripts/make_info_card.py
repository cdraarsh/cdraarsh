#!/usr/bin/env python3
"""Generate an animated neofetch-style info card SVG for a GitHub README.

No dependencies beyond the standard library. Writes to REPO/info-card.svg.
Set STATIC=1 in the environment to emit a frozen, fully-visible frame with
no animation elements (useful for quick diffing / debugging).
"""
import os
import textwrap
import html

WIDTH = 490
PAD_X = 20
PAD_TOP = 22

TITLE = "cdraarsh@github"
TITLE_FONT_SIZE = 15

KEY_FONT_SIZE = 13
VALUE_FONT_SIZE = 13
LINE_HEIGHT = 20
GROUP_GAP = 6  # extra space between key-groups

GUTTER = 98  # x-offset from PAD_X where values start
CHAR_WIDTH = VALUE_FONT_SIZE * 0.6  # rough monospace advance width
VALUE_MAX_WIDTH = WIDTH - PAD_X - GUTTER - PAD_X
MAX_CHARS = max(20, int(VALUE_MAX_WIDTH / CHAR_WIDTH))

BG = "#0d1117"
BORDER = "#30363d"
ACCENT = "#39d353"
VALUE_COLOR = "#c9d1d9"
DIM = "#8b949e"

FONT_STACK = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

ROWS = [
    ("Now", ["Product @ SigIQ.ai  ·  EverTutor (K-12 AI tutor)"]),
    ("Prev", ["Apponty  ·  Product Intern"]),
    ("Stack", ["Python  ·  TypeScript  ·  Next.js  ·  Claude Code skills"]),
    ("Highlights", [
        "claude-web-studio — AI website builder stack",
        "equity-research-india — Indian-equities research skill",
        "company-recon — structured company background checks",
        "notebooklm-newsletter-pipeline — Gmail → NotebookLM digests",
        "viewmd — native Mac Markdown reader",
    ]),
]

STATIC = os.environ.get("STATIC") == "1"


def esc(s):
    return html.escape(s, quote=True)


def wrap(value):
    return textwrap.wrap(value, width=MAX_CHARS, break_long_words=False, break_on_hyphens=False) or [""]


def build():
    lines = []  # list of dicts: {key, text, is_continuation}
    for key, values in ROWS:
        first_row = True
        for value in values:
            for i, wrapped_line in enumerate(wrap(value)):
                lines.append({
                    "key": key if (first_row and i == 0) else "",
                    "text": wrapped_line,
                })
                first_row = False if i == 0 else first_row

    title_y = PAD_TOP + TITLE_FONT_SIZE
    rule_y = title_y + 10
    content_start_y = rule_y + 26

    y = content_start_y
    row_elems = []
    idx = 0
    prev_key = None
    for line in lines:
        # small extra gap when a new key-group starts (but not for the very first line)
        if line["key"] and idx != 0:
            y += GROUP_GAP

        delay = idx * 0.09
        anim_attrs = ""
        cls = ""
        if not STATIC:
            cls = ' class="ln"'
            anim_attrs = f' style="animation-delay:{delay:.2f}s"'

        parts = []
        if line["key"]:
            parts.append(
                f'<text x="{PAD_X}" y="{y}" font-family="{FONT_STACK}" '
                f'font-size="{KEY_FONT_SIZE}" font-weight="700" fill="{ACCENT}">{esc(line["key"])}</text>'
            )
        parts.append(
            f'<text x="{PAD_X + GUTTER}" y="{y}" font-family="{FONT_STACK}" '
            f'font-size="{VALUE_FONT_SIZE}" fill="{VALUE_COLOR}">{esc(line["text"])}</text>'
        )
        row_elems.append(f'<g{cls}{anim_attrs}>' + "".join(parts) + "</g>")

        y += LINE_HEIGHT
        idx += 1

    height = y + PAD_TOP - (LINE_HEIGHT - 14)
    height = max(370, min(420, height))

    title_delay = 0.0
    title_cls = ' class="ln"' if not STATIC else ""
    title_style = f' style="animation-delay:{title_delay:.2f}s"' if not STATIC else ""
    rule_cls = ' class="ln"' if not STATIC else ""
    rule_style = f' style="animation-delay:0.04s"' if not STATIC else ""

    style_block = ""
    if not STATIC:
        style_block = f"""
  <style>
    .ln {{
      opacity: 0;
      animation: fadeSlide 0.5s ease-out forwards;
    }}
    @keyframes fadeSlide {{
      0%   {{ opacity: 0; transform: translateY(6px); }}
      100% {{ opacity: 1; transform: translateY(0); }}
    }}
  </style>"""

    svg = f'''<svg width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="neofetch-style info card for cdraarsh">{style_block}
  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="8" fill="{BG}" stroke="{BORDER}"/>
  <g{title_cls}{title_style}>
    <text x="{PAD_X}" y="{title_y}" font-family="{FONT_STACK}" font-size="{TITLE_FONT_SIZE}" font-weight="700" fill="{ACCENT}">{esc(TITLE)}</text>
  </g>
  <g{rule_cls}{rule_style}>
    <line x1="{PAD_X}" y1="{rule_y}" x2="{WIDTH - PAD_X}" y2="{rule_y}" stroke="{DIM}" stroke-opacity="0.4" stroke-width="1"/>
  </g>
  {chr(10).join(row_elems)}
</svg>
'''
    return svg


def main():
    svg = build()
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "info-card.svg")
    with open(out_path, "w") as f:
        f.write(svg)
    print(f"wrote {out_path} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
