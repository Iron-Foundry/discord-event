"""BingoService and pure completion-logic helpers."""

from __future__ import annotations

import io
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import discord
from loguru import logger

from bingo.models import (
    SubmissionStatus,
    TeamBoard,
    TileState,
    TileStatus,
    TileSubmission,
)
from bingo.repository import BingoRepository
from bingo.tile_defs import (
    TILE_DEFINITIONS,
    CompletionPath,
    TileDefinition,
    get_tile_def,
)
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
    # Named item requirements (all must be met)
    if any(item_counts[k] < v for k, v in path.requirements.items()):
        return False
    # Pool requirements (every pool must be met — AND semantics)
    for pool in path.pool_requirements:
        if pool.item_weights:
            # Value-weighted mode: sum of (count × weight) must reach required_value
            total_val = sum(
                item_counts[item] * w for item, w in pool.item_weights.items()
            )
            if total_val < pool.required_value:
                return False
        else:
            candidates = [
                s
                for s in approved_subs
                if not pool.eligible_items or s.item_label in pool.eligible_items
            ]
            count = (
                len({s.item_label for s in candidates})
                if pool.unique_labels
                else len(candidates)
            )
            if count < pool.required_total:
                return False
    return True


def path_progress(
    path: CompletionPath, approved_subs: list[TileSubmission]
) -> list[tuple[str, int, int]]:
    """Return per-constraint progress as a list of ``(label, done, total)``.

    One entry per named-requirements aggregate (if any) plus one entry per
    pool requirement.  For paths with no requirements, returns a single
    trivially-satisfied entry.
    """
    result: list[tuple[str, int, int]] = []
    item_counts: Counter[str] = Counter(
        s.item_label for s in approved_subs if s.item_label
    )

    # Named requirements as a single aggregate entry
    if path.requirements:
        done = sum(min(item_counts[k], v) for k, v in path.requirements.items())
        total = sum(path.requirements.values())
        result.append((path.label, done, total))

    # One entry per pool requirement
    for pool in path.pool_requirements:
        if pool.item_weights:
            # Value-weighted mode
            total_val = sum(
                item_counts[item] * w for item, w in pool.item_weights.items()
            )
            result.append(
                (pool.label, min(total_val, pool.required_value), pool.required_value)
            )
        else:
            candidates = [
                s
                for s in approved_subs
                if not pool.eligible_items or s.item_label in pool.eligible_items
            ]
            count = (
                len({s.item_label for s in candidates})
                if pool.unique_labels
                else len(candidates)
            )
            result.append(
                (pool.label, min(count, pool.required_total), pool.required_total)
            )

    # Path with no requirements (trivially satisfied)
    if not result:
        result.append((path.label, 1, 1))

    return result


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


def _compact_progress(
    tile_def: TileDefinition,
    approved: list[TileSubmission],
    team_member_count: int,
) -> str:
    """Return a brief done/total string for the best completion path."""
    if tile_def.is_team_wide:
        submitted = len({s.submitted_by for s in approved})
        return f"{submitted}/{team_member_count}"
    if not tile_def.completion_paths:
        return "—"
    best = max(
        (path_progress(path, approved) for path in tile_def.completion_paths),
        key=lambda c: sum(d for _, d, _ in c) / max(sum(t for _, _, t in c), 1),
    )
    done = sum(d for _, d, _ in best)
    total = sum(t for _, _, t in best)
    return f"{done}/{total}"


def _best_path_summary(
    tile_def: TileDefinition,
    approved_subs: list[TileSubmission],
) -> str:
    """Return a compact progress string for the path with the highest completion ratio."""
    if not tile_def.completion_paths:
        return "—"

    best_path: CompletionPath | None = None
    best_constraints: list[tuple[str, int, int]] = []
    best_ratio = -1.0

    for path in tile_def.completion_paths:
        constraints = path_progress(path, approved_subs)
        total_done = sum(done for _, done, _ in constraints)
        total_total = sum(total for _, _, total in constraints)
        ratio = total_done / total_total if total_total > 0 else 0.0
        if ratio > best_ratio:
            best_ratio = ratio
            best_path = path
            best_constraints = constraints

    if best_path is None:
        return "—"

    multi_path = len(tile_def.completion_paths) > 1

    item_counts: Counter[str] = Counter(
        s.item_label for s in approved_subs if s.item_label
    )
    parts: list[str] = []

    # Named requirements — one entry per item so missing items are visible
    for item_name, required in best_path.requirements.items():
        done = min(item_counts[item_name], required)
        parts.append(f"{item_name}: {done}/{required}")

    # Pool requirements — path_progress pools follow the named-requirements aggregate
    pool_constraint_idx = 1 if best_path.requirements else 0
    for pool in best_path.pool_requirements:
        if pool_constraint_idx >= len(best_constraints):
            break
        clabel, done, total = best_constraints[pool_constraint_idx]
        if pool.item_weights:
            parts.append(f"{clabel}: {done}/{total} pts")
        elif pool.eligible_items:
            items = pool.eligible_items[:3]
            suffix = ", ..." if len(pool.eligible_items) > 3 else ""
            items_str = ", ".join(items) + suffix
            parts.append(f"{clabel}: {done}/{total} ({items_str})")
        else:
            parts.append(f"{clabel}: {done}/{total}")
        pool_constraint_idx += 1

    # Trivially-satisfied path with no requirements (path_progress returns [(label,1,1)])
    if not parts and best_constraints:
        clabel, done, total = best_constraints[0]
        parts.append(f"{clabel}: {done}/{total}")

    summary = ", ".join(parts)
    if multi_path:
        return f"[{best_path.label}] {summary}"
    return summary


def _make_board_embed(
    team: "Team",
    board: TeamBoard,
    img_bytes: bytes,
    filename: str,
    in_progress_data: "list[tuple[str, TileDefinition, list[TileSubmission]]] | None" = None,
) -> tuple[discord.Embed, discord.File]:
    complete = sum(
        1 for s in board.tile_states.values() if s.status == TileStatus.COMPLETE
    )
    prioritized = sum(
        1 for s in board.tile_states.values() if s.status == TileStatus.PRIORITIZED
    )
    in_progress_count = sum(
        1 for s in board.tile_states.values() if s.status == TileStatus.IN_PROGRESS
    )
    embed = discord.Embed(
        title=f"{team.name} — Bingo Board", color=discord.Color.blue()
    )
    embed.set_image(url=f"attachment://{filename}")
    embed.set_footer(
        text=f"■ {complete}/49 complete  ○ {in_progress_count} in progress  P {prioritized} prioritized"
    )

    if in_progress_data:
        member_count = len(team.members)
        lines: list[str] = []
        for _, tile_def, approved in in_progress_data:
            tile_label = f"({tile_def.row},{tile_def.col}) {tile_def.description}"
            fraction = _compact_progress(tile_def, approved, member_count)
            lines.append(f"`{tile_label}` — {fraction}")

        if lines:
            embed.add_field(
                name="○ In Progress",
                value="\n".join(lines)[:1024],
                inline=False,
            )

    return embed, discord.File(io.BytesIO(img_bytes), filename=filename)


def _make_completed_embed(
    team: "Team", board: TeamBoard, img_bytes: bytes, filename: str
) -> tuple[discord.Embed, discord.File]:
    complete = sum(
        1 for s in board.tile_states.values() if s.status == TileStatus.COMPLETE
    )
    embed = discord.Embed(
        title=f"{team.name} — Completed Tiles", color=discord.Color.green()
    )
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

        from bingo.views import BoardProgressView, SubmissionReviewView

        for team_id, board in self._boards.items():
            if board.board_panel_message_id:
                self._client.add_view(BoardProgressView(self, team_id))

        pending = await self._repo.get_pending_for_reattach(self._guild.id)
        reattached = 0
        for sub in pending:
            if not sub.review_channel_id or not sub.review_message_id:
                continue
            channel = self._guild.get_channel(sub.review_channel_id)
            if channel is None:
                continue
            try:
                msg = await channel.fetch_message(sub.review_message_id)  # type: ignore[union-attr]
                await msg.edit(view=SubmissionReviewView(self, sub.submission_id))
                reattached += 1
            except discord.NotFound:
                pass
            except discord.HTTPException as e:
                logger.warning(
                    f"Could not re-attach view to submission {sub.submission_id}: {e}"
                )
        if reattached:
            logger.info(
                f"BingoService post_ready: re-attached {reattached} review views"
            )

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
        await self._post_submission_notification(sub)
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
        tile_state = board.tile_states.get(
            sub.tile_key, TileState(tile_key=sub.tile_key)
        )
        if now_complete and tile_state.status != TileStatus.COMPLETE:
            tile_state.status = TileStatus.COMPLETE
            tile_state.completed_at = datetime.now(UTC)
            tile_state.approved_by = reviewed_by
            await self._repo.update_tile_state(
                sub.guild_id, sub.team_id, sub.tile_key, tile_state
            )
            board.tile_states[sub.tile_key] = tile_state
            logger.info(f"Tile {sub.tile_key} completed for team {sub.team_id}")
        elif not now_complete and tile_state.status != TileStatus.IN_PROGRESS:
            # First approval that doesn't yet complete the tile — advance to IN_PROGRESS
            tile_state.status = TileStatus.IN_PROGRESS
            await self._repo.update_tile_state(
                sub.guild_id, sub.team_id, sub.tile_key, tile_state
            )
            board.tile_states[sub.tile_key] = tile_state

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
    ) -> dict[str, list[tuple[str, int, int]]]:
        """Return per-path progress as {path_label: [(constraint_label, done, total)]}."""
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

    async def rebuild_states(self, team_id: int | None = None) -> list[str]:
        """Recompute all tile states from approved submissions.

        Safe to run at any time — idempotent.  Use after tile-definition
        changes or any other event that may have left stored states stale.
        PRIORITIZED status is preserved on tiles that have no pending submissions
        and are not complete.
        """
        results: list[str] = []
        teams = self._event_service.get_all_teams()
        if team_id is not None:
            teams = [t for t in teams if t.team_id == team_id]

        for team in teams:
            board = await self._get_board(team.team_id)
            member_ids = self._get_member_ids(team.team_id)

            approved_subs = await self._repo.get_all_approved(
                self._guild.id, team.team_id
            )
            pending_subs = await self._repo.get_all_pending(
                self._guild.id, team.team_id
            )

            approved_by_tile: dict[str, list[TileSubmission]] = {}
            for sub in approved_subs:
                approved_by_tile.setdefault(sub.tile_key, []).append(sub)

            pending_by_tile: dict[str, list[TileSubmission]] = {}
            for sub in pending_subs:
                pending_by_tile.setdefault(sub.tile_key, []).append(sub)

            changed = 0
            for key, tile_def in TILE_DEFINITIONS.items():
                tile_approved = approved_by_tile.get(key, [])
                tile_pending = pending_by_tile.get(key, [])
                old_state = board.tile_states.get(key, TileState(tile_key=key))

                is_complete = check_tile_complete(tile_def, tile_approved, member_ids)

                if is_complete:
                    new_status = TileStatus.COMPLETE
                elif tile_approved:
                    new_status = TileStatus.IN_PROGRESS
                elif tile_pending:
                    new_status = TileStatus.IN_REVIEW
                elif old_state.status == TileStatus.PRIORITIZED:
                    new_status = TileStatus.PRIORITIZED  # preserve captain's prioritization
                else:
                    new_status = TileStatus.INCOMPLETE

                if old_state.status == new_status:
                    continue

                new_state = TileState(
                    tile_key=key,
                    status=new_status,
                    completed_at=(
                        old_state.completed_at or datetime.now(UTC)
                        if new_status == TileStatus.COMPLETE
                        else None
                    ),
                    approved_by=(
                        old_state.approved_by
                        if new_status == TileStatus.COMPLETE
                        else None
                    ),
                )
                await self._repo.update_tile_state(
                    self._guild.id, team.team_id, key, new_state
                )
                board.tile_states[key] = new_state
                changed += 1

            if changed:
                await self._update_board_panel(team.team_id)
                await self._update_completed_panel(team.team_id)

            results.append(f"Team {team.name}: {changed} tile(s) updated")

        return results

    async def edit_submission(
        self,
        submission_id: str,
        reviewed_by: int,
        new_item_label: str,
    ) -> tuple[TileSubmission, bool, bool]:
        """Edit the item_label of an approved submission and recheck tile completion.

        Returns ``(submission, tile_now_complete, tile_was_uncompleted)``.
        ``tile_was_uncompleted`` is True when the edit caused a previously-complete
        tile to fall back to IN_REVIEW.
        """
        sub = await self._repo.get_submission(submission_id)
        if sub is None:
            raise ValueError(f"Submission {submission_id!r} not found")
        if sub.status != SubmissionStatus.APPROVED:
            raise ValueError(f"Submission `{submission_id[:8]}` is not approved")

        sub.item_label = new_item_label
        await self._repo.update_submission(sub)

        tile_def = get_tile_def(sub.tile_key)
        if tile_def is None:
            return sub, False, False

        approved = await self._repo.get_approved_submissions(
            sub.guild_id, sub.team_id, sub.tile_key
        )
        member_ids = self._get_member_ids(sub.team_id)
        now_complete = check_tile_complete(tile_def, approved, member_ids)

        board = await self._get_board(sub.team_id)
        tile_state = board.tile_states.get(
            sub.tile_key, TileState(tile_key=sub.tile_key)
        )
        was_complete = tile_state.status == TileStatus.COMPLETE
        tile_uncompleted = False

        if now_complete and not was_complete:
            tile_state.status = TileStatus.COMPLETE
            tile_state.completed_at = datetime.now(UTC)
            tile_state.approved_by = reviewed_by
            await self._repo.update_tile_state(
                sub.guild_id, sub.team_id, sub.tile_key, tile_state
            )
            board.tile_states[sub.tile_key] = tile_state
        elif not now_complete and was_complete:
            # Edit removed a qualifying item — walk back the completion
            tile_state.status = TileStatus.IN_PROGRESS
            tile_state.completed_at = None
            tile_state.approved_by = None
            await self._repo.update_tile_state(
                sub.guild_id, sub.team_id, sub.tile_key, tile_state
            )
            board.tile_states[sub.tile_key] = tile_state
            tile_uncompleted = True

        await self._update_board_panel(sub.team_id)
        if now_complete or tile_uncompleted:
            await self._update_completed_panel(sub.team_id)

        logger.info(
            f"Submission {submission_id[:8]} item_label updated to {new_item_label!r}"
            f" by {reviewed_by} (tile {sub.tile_key}, team {sub.team_id})"
        )
        return sub, now_complete, tile_uncompleted

    async def prioritize_tile(self, team_id: int, tile_key: str) -> TileState:
        """Mark a tile PRIORITIZED (only from INCOMPLETE). Triggers panel update."""
        board = await self._get_board(team_id)
        state = board.tile_states.get(tile_key, TileState(tile_key=tile_key))
        if state.status != TileStatus.INCOMPLETE:
            raise ValueError(f"Tile {tile_key!r} is already {state.status.value}")
        state.status = TileStatus.PRIORITIZED
        await self._repo.update_tile_state(self._guild.id, team_id, tile_key, state)
        board.tile_states[tile_key] = state
        await self._update_board_panel(team_id)
        return state

    async def unprioritize_tile(self, team_id: int, tile_key: str) -> TileState:
        """Revert a PRIORITIZED tile to INCOMPLETE. Triggers panel update."""
        board = await self._get_board(team_id)
        state = board.tile_states.get(tile_key, TileState(tile_key=tile_key))
        if state.status != TileStatus.PRIORITIZED:
            raise ValueError(
                f"Tile {tile_key!r} is not prioritized (status: {state.status.value})"
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
            in_progress_data = await self._collect_in_progress_data(team.team_id)
            embed, file = _make_board_embed(
                team, board, img_bytes, "board.png", in_progress_data
            )
            from bingo.views import BoardProgressView

            view = BoardProgressView(self, team.team_id)
            msg = await channel.send(embed=embed, file=file, view=view)  # type: ignore[union-attr]
            board.board_panel_message_id = msg.id
            await self._repo.update_panel_ids(
                self._guild.id, team.team_id, board_panel_message_id=msg.id
            )
            results.append(f"Team {team.name}: board posted (msg {msg.id})")
        return results

    async def refresh_panels(self) -> list[str]:
        """Re-render and edit all existing board and completed panels for every team."""
        results: list[str] = []
        for team in self._event_service.get_all_teams():
            await self._update_board_panel(team.team_id)
            await self._update_completed_panel(team.team_id)
            results.append(f"Team {team.name}: refreshed")
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

    async def _collect_in_progress_data(
        self, team_id: int
    ) -> list[tuple[str, TileDefinition, list[TileSubmission]]]:
        """Gather per-tile progress data for all IN_PROGRESS tiles of a team."""
        board = await self._get_board(team_id)
        result: list[tuple[str, TileDefinition, list[TileSubmission]]] = []
        for key, state in sorted(
            board.tile_states.items(),
            key=lambda kv: tuple(int(x) for x in kv[0].split(",")),
        ):
            if state.status != TileStatus.IN_PROGRESS:
                continue
            tile_def = get_tile_def(key)
            if tile_def is None:
                continue
            approved = await self._repo.get_approved_submissions(
                self._guild.id, team_id, key
            )
            result.append((key, tile_def, approved))
        return result

    async def _get_board(self, team_id: int) -> TeamBoard:
        if team_id not in self._boards:
            board = await self._repo.get_or_create_board(self._guild.id, team_id)
            self._boards[team_id] = board
        return self._boards[team_id]

    async def _post_submission_notification(self, sub: TileSubmission) -> None:
        channel_id = self._event_service.get_submission_channel_id()
        if channel_id is None:
            return
        channel = self._guild.get_channel(channel_id)
        if channel is None:
            return
        tile_def = get_tile_def(sub.tile_key)
        tile_label = (
            f"({tile_def.row},{tile_def.col}) {tile_def.description}"
            if tile_def
            else sub.tile_key
        )
        team = self._get_team(sub.team_id)
        team_name = team.name if team else f"Team {sub.team_id}"
        embed = discord.Embed(
            title="New Submission",
            description=f"**Tile:** {tile_label}\n**Item:** {sub.item_label or '—'}",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Team", value=team_name, inline=True)
        embed.add_field(
            name="Submitted by", value=f"<@{sub.submitted_by}>", inline=True
        )
        embed.add_field(name="ID", value=f"`{sub.submission_id[:8]}`", inline=True)
        if sub.notes:
            embed.add_field(name="Notes", value=sub.notes, inline=False)
        embed.set_image(url=sub.screenshot_url)
        from bingo.views import SubmissionReviewView

        view = SubmissionReviewView(self, sub.submission_id)
        try:
            msg = await channel.send(embed=embed, view=view)  # type: ignore[union-attr]
            sub.review_channel_id = channel_id
            sub.review_message_id = msg.id
            await self._repo.update_submission(sub)
        except discord.HTTPException as e:
            logger.warning(f"Could not post submission notification: {e}")

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
            in_progress_data = await self._collect_in_progress_data(team_id)
            embed, file = _make_board_embed(
                team, board, img_bytes, "board.png", in_progress_data
            )
            from bingo.views import BoardProgressView

            view = BoardProgressView(self, team_id)
            await msg.edit(embed=embed, attachments=[file], view=view)
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
