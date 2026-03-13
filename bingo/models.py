from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class TileStatus(str, Enum):
    INCOMPLETE = "incomplete"
    IN_REVIEW = "in_review"
    COMPLETE = "complete"


class SubmissionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TileSubmission(BaseModel):
    submission_id: str = Field(default_factory=lambda: str(uuid4()))
    guild_id: int
    team_id: int
    tile_key: str
    submitted_by: int
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    screenshot_url: str
    item_label: str | None = None
    notes: str | None = None
    status: SubmissionStatus = SubmissionStatus.PENDING
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    # For future Discord view re-attachment
    review_channel_id: int | None = None
    review_message_id: int | None = None


class TileState(BaseModel):
    tile_key: str
    status: TileStatus = TileStatus.INCOMPLETE
    review_thread_id: int | None = None
    completed_at: datetime | None = None
    approved_by: int | None = None


class TeamBoard(BaseModel):
    guild_id: int
    team_id: int
    tile_states: dict[str, TileState] = Field(default_factory=dict)
