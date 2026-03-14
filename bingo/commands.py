"""Bingo slash commands — participant and host interfaces."""

from __future__ import annotations

import io
import random
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from loguru import logger

from bingo.tile_defs import TILE_DEFINITIONS, get_tile_def
from bingo.models import TileStatus
from bingo.stats_commands import _BingoStatsGroup
from command_infra.checks import handle_check_failure
from command_infra.help_registry import HelpEntry, HelpGroup, HelpRegistry

if TYPE_CHECKING:
    from bingo.service import BingoService


# ------------------------------------------------------------------
# Help registration
# ------------------------------------------------------------------


def register_help(registry: HelpRegistry) -> None:
    """Register help entries for the bingo command group."""
    registry.add_group(
        HelpGroup(
            name="bingo",
            description="Track bingo tile submissions and board progress",
            commands=[
                HelpEntry(
                    "/bingo submit <tile> <item> <screenshot> [notes]",
                    "Submit a tile for host review",
                    "Everyone",
                ),
                HelpEntry("/bingo board", "View your team's 7×7 board", "Everyone"),
                HelpEntry(
                    "/bingo progress <tile>",
                    "View per-path progress for a tile",
                    "Everyone",
                ),
                HelpEntry(
                    "/bingo plan <tile>",
                    "Mark a tile as planned",
                    "Captain",
                ),
                HelpEntry(
                    "/bingo unplan <tile>",
                    "Remove planned status from a tile",
                    "Captain",
                ),
                HelpEntry(
                    "/bingo vc-invite <user>",
                    "Allow a user to join your team's voice channel",
                    "Everyone",
                ),
                HelpEntry(
                    "/bingo vc-uninvite <user>",
                    "Remove a user's access to your team's voice channel",
                    "Everyone",
                ),
            ],
        )
    )
    registry.add_group(
        HelpGroup(
            name="bingo host",
            description="Host tools for reviewing bingo submissions",
            commands=[
                HelpEntry(
                    "/bingo host pending [team]",
                    "List pending submissions",
                    "Event Host",
                ),
                HelpEntry(
                    "/bingo host approve <id>",
                    "Approve a submission",
                    "Event Host",
                ),
                HelpEntry(
                    "/bingo host reject <id> <reason>",
                    "Reject a submission",
                    "Event Host",
                ),
                HelpEntry(
                    "/bingo host release-boards",
                    "Post full board panel to each team's board channel",
                    "Event Host",
                ),
                HelpEntry(
                    "/bingo host post-completed <channel>",
                    "Post completed-only panels for all teams to a channel",
                    "Event Host",
                ),
                HelpEntry(
                    "/bingo host refresh-panels",
                    "Re-render and update all existing board and completed panels",
                    "Event Host",
                ),
                HelpEntry(
                    "/bingo host set-submission-channel <channel>",
                    "Set the channel where new submission notifications are posted",
                    "Event Host",
                ),
                HelpEntry(
                    "/bingo host rebuild [team]",
                    "Recompute all tile states from approved submissions",
                    "Event Host",
                ),
                HelpEntry(
                    "/bingo host edit-submission <id> <item>",
                    "Edit the item label on an approved submission",
                    "Event Host",
                ),
                HelpEntry(
                    "/bingo host notify-rejected",
                    "Retroactively DM all submitters whose submissions were rejected",
                    "Event Host",
                ),
                HelpEntry(
                    "/bingo host notify-approved",
                    "Retroactively DM all submitters whose submissions were approved",
                    "Event Host",
                ),
                HelpEntry(
                    "/bingo host audit-items",
                    "List submissions with item labels that don't match tile choices",
                    "Event Host",
                ),
            ],
        )
    )


# ------------------------------------------------------------------
# Autocomplete helpers
# ------------------------------------------------------------------


async def _autocomplete_tile(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete for tile parameters — all 49 tiles."""
    choices: list[app_commands.Choice[str]] = []
    for key, tile in TILE_DEFINITIONS.items():
        display = f"({tile.row},{tile.col}) {tile.description}"
        if not current or current.lower() in display.lower():
            choices.append(app_commands.Choice(name=display[:100], value=key))
    return choices[:25]


async def _autocomplete_item(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete items filtered to the selected tile's item_choices."""
    tile_key: str | None = getattr(interaction.namespace, "tile", None)
    if not tile_key:
        return []
    tile_def = get_tile_def(tile_key)
    if tile_def is None:
        return []
    choices = [
        app_commands.Choice(name=item, value=item)
        for item in tile_def.item_choices
        if not current or current.lower() in item.lower()
    ]
    return choices[:25]


async def _autocomplete_submission(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete pending submission IDs for host review commands."""
    client = interaction.client
    service: BingoService | None = getattr(client, "bingo_service", None)
    if service is None:
        return []
    pending = await service.get_pending_submissions()
    choices: list[app_commands.Choice[str]] = []
    for sub in pending:
        short_id = sub.submission_id[:8]
        item_str = sub.item_label or "—"
        name = f"[{short_id}] ({sub.tile_key}) {item_str} — <@{sub.submitted_by}>"
        if not current or current.lower() in name.lower():
            choices.append(
                app_commands.Choice(name=name[:100], value=sub.submission_id)
            )
    return choices[:25]


async def _autocomplete_incomplete_tile(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete tiles that are INCOMPLETE for the user's team."""
    client = interaction.client
    service: BingoService | None = getattr(client, "bingo_service", None)
    if service is None:
        return []
    team = service.get_team_for_member(interaction.user.id)
    if team is None:
        return []
    board = await service.get_board(team.team_id)
    choices: list[app_commands.Choice[str]] = []
    for key, tile in TILE_DEFINITIONS.items():
        state = board.tile_states.get(key)
        if state is not None and state.status != TileStatus.INCOMPLETE:
            continue
        display = f"({tile.row},{tile.col}) {tile.description}"
        if not current or current.lower() in display.lower():
            choices.append(app_commands.Choice(name=display[:100], value=key))
    return choices[:25]


async def _autocomplete_planned_tile(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete tiles that are PLANNED for the user's team."""
    client = interaction.client
    service: BingoService | None = getattr(client, "bingo_service", None)
    if service is None:
        return []
    team = service.get_team_for_member(interaction.user.id)
    if team is None:
        return []
    board = await service.get_board(team.team_id)
    choices: list[app_commands.Choice[str]] = []
    for key, tile in TILE_DEFINITIONS.items():
        state = board.tile_states.get(key)
        if state is None or state.status != TileStatus.PLANNED:
            continue
        display = f"({tile.row},{tile.col}) {tile.description}"
        if not current or current.lower() in display.lower():
            choices.append(app_commands.Choice(name=display[:100], value=key))
    return choices[:25]


async def _autocomplete_team_id(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[int]]:
    """Autocomplete for team_id parameters."""
    client = interaction.client
    service: BingoService | None = getattr(client, "bingo_service", None)
    if service is None:
        return []
    teams = service._event_service.get_all_teams()
    choices = [
        app_commands.Choice(
            name=f"Team {t.team_id} — {t.name}",
            value=t.team_id,
        )
        for t in teams
        if not current
        or str(t.team_id).startswith(current)
        or current.lower() in t.name.lower()
    ]
    return choices[:25]


async def _autocomplete_approved_submission(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete approved submission IDs for the edit-submission command."""
    client = interaction.client
    service: BingoService | None = getattr(client, "bingo_service", None)
    if service is None:
        return []
    approved = await service._repo.get_all_approved(service._guild.id)
    choices: list[app_commands.Choice[str]] = []
    for sub in approved:
        short_id = sub.submission_id[:8]
        item_str = sub.item_label or "—"
        name = f"[{short_id}] ({sub.tile_key}) {item_str} — Team {sub.team_id}"
        if not current or current.lower() in name.lower():
            choices.append(
                app_commands.Choice(name=name[:100], value=sub.submission_id)
            )
    return choices[:25]


async def _autocomplete_item_for_edit(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete item choices scoped to the selected submission's tile."""
    submission_id: str | None = getattr(interaction.namespace, "submission_id", None)
    if not submission_id:
        return []
    client = interaction.client
    service: BingoService | None = getattr(client, "bingo_service", None)
    if service is None:
        return []
    sub = await service._repo.get_submission(submission_id)
    if sub is None:
        return []
    tile_def = get_tile_def(sub.tile_key)
    if tile_def is None:
        return []
    return [
        app_commands.Choice(name=item, value=item)
        for item in tile_def.item_choices
        if not current or current.lower() in item.lower()
    ][:25]


# ------------------------------------------------------------------
# /bingo host subgroup
# ------------------------------------------------------------------


class _BingoHostGroup(
    app_commands.Group, name="host", description="Host tools for bingo review"
):
    """Commands for reviewing and managing bingo submissions."""

    def __init__(self, service: "BingoService") -> None:
        super().__init__()
        self._service = service

    def _check_host(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        return self._service.is_host(interaction.user)

    @app_commands.command(
        name="pending",
        description="List all pending submissions (optionally filtered by team)",
    )
    @app_commands.autocomplete(team_id=_autocomplete_team_id)
    async def host_pending(
        self,
        interaction: discord.Interaction,
        team_id: int | None = None,
    ) -> None:
        if not self._check_host(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        pending = await self._service.get_pending_submissions(team_id=team_id)
        if not pending:
            msg = "No pending submissions"
            if team_id is not None:
                msg += f" for Team {team_id}"
            await interaction.response.send_message(msg + ".", ephemeral=True)
            return

        lines: list[str] = []
        for sub in pending[:10]:
            short_id = sub.submission_id[:8]
            item_str = sub.item_label or "—"
            lines.append(
                f"`{short_id}` | `{sub.tile_key}` | {item_str} | Team {sub.team_id} | <@{sub.submitted_by}>"
            )

        description = "\n".join(lines)
        title = "Pending Submissions"
        if team_id is not None:
            title += f" — Team {team_id}"

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.orange(),
        )
        if len(pending) > 10:
            embed.set_footer(text=f"…and {len(pending) - 10} more")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="approve", description="Approve a pending submission")
    @app_commands.autocomplete(submission_id=_autocomplete_submission)
    async def host_approve(
        self,
        interaction: discord.Interaction,
        submission_id: str,
    ) -> None:
        if not self._check_host(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        try:
            sub, tile_now_complete = await self._service.approve(
                submission_id, interaction.user.id
            )
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        msg = f"Approved submission `{submission_id[:8]}` for tile `{sub.tile_key}`."
        if tile_now_complete:
            msg += "\n\n🎉 **Tile complete!**"
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(
        name="reject", description="Reject a pending submission with a reason"
    )
    @app_commands.autocomplete(submission_id=_autocomplete_submission)
    async def host_reject(
        self,
        interaction: discord.Interaction,
        submission_id: str,
        reason: str,
    ) -> None:
        if not self._check_host(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        try:
            sub = await self._service.reject(submission_id, interaction.user.id, reason)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        await interaction.response.send_message(
            f"Rejected submission `{submission_id[:8]}` for tile `{sub.tile_key}`.\nReason: {reason}",
            ephemeral=True,
        )
        try:
            user = await interaction.client.fetch_user(sub.submitted_by)
            embed = discord.Embed(
                title="❌ Submission Rejected",
                color=discord.Color.red(),
                description=f"**Reason:** {reason}",
            )
            embed.add_field(name="Tile", value=sub.tile_key, inline=True)
            if sub.item_label:
                embed.add_field(name="Item", value=sub.item_label, inline=True)
            embed.set_footer(text="Please fix the issue and re-submit.")
            await user.send(embed=embed)
        except discord.Forbidden, discord.HTTPException:
            pass

    @app_commands.command(
        name="set-submission-channel",
        description="Set the channel where new submission notifications are posted",
    )
    async def host_set_submission_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if not self._check_host(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        await self._service._event_service.set_submission_channel(channel.id)
        await interaction.response.send_message(
            f"Submission notifications will now be posted to {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="refresh-panels",
        description="Re-render and update all existing board and completed panels",
    )
    async def host_refresh_panels(self, interaction: discord.Interaction) -> None:
        if not self._check_host(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        results = await self._service.refresh_panels()
        await interaction.followup.send("\n".join(results) or "Done.", ephemeral=True)

    @app_commands.command(
        name="release-boards",
        description="Post the full board panel to each team's board channel",
    )
    async def host_release_boards(self, interaction: discord.Interaction) -> None:
        if not self._check_host(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        results = await self._service.release_boards()
        await interaction.followup.send("\n".join(results) or "Done.", ephemeral=True)

    @app_commands.command(
        name="post-completed",
        description="Post completed-only panels for all teams to a channel",
    )
    async def host_post_completed(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if not self._check_host(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            results = await self._service.post_completed_panels(channel.id)
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return
        await interaction.followup.send("\n".join(results) or "Done.", ephemeral=True)

    @app_commands.command(
        name="rebuild",
        description="Recompute all tile states from approved submissions (run after tile-def changes)",
    )
    @app_commands.autocomplete(team_id=_autocomplete_team_id)
    async def host_rebuild(
        self,
        interaction: discord.Interaction,
        team_id: int | None = None,
    ) -> None:
        if not self._check_host(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        results = await self._service.rebuild_states(team_id=team_id)
        await interaction.followup.send(
            "\n".join(results) or "Done (no changes).", ephemeral=True
        )

    @app_commands.command(
        name="edit-submission",
        description="Edit the item label on an approved submission",
    )
    @app_commands.autocomplete(
        submission_id=_autocomplete_approved_submission,
        item_label=_autocomplete_item_for_edit,
    )
    async def host_edit_submission(
        self,
        interaction: discord.Interaction,
        submission_id: str,
        item_label: str,
    ) -> None:
        if not self._check_host(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        try:
            sub, now_complete, tile_uncompleted = await self._service.edit_submission(
                submission_id, interaction.user.id, item_label
            )
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        msg = (
            f"Submission `{submission_id[:8]}` updated.\n"
            f"**Tile:** `{sub.tile_key}` · **New item:** `{item_label}`"
        )
        if now_complete:
            msg += "\n\n🎉 **Tile now complete!**"
        elif tile_uncompleted:
            msg += "\n\n⚠️ **Tile was complete but is no longer satisfied — reverted to In Progress.**"
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(
        name="notify-approved",
        description="Retroactively DM all submitters whose submissions were approved",
    )
    async def host_notify_approved(self, interaction: discord.Interaction) -> None:
        if not self._check_host(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        approved = await self._service._repo.get_all_approved(self._service._guild.id)
        if not approved:
            await interaction.followup.send(
                "No approved submissions found.", ephemeral=True
            )
            return

        # Cache tile completion status: (team_id, tile_key) → bool
        tile_complete: dict[tuple[int, str], bool] = {}
        for sub in approved:
            key = (sub.team_id, sub.tile_key)
            if key not in tile_complete:
                board = await self._service.get_board(sub.team_id)
                state = board.tile_states.get(sub.tile_key)
                tile_complete[key] = (
                    state is not None and state.status == TileStatus.COMPLETE
                )

        sent = 0
        failed = 0
        for sub in approved:
            tile_now_complete = tile_complete[(sub.team_id, sub.tile_key)]
            try:
                user = await interaction.client.fetch_user(sub.submitted_by)
                embed = discord.Embed(
                    title="✅ Submission Approved",
                    color=discord.Color.green(),
                )
                embed.add_field(name="Tile", value=sub.tile_key, inline=True)
                if sub.item_label:
                    embed.add_field(name="Item", value=sub.item_label, inline=True)
                if tile_now_complete:
                    embed.description = "🎉 Your team's tile is now **complete**!"
                embed.set_image(url=sub.screenshot_url)
                await user.send(embed=embed)
                sent += 1
            except discord.Forbidden, discord.HTTPException:
                failed += 1

        lines = [
            f"Done. **{sent}** DM(s) sent across {len(approved)} approved submission(s)."
        ]
        if failed:
            lines.append(f"**{failed}** failed (DMs disabled or user unreachable).")
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @app_commands.command(
        name="notify-rejected",
        description="Retroactively DM all submitters whose submissions were rejected",
    )
    async def host_notify_rejected(self, interaction: discord.Interaction) -> None:
        if not self._check_host(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        rejected = await self._service._repo.get_all_rejected(self._service._guild.id)
        if not rejected:
            await interaction.followup.send(
                "No rejected submissions found.", ephemeral=True
            )
            return

        sent = 0
        failed = 0
        for sub in rejected:
            reason = sub.rejection_reason or "No reason provided."
            try:
                user = await interaction.client.fetch_user(sub.submitted_by)
                embed = discord.Embed(
                    title="❌ Submission Rejected",
                    color=discord.Color.red(),
                    description=f"**Reason:** {reason}",
                )
                embed.add_field(name="Tile", value=sub.tile_key, inline=True)
                if sub.item_label:
                    embed.add_field(name="Item", value=sub.item_label, inline=True)
                embed.set_footer(text="Please fix the issue and re-submit.")
                embed.set_image(url=sub.screenshot_url)
                await user.send(embed=embed)
                sent += 1
            except discord.Forbidden, discord.HTTPException:
                failed += 1

        lines = [
            f"Done. **{sent}** DM(s) sent across {len(rejected)} rejected submission(s)."
        ]
        if failed:
            lines.append(f"**{failed}** failed (DMs disabled or user unreachable).")
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @app_commands.command(
        name="audit-items",
        description="List all submissions whose item label is not a valid choice for their tile",
    )
    async def host_audit_items(self, interaction: discord.Interaction) -> None:
        if not self._check_host(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        subs = await self._service._repo.get_all_active(self._service._guild.id)

        invalid: list[tuple[str, object]] = []
        for sub in subs:
            tile_def = get_tile_def(sub.tile_key)
            if tile_def is None:
                invalid.append((f"Unknown tile `{sub.tile_key}`", sub))
                continue
            if sub.item_label not in tile_def.item_choices:
                valid_str = ", ".join(tile_def.item_choices)
                label = sub.item_label or "(none)"
                tile_label = f"({tile_def.row},{tile_def.col}) {tile_def.description}"
                invalid.append(
                    (
                        f'[{sub.submission_id[:8]}] {tile_label} | "{label}" → {valid_str}  [{sub.status.value}]',
                        sub,
                    )
                )

        if not invalid:
            await interaction.followup.send(
                "All active submissions have valid item labels. ✓", ephemeral=True
            )
            return

        # Sort: PENDING first, then APPROVED
        invalid.sort(
            key=lambda x: (0 if x[1].status.value == "pending" else 1, x[1].tile_key)
        )  # type: ignore[union-attr]

        lines = [f"Found {len(invalid)} invalid submission(s):\n"]
        for line, _ in invalid:
            lines.append(line)

        output = "\n".join(lines)

        if len(invalid) <= 15:
            embed = discord.Embed(
                title="⚠️ Invalid Item Labels",
                description=f"```\n{output}\n```",
                color=discord.Color.yellow(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            file = discord.File(
                io.BytesIO(output.encode()),
                filename="invalid_items.txt",
            )
            await interaction.followup.send(
                f"Found {len(invalid)} invalid submissions — see attached file.",
                file=file,
                ephemeral=True,
            )

    @app_commands.command(
        name="testboard",
        description="Render a test board with randomly placed tile markers",
    )
    async def host_testboard(
        self,
        interaction: discord.Interaction,
        complete: app_commands.Range[int, 0, 49] = 5,
        in_review: app_commands.Range[int, 0, 49] = 5,
        seed: int | None = None,
    ) -> None:
        if not self._check_host(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        from bingo.board_renderer import render_test_board

        rng = random.Random(seed)
        all_keys = [f"{r},{c}" for r in range(1, 8) for c in range(1, 8)]
        total = min(complete + in_review, 49)
        sampled = rng.sample(all_keys, total)

        tile_states: dict[str, TileStatus] = {}
        for key in sampled[:complete]:
            tile_states[key] = TileStatus.COMPLETE
        for key in sampled[complete:]:
            tile_states[key] = TileStatus.IN_REVIEW

        img_bytes = render_test_board(tile_states)

        complete_keys = sorted(
            k for k, v in tile_states.items() if v == TileStatus.COMPLETE
        )
        review_keys = sorted(
            k for k, v in tile_states.items() if v == TileStatus.IN_REVIEW
        )
        seed_str = str(seed) if seed is not None else "random"

        lines = [f"**Seed:** `{seed_str}`  •  **{len(tile_states)}/49** tiles marked"]
        if complete_keys:
            lines.append(
                "**■ Complete:** " + "  ".join(f"`{k}`" for k in complete_keys)
            )
        if review_keys:
            lines.append(
                "**○ In Progress:** " + "  ".join(f"`{k}`" for k in review_keys)
            )

        embed = discord.Embed(
            title="Test Board Render",
            description="\n".join(lines),
            color=discord.Color.purple(),
        )
        embed.set_image(url="attachment://test_board.png")

        file = discord.File(io.BytesIO(img_bytes), filename="test_board.png")
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)


# ------------------------------------------------------------------
# /bingo top-level group
# ------------------------------------------------------------------

_GRID_SYMBOLS = {
    TileStatus.COMPLETE: "■",
    TileStatus.IN_REVIEW: "○",
    TileStatus.IN_PROGRESS: "○",
    TileStatus.PLANNED: "P",
    TileStatus.INCOMPLETE: "·",
}


class BingoGroup(
    app_commands.Group, name="bingo", description="Bingo board and submissions"
):
    """Slash commands for bingo tile submissions and board viewing."""

    def __init__(self, service: "BingoService") -> None:
        super().__init__()
        self._service = service
        self.add_command(_BingoHostGroup(service))
        self.add_command(_BingoStatsGroup(service))

    async def on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        await handle_check_failure(interaction, error)

    # ------------------------------------------------------------------
    # /bingo plan / /bingo unplan
    # ------------------------------------------------------------------

    @app_commands.command(
        name="plan", description="Mark a tile as planned (captain only)"
    )
    @app_commands.autocomplete(tile=_autocomplete_incomplete_tile)
    async def plan(self, interaction: discord.Interaction, tile: str) -> None:
        if not self._service.is_captain(interaction.user.id):
            await interaction.response.send_message(
                "Only the team captain can plan tiles.", ephemeral=True
            )
            return
        tile_def = get_tile_def(tile)
        if tile_def is None:
            await interaction.response.send_message(
                f"Unknown tile `{tile}`.", ephemeral=True
            )
            return
        team = self._service.get_team_for_member(interaction.user.id)
        try:
            await self._service.plan_tile(team.team_id, tile)  # type: ignore[union-attr]
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return
        await interaction.response.send_message(
            f"Tile `({tile_def.row},{tile_def.col}) {tile_def.description}` marked as planned.",
            ephemeral=True,
        )

    @app_commands.command(
        name="unplan", description="Remove planned status from a tile (captain only)"
    )
    @app_commands.autocomplete(tile=_autocomplete_planned_tile)
    async def unplan(self, interaction: discord.Interaction, tile: str) -> None:
        if not self._service.is_captain(interaction.user.id):
            await interaction.response.send_message(
                "Only the team captain can unplan tiles.", ephemeral=True
            )
            return
        tile_def = get_tile_def(tile)
        if tile_def is None:
            await interaction.response.send_message(
                f"Unknown tile `{tile}`.", ephemeral=True
            )
            return
        team = self._service.get_team_for_member(interaction.user.id)
        try:
            await self._service.unplan_tile(team.team_id, tile)  # type: ignore[union-attr]
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return
        await interaction.response.send_message(
            f"Tile `({tile_def.row},{tile_def.col}) {tile_def.description}` removed from planned.",
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    # /bingo vc-invite / /bingo vc-uninvite
    # ------------------------------------------------------------------

    @app_commands.command(
        name="vc-invite",
        description="Allow a user to join your team's voice channel",
    )
    async def vc_invite(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        team = self._service.get_team_for_member(interaction.user.id)
        if team is None:
            await interaction.response.send_message(
                "You are not on a bingo team.", ephemeral=True
            )
            return
        if not team.voice_channel_id:
            await interaction.response.send_message(
                "Your team does not have a voice channel.", ephemeral=True
            )
            return
        channel = interaction.guild.get_channel(team.voice_channel_id)  # type: ignore[union-attr]
        if channel is None:
            await interaction.response.send_message(
                "Your team's voice channel could not be found.", ephemeral=True
            )
            return
        await channel.set_permissions(user, connect=True, view_channel=True)  # type: ignore[union-attr]
        await interaction.response.send_message(
            f"{user.mention} can now join **{channel.name}**.", ephemeral=True
        )

    @app_commands.command(
        name="vc-uninvite",
        description="Remove a user's access to your team's voice channel",
    )
    async def vc_uninvite(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        team = self._service.get_team_for_member(interaction.user.id)
        if team is None:
            await interaction.response.send_message(
                "You are not on a bingo team.", ephemeral=True
            )
            return
        if not team.voice_channel_id:
            await interaction.response.send_message(
                "Your team does not have a voice channel.", ephemeral=True
            )
            return
        channel = interaction.guild.get_channel(team.voice_channel_id)  # type: ignore[union-attr]
        if channel is None:
            await interaction.response.send_message(
                "Your team's voice channel could not be found.", ephemeral=True
            )
            return
        await channel.set_permissions(user, overwrite=None)  # type: ignore[union-attr]
        await interaction.response.send_message(
            f"{user.mention}'s access to **{channel.name}** has been removed.",
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    # /bingo submit
    # ------------------------------------------------------------------

    @app_commands.command(
        name="submit", description="Submit a tile completion screenshot for review"
    )
    @app_commands.autocomplete(tile=_autocomplete_tile, item=_autocomplete_item)
    async def submit(
        self,
        interaction: discord.Interaction,
        tile: str,
        item: str,
        screenshot: discord.Attachment,
        notes: str | None = None,
    ) -> None:
        team = self._service.get_team_for_member(interaction.user.id)
        if team is None:
            await interaction.response.send_message(
                "You are not on a bingo team.", ephemeral=True
            )
            return

        tile_def = get_tile_def(tile)
        if tile_def is None:
            await interaction.response.send_message(
                f"Unknown tile `{tile}`.", ephemeral=True
            )
            return

        if item not in tile_def.item_choices:
            valid = ", ".join(f"`{c}`" for c in tile_def.item_choices)
            await interaction.response.send_message(
                f"`{item}` is not a valid item for this tile. Valid choices: {valid}",
                ephemeral=True,
            )
            return

        board = await self._service.get_board(team.team_id)
        tile_state = board.tile_states.get(tile)
        if tile_state is not None and tile_state.status == TileStatus.COMPLETE:
            await interaction.response.send_message(
                f"Tile `({tile_def.row},{tile_def.col}) {tile_def.description}` is already complete.",
                ephemeral=True,
            )
            return

        sub = await self._service.submit(
            team_id=team.team_id,
            tile_key=tile,
            submitted_by=interaction.user.id,
            screenshot_url=screenshot.url,
            item_label=item or None,
            notes=notes,
        )

        await interaction.response.send_message(
            f"Submission received!\n"
            f"**Tile:** ({tile_def.row},{tile_def.col}) {tile_def.description}\n"
            f"**Item:** {item or '—'}\n"
            f"**ID:** `{sub.submission_id[:8]}`\n"
            "A host will review your submission.",
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    # /bingo board
    # ------------------------------------------------------------------

    @app_commands.command(name="board", description="View your team's 7×7 bingo board")
    async def board(self, interaction: discord.Interaction) -> None:
        team = self._service.get_team_for_member(interaction.user.id)
        if team is None:
            await interaction.response.send_message(
                "You are not on a bingo team.", ephemeral=True
            )
            return

        board = await self._service.get_board(team.team_id)

        # Build 7×7 ASCII grid
        header = "     " + "  ".join(str(c) for c in range(1, 8))
        rows: list[str] = [header]
        complete_count = 0
        for r in range(1, 8):
            cells: list[str] = []
            for c in range(1, 8):
                key = f"{r},{c}"
                state = board.tile_states.get(key)
                status = state.status if state else TileStatus.INCOMPLETE
                symbol = _GRID_SYMBOLS[status]
                if status == TileStatus.COMPLETE:
                    complete_count += 1
                cells.append(symbol)
            rows.append(f"  {r}   " + "  ".join(cells))

        grid_text = "\n".join(rows)

        embed = discord.Embed(
            title=f"Team {team.team_id} — {team.name} — Bingo Board",
            description=f"```\n{grid_text}\n```",
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text=f"■ Complete  ○ In Progress  P Planned  · Incomplete  |  {complete_count}/49 complete"
        )
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # /bingo progress
    # ------------------------------------------------------------------

    @app_commands.command(
        name="progress", description="View per-path progress on a specific tile"
    )
    @app_commands.autocomplete(tile=_autocomplete_tile)
    async def progress(
        self,
        interaction: discord.Interaction,
        tile: str,
    ) -> None:
        team = self._service.get_team_for_member(interaction.user.id)
        if team is None:
            await interaction.response.send_message(
                "You are not on a bingo team.", ephemeral=True
            )
            return

        tile_def = get_tile_def(tile)
        if tile_def is None:
            await interaction.response.send_message(
                f"Unknown tile `{tile}`.", ephemeral=True
            )
            return

        board = await self._service.get_board(team.team_id)
        tile_state = board.tile_states.get(tile)
        status = tile_state.status if tile_state else TileStatus.INCOMPLETE

        approved_subs = await self._service._repo.get_approved_submissions(
            self._service._guild.id, team.team_id, tile
        )

        per_path = self._service.get_tile_progress(tile_def, approved_subs)

        status_label = {
            TileStatus.INCOMPLETE: "Incomplete",
            TileStatus.PLANNED: "Planned",
            TileStatus.IN_REVIEW: "In Progress",
            TileStatus.IN_PROGRESS: "In Progress",
            TileStatus.COMPLETE: "Complete ✓",
        }.get(status, status.value)

        embed = discord.Embed(
            title=f"({tile_def.row},{tile_def.col}) {tile_def.description}",
            description=f"**Status:** {status_label}",
            color=discord.Color.green()
            if status == TileStatus.COMPLETE
            else discord.Color.blue(),
        )

        # Per-path progress fields
        for path in tile_def.completion_paths:
            constraints = per_path[path.label]
            all_done = all(done >= total for _, done, total in constraints)

            if all_done:
                value = "✓ Complete"
            elif len(constraints) == 1:
                _, done, total = constraints[0]
                value = f"{done}/{total}"
            else:
                lines = []
                for clabel, done, total in constraints:
                    if done >= total:
                        lines.append(f"✓ {clabel}")
                    else:
                        lines.append(f"{clabel}: {done}/{total}")
                value = "\n".join(lines)

            # Approved items relevant to this path (union of all pools + requirements)
            all_eligible: set[str] = set(path.requirements.keys())
            for pool in path.pool_requirements:
                all_eligible.update(pool.eligible_items)
            path_items = [
                s.item_label
                for s in approved_subs
                if s.item_label and (not all_eligible or s.item_label in all_eligible)
            ]
            if path_items:
                value += "\n" + ", ".join(f"`{i}`" for i in path_items)

            embed.add_field(name=path.label, value=value, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)
