"""BingoService and pure completion-logic helpers."""

from __future__ import annotations

import io
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import discord
from loguru import logger

from bingo.models import SubmissionStatus, TeamBoard, TileState, TileStatus, TileSubmission
from bingo.repository import BingoRepository
from bingo.tile_defs import CompletionPath, TileDefinition, get_tile_def
from core.service_base import Service

if TYPE_CHECKING:
    from events.models import Team
    from events.service import EventService
    from core.discord_client import DiscordClient


# ------------------------------------------------------------------
# Standalone helpers (importable for testing)
# ------------------------------------------------------------------


def check_path_satisfied(
    path: CompletionPath, approved_subs: list[TileSubmission]
) -> bool:
    """Return True if all requirements of *path* are met by *approved_subs*."""
    item_counts: Counter[str] = Counter(
        s.item_label for s in approved_subs if s.item_label
    )
    # Named item requirements
    if any(item_counts[k] < v for k, v in path.requirements.items()):
        return False
    # Pool count requirement
    if path.required_total > 0:
        pool = [
            s for s in approved_subs
            if not path.eligible_items or s.item_label in path.eligible_items
        ]
        count = (
            len({s.item_label for s in pool})
            if path.unique_labels
            else len(pool)
        )
        if count < path.required_total:
            return False
    return True


def path_progress(
    path: CompletionPath, approved_subs: list[TileSubmission]
) -> tuple[int, int]:
    """Return ``(items_done, items_total)`` for progress display.

    For named requirements, returns the sum of min(actual, needed) vs sum of
    needed.  For pool requirements, returns the capped pool count vs
    required_total.  For paths with no requirements, returns (1, 1).
    """
    if path.requirements:
        item_counts: Counter[str] = Counter(
            s.item_label for s in approved_subs if s.item_label
        )
        done = sum(min(item_counts[k], v) for k, v in path.requirements.items())
        total = sum(path.requirements.values())
        return done, total

    if path.required_total > 0:
        pool = [
            s for s in approved_subs
            if not path.eligible_items or s.item_label in path.eligible_items
        ]
        count = (
            len({s.item_label for s in pool})
            if path.unique_labels
            else len(pool)
        )
        return min(count, path.required_total), path.required_total

    # No requirements — trivially satisfied
    return 1, 1


def check_tile_complete(
    tile_def: TileDefinition,
    approved_subs: list[TileSubmission],
    team_member_ids: list[int],
) -> bool:
    """Return True if *tile_def* is complete given the approved submissions.

    For team-wide tiles every member must have at least one approved sub.
    For all other tiles, any single completion path being satisfied is enough.
    """
    if tile_def.is_team_wide:
        submitters = {s.submitted_by for s in approved_subs}
        return all(mid in submitters for mid in team_member_ids)

    for path in tile_def.completion_paths:
        if check_path_satisfied(path, approved_subs):
            return True
    return False


# ------------------------------------------------------------------
# Embed factories
# ------------------------------------------------------------------


def _make_board_embed(
    team: "Team", board: TeamBoard, img_bytes: bytes, filename: str
) -> tuple[discord.Embed, discord.File]:
    complete = sum(1 for s in board.tile_states.values() if s.status == TileStatus.COMPLETE)
    planned = sum(1 for s in board.tile_states.values() if s.status == TileStatus.PLANNED)
    in_review = sum(1 for s in board.tile_states.values() if s.status == TileStatus.IN_REVIEW)
    embed = discord.Embed(title=f"{team.name} — Bingo Board", color=discord.Color.blue())
    embed.set_image(url=f"attachment://{filename}")
    embed.set_footer(
        text=f"■ {complete}/49 complete  ○ {in_review} in review  P {planned} planned"
    )
    return embed, discord.File(io.BytesIO(img_bytes), filename=filename)


def _make_completed_embed(
    team: "Team", board: TeamBoard, img_bytes: bytes, filename: str
) -> tuple[discord.Embed, discord.File]:
    complete = sum(1 for s in board.tile_states.values() if s.status == TileStatus.COMPLETE)
    embed = discord.Embed(title=f"{team.name} — Completed Tiles", color=discord.Color.green())
    embed.set_image(url=f"attachment://{filename}")
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    embed.set_footer(text=f"{complete}/49 tiles complete  •  Updated {ts}")
    return embed, discord.File(io.BytesIO(img_bytes), filename=filename)


# ------------------------------------------------------------------
# BingoService
# ------------------------------------------------------------------


class BingoService(Service):
    """Manages bingo board state, submissions, and completion logic."""

    def __init__(
        self,
        guild: discord.Guild,
        repo: BingoRepository,
        event_service: EventService,
        client: DiscordClient,
    ) -> None:
        self._guild = guild
        self._repo = repo
        self._event_service = event_service
        self._client = client
        # team_id → cached TeamBoard
        self._boards: dict[int, TeamBoard] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        await self._repo.ensure_indexes()
        logger.info("BingoService initialised")

    async def post_ready(self) -> None:
        """Cache all team boards after event service has loaded teams."""
        for team in self._event_service.get_all_teams():
            board = await self._repo.get_or_create_board(self._guild.id, team.team_id)
            self._boards[team.team_id] = board
        logger.info(f"BingoService post_ready: {len(self._boards)} boards cached")
        # Stub: future re-attachment of pending review views goes here

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    async def submit(
        self,
        team_id: int,
        tile_key: str,
        submitted_by: int,
        screenshot_url: str,
        item_label: str | None,
        notes: str | None,
    ) -> TileSubmission:
        """Create a new pending submission and advance the tile to IN_REVIEW."""
        sub = TileSubmission(
            guild_id=self._guild.id,
            team_id=team_id,
            tile_key=tile_key,
            submitted_by=submitted_by,
            screenshot_url=screenshot_url,
            item_label=item_label,
            notes=notes,
        )
        await self._repo.save_submission(sub)

        board = await self._get_board(team_id)
        tile_state = board.tile_states.get(tile_key, TileState(tile_key=tile_key))
        if tile_state.status == TileStatus.INCOMPLETE:
            tile_state.status = TileStatus.IN_REVIEW
            await self._repo.update_tile_state(
                self._guild.id, team_id, tile_key, tile_state
            )
            board.tile_states[tile_key] = tile_state

        logger.info(
            f"Submission {sub.submission_id} created for tile {tile_key}"
            f" by user {submitted_by} (team {team_id})"
        )
        return sub

    async def approve(
        self, submission_id: str, reviewed_by: int
    ) -> tuple[TileSubmission, bool]:
        """Approve a submission and check whether its tile is now complete.

        Returns:
            A tuple of (updated submission, tile_now_complete).
        """
        sub = await self._repo.get_submission(submission_id)
        if sub is None:
            raise ValueError(f"Submission {submission_id!r} not found")

        sub.status = SubmissionStatus.APPROVED
        sub.reviewed_by = reviewed_by
        sub.reviewed_at = datetime.now(UTC)
        await self._repo.update_submission(sub)

        tile_def = get_tile_def(sub.tile_key)
        if tile_def is None:
            logger.warning(
                f"Unknown tile key {sub.tile_key!r} on submission {submission_id}"
                " — skipping completion check"
            )
            return sub, False

        approved = await self._repo.get_approved_submissions(
            sub.guild_id, sub.team_id, sub.tile_key
        )
        member_ids = self._get_member_ids(sub.team_id)
        now_complete = check_tile_complete(tile_def, approved, member_ids)

        board = await self._get_board(sub.team_id)
        tile_state = board.tile_states.get(sub.tile_key, TileState(tile_key=sub.tile_key))
        if now_complete and tile_state.status != TileStatus.COMPLETE:
            tile_state.status = TileStatus.COMPLETE
            tile_state.completed_at = datetime.now(UTC)
            tile_state.approved_by = reviewed_by
            await self._repo.update_tile_state(
                sub.guild_id, sub.team_id, sub.tile_key, tile_state
            )
            board.tile_states[sub.tile_key] = tile_state
            logger.info(f"Tile {sub.tile_key} completed for team {sub.team_id}")

        await self._update_board_panel(sub.team_id)
        if now_complete:
            await self._update_completed_panel(sub.team_id)

        return sub, now_complete

    async def reject(
        self, submission_id: str, reviewed_by: int, reason: str
    ) -> TileSubmission:
        """Reject a submission with a reason."""
        sub = await self._repo.get_submission(submission_id)
        if sub is None:
            raise ValueError(f"Submission {submission_id!r} not found")

        sub.status = SubmissionStatus.REJECTED
        sub.reviewed_by = reviewed_by
        sub.reviewed_at = datetime.now(UTC)
        sub.rejection_reason = reason
        await self._repo.update_submission(sub)

        logger.info(f"Submission {submission_id} rejected by {reviewed_by}: {reason!r}")
        return sub

    async def get_board(self, team_id: int) -> TeamBoard:
        """Return the cached (or freshly loaded) board for a team."""
        return await self._get_board(team_id)

    def get_tile_progress(
        self,
        tile_def: TileDefinition,
        approved_subs: list[TileSubmission],
    ) -> dict[str, tuple[int, int]]:
        """Return per-path progress as {path_label: (done, total)}."""
        return {
            path.label: path_progress(path, approved_subs)
            for path in tile_def.completion_paths
        }

    def get_team_for_member(self, user_id: int) -> Team | None:
        """Return the Team containing *user_id*, or None."""
        for team in self._event_service.get_all_teams():
            if any(m.discord_user_id == user_id for m in team.members):
                return team
        return None

    def is_host(self, member: discord.Member) -> bool:
        """Delegate host check to the event service."""
        return self._event_service.is_host(member)

    async def get_pending_submissions(
        self, team_id: int | None = None
    ) -> list[TileSubmission]:
        """Return all pending submissions for this guild, optionally filtered by team."""
        return await self._repo.get_all_pending(self._guild.id, team_id)

    def is_captain(self, user_id: int) -> bool:
        """Return True if user_id is a captain of their team."""
        team = self.get_team_for_member(user_id)
        if team is None:
            return False
        return any(m.discord_user_id == user_id and m.is_captain for m in team.members)

    async def plan_tile(self, team_id: int, tile_key: str) -> TileState:
        """Mark a tile PLANNED (only from INCOMPLETE). Triggers panel update."""
        board = await self._get_board(team_id)
        state = board.tile_states.get(tile_key, TileState(tile_key=tile_key))
        if state.status != TileStatus.INCOMPLETE:
            raise ValueError(f"Tile {tile_key!r} is already {state.status.value}")
        state.status = TileStatus.PLANNED
        await self._repo.update_tile_state(self._guild.id, team_id, tile_key, state)
        board.tile_states[tile_key] = state
        await self._update_board_panel(team_id)
        return state

    async def unplan_tile(self, team_id: int, tile_key: str) -> TileState:
        """Revert a PLANNED tile to INCOMPLETE. Triggers panel update."""
        board = await self._get_board(team_id)
        state = board.tile_states.get(tile_key, TileState(tile_key=tile_key))
        if state.status != TileStatus.PLANNED:
            raise ValueError(
                f"Tile {tile_key!r} is not planned (status: {state.status.value})"
            )
        state.status = TileStatus.INCOMPLETE
        await self._repo.update_tile_state(self._guild.id, team_id, tile_key, state)
        board.tile_states[tile_key] = state
        await self._update_board_panel(team_id)
        return state

    async def release_boards(self) -> list[str]:
        """Post full board panels to each team's board_channel_id. Returns log lines."""
        from bingo.board_renderer import render_board

        results: list[str] = []
        for team in self._event_service.get_all_teams():
            if not team.board_channel_id:
                results.append(f"Team {team.name}: no board_channel_id — skipped")
                continue
            channel = self._guild.get_channel(team.board_channel_id)
            if channel is None:
                results.append(f"Team {team.name}: channel not found — skipped")
                continue
            board = await self._get_board(team.team_id)
            img_bytes = render_board(board)
            embed, file = _make_board_embed(team, board, img_bytes, "board.png")
            msg = await channel.send(embed=embed, file=file)  # type: ignore[union-attr]
            board.board_panel_message_id = msg.id
            await self._repo.update_panel_ids(
                self._guild.id, team.team_id, board_panel_message_id=msg.id
            )
            results.append(f"Team {team.name}: board posted (msg {msg.id})")
        return results

    async def post_completed_panels(self, channel_id: int) -> list[str]:
        """Post completed-only panels for all teams to the specified channel."""
        from bingo.board_renderer import render_completed_board

        channel = self._guild.get_channel(channel_id)
        if channel is None:
            raise ValueError(f"Channel {channel_id} not found")
        results: list[str] = []
        for team in self._event_service.get_all_teams():
            board = await self._get_board(team.team_id)
            img_bytes = render_completed_board(board)
            embed, file = _make_completed_embed(team, board, img_bytes, "completed.png")
            msg = await channel.send(embed=embed, file=file)  # type: ignore[union-attr]
            board.completed_panel_channel_id = channel_id
            board.completed_panel_message_id = msg.id
            await self._repo.update_panel_ids(
                self._guild.id,
                team.team_id,
                completed_panel_channel_id=channel_id,
                completed_panel_message_id=msg.id,
            )
            results.append(f"Team {team.name}: posted (msg {msg.id})")
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_board(self, team_id: int) -> TeamBoard:
        if team_id not in self._boards:
            board = await self._repo.get_or_create_board(self._guild.id, team_id)
            self._boards[team_id] = board
        return self._boards[team_id]

    def _get_member_ids(self, team_id: int) -> list[int]:
        for team in self._event_service.get_all_teams():
            if team.team_id == team_id:
                return [m.discord_user_id for m in team.members]
        return []

    def _get_team(self, team_id: int) -> "Team | None":
        for team in self._event_service.get_all_teams():
            if team.team_id == team_id:
                return team
        return None

    async def _update_board_panel(self, team_id: int) -> None:
        from bingo.board_renderer import render_board

        board = await self._get_board(team_id)
        if not board.board_panel_message_id:
            return
        team = self._get_team(team_id)
        if team is None or not team.board_channel_id:
            return
        channel = self._guild.get_channel(team.board_channel_id)
        if channel is None:
            return
        try:
            msg = await channel.fetch_message(board.board_panel_message_id)  # type: ignore[union-attr]
            img_bytes = render_board(board)
            embed, file = _make_board_embed(team, board, img_bytes, "board.png")
            await msg.edit(embed=embed, attachments=[file])
        except discord.NotFound:
            board.board_panel_message_id = None
            await self._repo.update_panel_ids(
                self._guild.id, team_id, board_panel_message_id=None
            )

    async def _update_completed_panel(self, team_id: int) -> None:
        from bingo.board_renderer import render_completed_board

        board = await self._get_board(team_id)
        if not board.completed_panel_message_id or not board.completed_panel_channel_id:
            return
        channel = self._guild.get_channel(board.completed_panel_channel_id)
        if channel is None:
            return
        team = self._get_team(team_id)
        if team is None:
            return
        try:
            msg = await channel.fetch_message(board.completed_panel_message_id)  # type: ignore[union-attr]
            img_bytes = render_completed_board(board)
            embed, file = _make_completed_embed(team, board, img_bytes, "completed.png")
            await msg.edit(embed=embed, attachments=[file])
        except discord.NotFound:
            board.completed_panel_message_id = None
            board.completed_panel_channel_id = None
            await self._repo.update_panel_ids(
                self._guild.id,
                team_id,
                completed_panel_channel_id=None,
                completed_panel_message_id=None,
            )
