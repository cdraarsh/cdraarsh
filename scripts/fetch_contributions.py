#!/usr/bin/env python3
"""Scrape cdraarsh's public GitHub contribution calendar into data/contributions.json.

No API/token — parses the public HTML fragment at
https://github.com/users/<user>/contributions. Meant to run unattended
(daily cron): any parse failure exits nonzero with a clear message rather
than silently writing an empty/zeroed calendar.
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

USERNAME = "cdraarsh"
URL = f"https://github.com/users/{USERNAME}/contributions"
REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "contributions.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def die(msg: str) -> "NoReturn":
    print(f"fetch_contributions: FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_tooltip_count(text: str) -> int:
    text = text.strip()
    if text.lower().startswith("no contributions"):
        return 0
    m = re.match(r"^(\d+)", text)
    if not m:
        die(f"could not parse a leading integer out of tooltip text: {text!r}")
    return int(m.group(1))


def compute_streaks(days: list[dict]) -> tuple[int, int]:
    """days must be chronological. Returns (current_streak, longest_streak)."""
    longest = 0
    running = 0
    for d in days:
        if d["count"] > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0

    current = 0
    for d in reversed(days):
        if d["count"] > 0:
            current += 1
        else:
            break
    return current, longest


def main() -> None:
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        die(f"request to {URL} failed: {e}")

    if resp.status_code != 200:
        die(f"GET {URL} returned HTTP {resp.status_code}, expected 200")

    soup = BeautifulSoup(resp.text, "html.parser")

    h2 = soup.find("h2", id="js-contribution-activity-description")
    if h2 is None:
        die("selector h2#js-contribution-activity-description not found — GitHub markup may have changed")
    h2_text = " ".join(h2.get_text().split())
    m = re.search(r"(\d+)\s+contributions?\s+in the last year", h2_text)
    if not m:
        die(f"could not parse year total out of h2 text: {h2_text!r}")
    year_total = int(m.group(1))

    day_cells = soup.select("td.ContributionCalendar-day")
    if not day_cells:
        die("selector td.ContributionCalendar-day found zero cells — GitHub markup may have changed")

    # tool-tip elements carry the exact count, keyed by the day cell's id via `for`.
    tooltip_by_for = {}
    for tt in soup.find_all("tool-tip"):
        for_id = tt.get("for")
        if for_id:
            tooltip_by_for[for_id] = tt.get_text()

    days = []
    missing_tooltip = 0
    missing_date = 0
    for cell in day_cells:
        date = cell.get("data-date")
        if not date:
            missing_date += 1
            continue
        level_raw = cell.get("data-level")
        level = int(level_raw) if level_raw is not None else 0

        cell_id = cell.get("id")
        tooltip_text = tooltip_by_for.get(cell_id)
        if tooltip_text is None:
            missing_tooltip += 1
            count = 0
        else:
            count = parse_tooltip_count(tooltip_text)

        days.append({"date": date, "level": level, "count": count})

    if missing_date:
        die(f"{missing_date} day cell(s) had no data-date attribute — GitHub markup may have changed")
    if missing_tooltip == len(days):
        die("no day cell matched a tool-tip by id — tool-tip/for join is broken, GitHub markup may have changed")

    days.sort(key=lambda d: d["date"])

    if len(days) < 300:
        die(f"only parsed {len(days)} day cells, expected ~370 — likely a broken parse, refusing to write output")

    current_streak, longest_streak = compute_streaks(days)

    best_day = max(days, key=lambda d: d["count"])
    best_day_out = {"date": best_day["date"], "count": best_day["count"]}

    monthly_totals = defaultdict(int)
    for d in days:
        month_key = d["date"][:7]  # YYYY-MM
        monthly_totals[d["date"][:7]] += d["count"]
    monthly_totals = dict(sorted(monthly_totals.items()))

    out = {
        "days": days,
        "year_total": year_total,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "best_day": best_day_out,
        "monthly_totals": monthly_totals,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {OUT_PATH} — {len(days)} days, year_total={year_total}, "
          f"current_streak={current_streak}, longest_streak={longest_streak}")


if __name__ == "__main__":
    main()
