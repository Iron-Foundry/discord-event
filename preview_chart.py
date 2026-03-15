"""Local chart preview tool — no bot, no Discord, no MongoDB required.

Usage:
    uv run preview_chart.py                      # ecdf (default)
    uv run preview_chart.py --chart bar_grouped_h
    uv run preview_chart.py --chart pie
    uv run preview_chart.py --chart scatter
    uv run preview_chart.py --players 20         # fewer players for quick tests
    uv run preview_chart.py --out /tmp/my.png    # custom output path
    uv run preview_chart.py --no-open            # skip auto-open

Available chart types:
    ecdf, bar_grouped_h, bar_stacked_h, bar_grouped_v, bar_stacked_v,
    pie, scatter, treemap, sunburst
"""

from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

def _make_submissions(n_players: int, seed: int = 42):
    """Return a list of TileSubmission-like objects with realistic variance."""
    # Import here so the script is runnable from the project root with uv run.
    from bingo.models import SubmissionStatus, TileSubmission  # noqa: PLC0415

    rng = random.Random(seed)
    event_start = datetime(2025, 1, 1, 10, 0, 0)
    event_end = datetime(2025, 3, 15, 23, 59, 59)
    event_span = (event_end - event_start).total_seconds()

    tile_keys = [f"tile_{i:02d}" for i in range(1, 31)]
    items = [
        "Abyssal whip", "Dragon bones", "Rune platebody", "Bandos chestplate",
        "Armadyl helmet", "Barrows gloves", "Fire cape", "Torva platelegs",
        "Zenyte shard", "Twisted bow", "Scythe of vitur", "Tumeken's shadow",
    ]

    # Distribute players across teams with 6-10 players each
    teams: list[int] = []
    team_id = 1
    assigned = 0
    while assigned < n_players:
        size = rng.randint(6, 10)
        teams.extend([team_id] * min(size, n_players - assigned))
        assigned += size
        team_id += 1

    # Each player gets a "skill level" that biases their approval rate and volume
    subs: list[TileSubmission] = []
    for player_id in range(1, n_players + 1):
        player_team = teams[player_id - 1]
        skill = rng.gauss(0.72, 0.15)          # approval rate ~ N(0.72, 0.15)
        skill = max(0.2, min(0.98, skill))
        n_subs = int(rng.gauss(28, 14))         # submissions ~ N(28, 14)
        n_subs = max(1, n_subs)

        # Active window: players join at different times and may go quiet early
        join_offset = rng.uniform(0, event_span * 0.3)
        active_until = rng.uniform(0.6, 1.0) * event_span

        for _ in range(n_subs):
            offset = rng.uniform(join_offset, active_until)
            submitted_at = event_start + timedelta(seconds=offset)

            status = (
                SubmissionStatus.APPROVED
                if rng.random() < skill
                else SubmissionStatus.REJECTED
                if rng.random() < 0.7   # remainder split rejected / pending
                else SubmissionStatus.PENDING
            )

            subs.append(TileSubmission(
                guild_id=1,
                team_id=player_team,
                tile_key=rng.choice(tile_keys),
                submitted_by=player_id,
                submitted_at=submitted_at,
                screenshot_url="https://example.com/fake.png",
                item_label=rng.choice(items),
                status=status,
            ))

    return subs


def _make_player_names(n_players: int) -> dict[int, str]:
    prefixes = [
        "Iron", "Zulrah", "Void", "Infernal", "Twisted", "Toxic", "Dragon",
        "Shadow", "Armadyl", "Bandos", "Barrows", "Ancient", "Lunar", "Mystic",
    ]
    suffixes = [
        "Slayer", "Ranger", "Mage", "Tank", "Striker", "Hunter", "Skiller",
        "Raider", "Bossing", "PKer", "Ironman", "UIM", "HCIM", "GIM",
    ]
    rng = random.Random(0)
    names: dict[int, str] = {}
    used: set[str] = set()
    for pid in range(1, n_players + 1):
        while True:
            name = f"{rng.choice(prefixes)}{rng.choice(suffixes)}{rng.randint(1, 999)}"
            if name not in used:
                used.add(name)
                names[pid] = name
                break
    return names


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Preview bingo stats charts locally.")
    parser.add_argument(
        "--chart",
        default="ecdf",
        metavar="TYPE",
        help="Chart type (default: ecdf)",
    )
    parser.add_argument(
        "--players",
        type=int,
        default=96,
        metavar="N",
        help="Number of synthetic players (default: 96)",
    )
    parser.add_argument(
        "--out",
        metavar="PATH",
        help="Write PNG to this path instead of a temp file",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not auto-open the image after rendering",
    )
    args = parser.parse_args()

    from bingo.stats_graphs import render_player_submissions_chart  # noqa: PLC0415

    print(f"Generating {args.players} players …")
    subs = _make_submissions(args.players)
    player_names = _make_player_names(args.players)

    print(f"Rendering chart_type={args.chart!r} …")
    pngs = render_player_submissions_chart(
        subs,
        player_names,
        title="Submissions by Player — All Teams",
        time_label="All time",
        chart_type=args.chart,
    )

    for idx, png in enumerate(pngs):
        if args.out:
            path = args.out if len(pngs) == 1 else f"{args.out}.{idx}.png"
        else:
            out_dir = os.path.join(os.path.dirname(__file__), "preview_output")
            os.makedirs(out_dir, exist_ok=True)
            suffix = f"_{idx}" if len(pngs) > 1 else ""
            path = os.path.join(out_dir, f"chart_{args.chart}{suffix}.png")

        with open(path, "wb") as f:
            f.write(png)

        print(f"  Saved → {path}")

        if not args.no_open:
            _open(path)


def _open(path: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    elif sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        # Linux: try common viewers in order
        for viewer in ("xdg-open", "eog", "feh", "display"):
            if subprocess.run(["which", viewer], capture_output=True).returncode == 0:
                subprocess.Popen([viewer, path])  # noqa: S603
                break


if __name__ == "__main__":
    main()
