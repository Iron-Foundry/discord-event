from __future__ import annotations

from pymongo import AsyncMongoClient, IndexModel, ASCENDING

from events.models import EventConfig, HostAccessGrant, Team


class MongoEventRepository:
    """MongoDB-backed persistence for the event service."""

    def __init__(self, mongo_uri: str, db_name: str) -> None:
        self._client: AsyncMongoClient = AsyncMongoClient(mongo_uri)
        self._db = self._client[db_name]
        self._config_col = self._db["bingo_event_config"]
        self._teams_col = self._db["bingo_teams"]
        self._grants_col = self._db["bingo_host_access"]

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    async def get_config(self, guild_id: int) -> EventConfig | None:
        """Return the event config for the given guild, or None if not set."""
        doc = await self._config_col.find_one({"guild_id": guild_id}, {"_id": 0})
        if not doc:
            return None
        return EventConfig(**doc)

    async def save_config(self, config: EventConfig) -> None:
        """Upsert the event config for the given guild."""
        await self._config_col.update_one(
            {"guild_id": config.guild_id},
            {"$set": config.model_dump()},
            upsert=True,
        )

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    async def upsert_team(self, team: Team) -> None:
        """Upsert a team document by guild_id + team_id."""
        await self._teams_col.update_one(
            {"guild_id": team.guild_id, "team_id": team.team_id},
            {"$set": team.model_dump()},
            upsert=True,
        )

    async def get_team(self, guild_id: int, team_id: int) -> Team | None:
        """Return a team by its compound key, or None."""
        doc = await self._teams_col.find_one(
            {"guild_id": guild_id, "team_id": team_id}, {"_id": 0}
        )
        if not doc:
            return None
        return Team(**doc)

    async def get_all_teams(self, guild_id: int) -> list[Team]:
        """Return all teams for the given guild, sorted by team_id."""
        cursor = self._teams_col.find({"guild_id": guild_id}, {"_id": 0}).sort(
            "team_id", ASCENDING
        )
        return [Team(**doc) async for doc in cursor]

    async def update_team_channels(
        self,
        guild_id: int,
        team_id: int,
        general_id: int,
        forum_id: int,
        board_id: int,
        voice_id: int,
    ) -> None:
        """Persist channel snowflakes for a team."""
        await self._teams_col.update_one(
            {"guild_id": guild_id, "team_id": team_id},
            {
                "$set": {
                    "general_channel_id": general_id,
                    "forum_channel_id": forum_id,
                    "board_channel_id": board_id,
                    "voice_channel_id": voice_id,
                }
            },
        )

    # ------------------------------------------------------------------
    # Host access grants
    # ------------------------------------------------------------------

    async def save_host_grant(self, grant: HostAccessGrant) -> None:
        """Upsert a host access grant."""
        await self._grants_col.update_one(
            {"channel_id": grant.channel_id, "host_user_id": grant.host_user_id},
            {"$set": grant.model_dump()},
            upsert=True,
        )

    async def delete_host_grant(
        self, guild_id: int, channel_id: int, host_user_id: int
    ) -> None:
        """Delete a specific host access grant."""
        await self._grants_col.delete_one(
            {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "host_user_id": host_user_id,
            }
        )

    async def get_active_grants(self, guild_id: int) -> list[HostAccessGrant]:
        """Return all active host access grants for the given guild."""
        cursor = self._grants_col.find({"guild_id": guild_id}, {"_id": 0})
        return [HostAccessGrant(**doc) async for doc in cursor]

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------

    async def ensure_indexes(self) -> None:
        """Create necessary MongoDB indexes."""
        await self._config_col.create_index("guild_id", unique=True)
        await self._teams_col.create_indexes(
            [IndexModel([("guild_id", ASCENDING), ("team_id", ASCENDING)], unique=True)]
        )
        await self._grants_col.create_indexes(
            [
                IndexModel(
                    [("channel_id", ASCENDING), ("host_user_id", ASCENDING)],
                    unique=True,
                ),
                IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0),
            ]
        )
