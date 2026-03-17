from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient, IndexModel

from bingo.models import SubmissionStatus, TeamBoard, TileState, TileSubmission

_UNSET = object()


class BingoRepository:
    """MongoDB-backed persistence for the bingo service."""

    def __init__(self, mongo_uri: str, db_name: str) -> None:
        self._client: AsyncMongoClient = AsyncMongoClient(mongo_uri)
        self._db = self._client[db_name]
        self._boards = self._db["bingo_boards"]
        self._submissions = self._db["bingo_submissions"]

    # ------------------------------------------------------------------
    # Boards
    # ------------------------------------------------------------------

    async def get_or_create_board(self, guild_id: int, team_id: int) -> TeamBoard:
        doc = await self._boards.find_one(
            {"guild_id": guild_id, "team_id": team_id}, {"_id": 0}
        )
        if doc:
            return TeamBoard(**doc)
        board = TeamBoard(guild_id=guild_id, team_id=team_id)
        await self._boards.insert_one(board.model_dump())
        return board

    async def update_panel_ids(
        self,
        guild_id: int,
        team_id: int,
        *,
        board_panel_message_id: int | None = _UNSET,  # type: ignore[assignment]
        completed_panel_channel_id: int | None = _UNSET,  # type: ignore[assignment]
        completed_panel_message_id: int | None = _UNSET,  # type: ignore[assignment]
    ) -> None:
        """Persist panel message IDs onto the TeamBoard document."""
        fields: dict = {}
        if board_panel_message_id is not _UNSET:
            fields["board_panel_message_id"] = board_panel_message_id
        if completed_panel_channel_id is not _UNSET:
            fields["completed_panel_channel_id"] = completed_panel_channel_id
        if completed_panel_message_id is not _UNSET:
            fields["completed_panel_message_id"] = completed_panel_message_id
        if fields:
            await self._boards.update_one(
                {"guild_id": guild_id, "team_id": team_id},
                {"$set": fields},
                upsert=True,
            )

    async def update_tile_state(
        self, guild_id: int, team_id: int, tile_key: str, state: TileState
    ) -> None:
        await self._boards.update_one(
            {"guild_id": guild_id, "team_id": team_id},
            {"$set": {f"tile_states.{tile_key}": state.model_dump()}},
            upsert=True,
        )

    # ------------------------------------------------------------------
    # Submissions
    # ------------------------------------------------------------------

    async def save_submission(self, sub: TileSubmission) -> None:
        await self._submissions.insert_one(sub.model_dump())

    async def update_submission(self, sub: TileSubmission) -> None:
        await self._submissions.update_one(
            {"submission_id": sub.submission_id},
            {"$set": sub.model_dump()},
        )

    async def get_submission(self, submission_id: str) -> TileSubmission | None:
        doc = await self._submissions.find_one(
            {"submission_id": submission_id}, {"_id": 0}
        )
        if not doc:
            return None
        return TileSubmission(**doc)

    async def get_approved_submissions(
        self, guild_id: int, team_id: int, tile_key: str
    ) -> list[TileSubmission]:
        cursor = self._submissions.find(
            {
                "guild_id": guild_id,
                "team_id": team_id,
                "tile_key": tile_key,
                "status": SubmissionStatus.APPROVED.value,
            },
            {"_id": 0},
        )
        return [TileSubmission(**doc) async for doc in cursor]

    async def get_all_pending(
        self, guild_id: int, team_id: int | None = None
    ) -> list[TileSubmission]:
        """Return all PENDING submissions for a guild (optionally filtered by team)."""
        query: dict = {"guild_id": guild_id, "status": SubmissionStatus.PENDING.value}
        if team_id is not None:
            query["team_id"] = team_id
        cursor = self._submissions.find(query, {"_id": 0})
        return [TileSubmission(**doc) async for doc in cursor]

    async def get_all_approved(
        self, guild_id: int, team_id: int | None = None
    ) -> list[TileSubmission]:
        """Return all APPROVED submissions for a guild (optionally filtered by team)."""
        query: dict = {"guild_id": guild_id, "status": SubmissionStatus.APPROVED.value}
        if team_id is not None:
            query["team_id"] = team_id
        cursor = self._submissions.find(query, {"_id": 0})
        return [TileSubmission(**doc) async for doc in cursor]

    async def get_all_rejected(
        self, guild_id: int, team_id: int | None = None
    ) -> list[TileSubmission]:
        """Return all REJECTED submissions for a guild (optionally filtered by team)."""
        query: dict = {"guild_id": guild_id, "status": SubmissionStatus.REJECTED.value}
        if team_id is not None:
            query["team_id"] = team_id
        cursor = self._submissions.find(query, {"_id": 0})
        return [TileSubmission(**doc) async for doc in cursor]

    async def get_all_active(self, guild_id: int) -> list[TileSubmission]:
        """Return all PENDING and APPROVED submissions for a guild."""
        cursor = self._submissions.find(
            {
                "guild_id": guild_id,
                "status": {
                    "$in": [
                        SubmissionStatus.PENDING.value,
                        SubmissionStatus.APPROVED.value,
                    ]
                },
            },
            {"_id": 0},
        )
        return [TileSubmission(**doc) async for doc in cursor]

    async def get_all_submissions(
        self, guild_id: int, team_id: int | None = None
    ) -> list[TileSubmission]:
        """All submissions (all statuses) for the guild, optionally filtered by team."""
        query: dict = {"guild_id": guild_id}
        if team_id is not None:
            query["team_id"] = team_id
        cursor = self._submissions.find(query, {"_id": 0})
        return [TileSubmission(**doc) async for doc in cursor]

    async def get_all_boards(
        self, guild_id: int, team_id: int | None = None
    ) -> list[TeamBoard]:
        """All team boards for the guild, optionally filtered to one team."""
        query: dict = {"guild_id": guild_id}
        if team_id is not None:
            query["team_id"] = team_id
        cursor = self._boards.find(query, {"_id": 0})
        return [TeamBoard(**doc) async for doc in cursor]

    async def get_recent_submissions(
        self, guild_id: int, team_id: int, limit: int = 10
    ) -> list[TileSubmission]:
        """Return the most recent submissions for a team, newest first."""
        cursor = (
            self._submissions.find(
                {"guild_id": guild_id, "team_id": team_id},
                {"_id": 0},
            )
            .sort("submitted_at", DESCENDING)
            .limit(limit)
        )
        return [TileSubmission(**doc) async for doc in cursor]

    async def get_pending_for_reattach(self, guild_id: int) -> list[TileSubmission]:
        """Return pending submissions that have a review_message_id set (for view re-attachment)."""
        cursor = self._submissions.find(
            {
                "guild_id": guild_id,
                "status": SubmissionStatus.PENDING.value,
                "review_message_id": {"$ne": None},
            },
            {"_id": 0},
        )
        return [TileSubmission(**doc) async for doc in cursor]

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------

    async def ensure_indexes(self) -> None:
        await self._boards.create_indexes(
            [IndexModel([("guild_id", ASCENDING), ("team_id", ASCENDING)], unique=True)]
        )
        await self._submissions.create_indexes(
            [
                IndexModel([("submission_id", ASCENDING)], unique=True),
                IndexModel(
                    [
                        ("guild_id", ASCENDING),
                        ("team_id", ASCENDING),
                        ("tile_key", ASCENDING),
                        ("status", ASCENDING),
                    ]
                ),
            ]
        )
