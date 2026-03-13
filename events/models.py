from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class EventConfig(BaseModel):
    """Guild-level event settings stored in bingo_event_config."""

    guild_id: int
    event_name: str = "Bingo Event"
    event_active: bool = False
    category_id: int | None = None
    general_channel_id: int | None = None
    staff_channel_id: int | None = None
    host_user_ids: list[int] = Field(default_factory=list)
    host_role_id: int | None = None
    submission_channel_id: int | None = None


class TeamMember(BaseModel):
    """A member of a bingo team."""

    discord_user_id: int
    rsn: str
    is_captain: bool = False

    @classmethod
    def from_signup(cls, data: dict[str, Any]) -> "TeamMember":
        """Create a TeamMember from a raw signup dict."""
        return cls(discord_user_id=int(data["discord_user"]), rsn=data["rsn"])


class Team(BaseModel):
    """A bingo team stored in bingo_teams."""

    guild_id: int
    team_id: int
    name: str
    members: list[TeamMember] = Field(default_factory=list)
    role_id: int | None = None
    general_channel_id: int | None = None
    forum_channel_id: int | None = None
    board_channel_id: int | None = None
    voice_channel_id: int | None = None


class HostAccessGrant(BaseModel):
    """A temporary host access grant stored in bingo_host_access."""

    guild_id: int
    channel_id: int
    host_user_id: int
    granted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
