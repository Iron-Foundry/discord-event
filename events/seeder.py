from __future__ import annotations

import json
from pathlib import Path

from events.models import Team, TeamMember


def load_teams_from_json(guild_id: int) -> list[Team]:
    """Parse exported-signups1.json and return one Team per team_id."""
    path = Path(__file__).parent.parent / "exported-signups1.json"
    signups: list[dict] = json.loads(path.read_text())
    groups: dict[int, list[TeamMember]] = {}
    for s in signups:
        groups.setdefault(s["team_id"], []).append(TeamMember.from_signup(s))
    return [
        Team(guild_id=guild_id, team_id=tid, name=f"Team {tid}", members=members)
        for tid, members in sorted(groups.items())
    ]
