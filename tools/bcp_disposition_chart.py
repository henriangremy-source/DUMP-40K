#!/usr/bin/env python3
"""Chart the Force Disposition split by faction for a Best Coast Pairings event.

    python3 tools/bcp_disposition_chart.py ChZP41nemm16

Pulls the event's player list from the BCP API -- each player carries a faction
and a `subFaction`, which is where BCP stores the WTC Force Disposition -- and
draws a horizontal stacked bar chart, one row per faction, sorted by headcount.

Writes a PNG and the underlying counts as CSV next to it.
"""

import argparse
import collections
import csv
import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://newprod-api.bestcoastpairings.com/v1"
HEADERS = {"client-id": "web-app", "User-Agent": "Mozilla/5.0"}

# Stack order, left to right. Also the legend order.
DISPOSITIONS = [
    "Purge the Foe",
    "Reconnaissance",
    "Disruption",
    "Take and Hold",
    "Priority Assets",
]

# Validated against scripts/validate_palette.js from the dataviz skill:
# lightness band, chroma floor and normal-vision separation all pass. The
# blue/purple pair sits in the 6-8 deutan band, which is legal because every
# segment wide enough to matter carries its own printed count.
COLORS = {
    "Purge the Foe": "#C0392B",
    "Reconnaissance": "#2E86C1",
    "Disruption": "#8E44AD",
    "Take and Hold": "#1E8449",
    "Priority Assets": "#D68910",
}

# BCP's faction names, tidied for the axis only.
LABEL_FIXES = {"Space Marines (Astartes)": "Space Marines"}


def get(path, params, retries=4):
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    delay = 2
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=HEADERS), timeout=30
            ) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries:
                raise
            time.sleep(delay)
            delay *= 2


def fetch_event(event_id):
    return get(f"events/{event_id}", {})


def fetch_players(event_id):
    players, next_key = [], None
    while True:
        params = {"eventId": event_id, "limit": 100}
        if next_key:
            params["nextKey"] = next_key
        payload = get("players", params)
        players.extend(payload.get("data", []))
        next_key = payload.get("nextKey")
        if not next_key:
            return players
        time.sleep(0.2)


def tally(players):
    """Count players per (faction, disposition), skipping incomplete entries."""
    counts = collections.defaultdict(collections.Counter)
    skipped = 0
    for player in players:
        faction = (player.get("faction") or {}).get("name")
        disposition = (player.get("subFaction") or {}).get("name")
        if not faction or disposition not in DISPOSITIONS:
            skipped += 1
            continue
        counts[LABEL_FIXES.get(faction, faction)][disposition] += 1
    return counts, skipped


def draw(counts, event_name, out_png):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    # Biggest faction on top: plot ascending, since y grows upward.
    factions = sorted(counts, key=lambda f: (sum(counts[f].values()), f))
    totals = [sum(counts[f].values()) for f in factions]
    grand_total = sum(totals)
    x_max = max(totals)

    fig, ax = plt.subplots(figsize=(13, 0.42 * len(factions) + 2.2))
    y = range(len(factions))
    left = [0] * len(factions)

    for disposition in DISPOSITIONS:
        widths = [counts[f][disposition] for f in factions]
        ax.barh(
            y,
            widths,
            left=left,
            height=0.72,
            color=COLORS[disposition],
            edgecolor="white",
            linewidth=1.2,
            zorder=3,
        )
        for row, (width, start) in enumerate(zip(widths, left)):
            # Only label a segment wide enough to hold the digits.
            if width / x_max > 0.03:
                ax.text(
                    start + width / 2,
                    row,
                    str(width),
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=9,
                    fontweight="bold",
                    zorder=4,
                )
        left = [a + b for a, b in zip(left, widths)]

    for row, total in enumerate(totals):
        ax.text(
            total + x_max * 0.008,
            row,
            str(total),
            ha="left",
            va="center",
            fontsize=9,
            fontweight="bold",
            color="#2A2A2A",
        )

    ax.set_yticks(list(y))
    ax.set_yticklabels(factions, fontsize=10)
    ax.set_xlim(0, x_max * 1.06)
    ax.set_ylim(-0.9, len(factions) - 0.1)
    ax.set_xlabel(f"Number of players ({grand_total} total)", fontsize=10)
    ax.set_title(
        f"{event_name} — Disposition split by faction",
        fontsize=14,
        fontweight="bold",
        pad=16,
    )
    ax.grid(axis="x", color="#EEEEEE", zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)

    ax.legend(
        handles=[
            Patch(facecolor=COLORS[d], edgecolor="white", label=d)
            for d in DISPOSITIONS
        ],
        loc="lower right",
        fontsize=10,
        frameon=True,
        edgecolor="#CCCCCC",
    )

    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def write_csv(counts, out_csv):
    factions = sorted(counts, key=lambda f: (-sum(counts[f].values()), f))
    with open(out_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Faction", *DISPOSITIONS, "Total"])
        for faction in factions:
            row = [counts[faction][d] for d in DISPOSITIONS]
            writer.writerow([faction, *row, sum(row)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event_id", help="BCP event id, e.g. ChZP41nemm16")
    parser.add_argument(
        "-o",
        "--outdir",
        default="build",
        help="where to write the PNG and CSV (default: build/)",
    )
    args = parser.parse_args()

    event = fetch_event(args.event_id)
    event_name = event.get("name") or args.event_id
    players = fetch_players(args.event_id)
    counts, skipped = tally(players)
    if not counts:
        sys.exit(f"No player has a Force Disposition recorded for {event_name}.")

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = outdir / f"{args.event_id}_disposition_by_faction"
    draw(counts, event_name, stem.with_suffix(".png"))
    write_csv(counts, stem.with_suffix(".csv"))

    charted = sum(sum(c.values()) for c in counts.values())
    print(f"{event_name}: {charted} of {len(players)} players charted", end="")
    print(f" ({skipped} without a faction or disposition)" if skipped else "")
    print(f"  {stem.with_suffix('.png')}")
    print(f"  {stem.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
