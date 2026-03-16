"""Discord UI views for bingo submission review."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bingo.models import TileSubmission
    from bingo.service import BingoService
    from bingo.tile_defs import TileDefinition


def _make_tile_detail_embed(
    tile_def: "TileDefinition",
    approved: "list[TileSubmission]",
    member_ids: list[int],
) -> discord.Embed:
    """Build a detailed progress embed for a single in-progress tile."""
    from bingo.service import check_path_satisfied, path_progress

    title = f"({tile_def.row},{tile_def.col}) {tile_def.description}"
    embed = discord.Embed(title=title, color=discord.Color.orange())

    if tile_def.is_team_wide:
        submitters = {s.submitted_by for s in approved}
        submitted_mentions = [f"<@{uid}>" for uid in member_ids if uid in submitters]
        missing_mentions = [f"<@{uid}>" for uid in member_ids if uid not in submitters]
        lines: list[str] = []
        if submitted_mentions:
            lines.append("Submitted: " + ", ".join(submitted_mentions))
        if missing_mentions:
            lines.append("Missing: " + ", ".join(missing_mentions))
        embed.add_field(
            name="Team Progress", value="\n".join(lines) or "—", inline=False
        )
        return embed

    item_counts: Counter[str] = Counter(s.item_label for s in approved if s.item_label)

    for path in tile_def.completion_paths:
        satisfied = check_path_satisfied(path, approved)
        constraints = path_progress(path, approved)
        lines = []

        for item_name, required in path.requirements.items():
            done = min(item_counts[item_name], required)
            mark = "✓" if done >= required else "·"
            lines.append(f"{mark} {item_name}: {done}/{required}")

        pool_idx = 1 if path.requirements else 0
        for pool in path.pool_requirements:
            if pool_idx >= len(constraints):
                break
            clabel, done, total = constraints[pool_idx]
            mark = "✓" if done >= total else "·"
            if pool.item_weights:
                lines.append(f"{mark} {clabel}: {done}/{total} pts")
            elif pool.eligible_items:
                shown = pool.eligible_items[:5]
                suffix = (
                    f" (+{len(pool.eligible_items) - 5} more)"
                    if len(pool.eligible_items) > 5
                    else ""
                )
                lines.append(
                    f"{mark} {clabel}: {done}/{total}\n  ↳ {', '.join(shown)}{suffix}"
                )
            else:
                lines.append(f"{mark} {clabel}: {done}/{total}")
                if pool.unique_labels and done > 0:
                    candidates = [
                        s
                        for s in approved
                        if s.item_label
                        and (
                            not pool.eligible_items
                            or s.item_label in pool.eligible_items
                        )
                    ]
                    obtained = sorted({s.item_label for s in candidates})
                    lines.append(f"  ↳ {', '.join(obtained)}")
            pool_idx += 1

        field_name = f"✓ {path.label}" if satisfied else path.label
        embed.add_field(name=field_name, value="\n".join(lines) or "—", inline=False)

    return embed


class _RejectReasonModal(discord.ui.Modal, title="Reject Submission"):
    reason: discord.ui.TextInput = discord.ui.TextInput(
        label="Reason for rejection",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    def __init__(self, view: SubmissionReviewView) -> None:
        super().__init__()
        self._view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._view._do_reject(interaction, self.reason.value)


class SubmissionReviewView(discord.ui.View):
    """Approve / Reject buttons attached to a submission notification message."""

    def __init__(self, service: "BingoService", submission_id: str) -> None:
        super().__init__(timeout=None)
        self._service = service
        self._submission_id = submission_id

        approve_btn = discord.ui.Button(
            label="Approve",
            style=discord.ButtonStyle.success,
            custom_id=f"sub_approve:{submission_id}",
        )
        approve_btn.callback = self._approve_callback
        self.add_item(approve_btn)

        reject_btn = discord.ui.Button(
            label="Reject",
            style=discord.ButtonStyle.danger,
            custom_id=f"sub_reject:{submission_id}",
        )
        reject_btn.callback = self._reject_callback
        self.add_item(reject_btn)

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    async def _approve_callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(
            interaction.user, discord.Member
        ) or not self._service.is_host(interaction.user):
            await interaction.response.send_message(
                "Only hosts can review submissions.", ephemeral=True
            )
            return
        try:
            sub, tile_now_complete = await self._service.approve(
                self._submission_id, interaction.user.id
            )
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        self._disable_buttons()
        embed = _copy_embed_with(
            interaction.message,
            color=discord.Color.green(),
            footer=f"✓ Approved by {interaction.user.display_name}",
        )
        content = "🎉 **Tile complete!**" if tile_now_complete else None
        await interaction.response.edit_message(content=content, embed=embed, view=self)
        await self._notify_submitter_approved(interaction, sub, tile_now_complete)

    async def _reject_callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(
            interaction.user, discord.Member
        ) or not self._service.is_host(interaction.user):
            await interaction.response.send_message(
                "Only hosts can review submissions.", ephemeral=True
            )
            return
        await interaction.response.send_modal(_RejectReasonModal(self))

    async def _do_reject(self, interaction: discord.Interaction, reason: str) -> None:
        try:
            sub = await self._service.reject(
                self._submission_id, interaction.user.id, reason
            )
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        self._disable_buttons()
        embed = _copy_embed_with(
            interaction.message,
            color=discord.Color.red(),
            footer=f"✗ Rejected by {interaction.user.display_name}: {reason}",
        )
        await interaction.response.edit_message(embed=embed, view=self)
        await self._notify_submitter_rejected(interaction, sub, reason)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _notify_submitter_approved(
        self,
        interaction: discord.Interaction,
        sub: "TileSubmission",
        tile_now_complete: bool,
    ) -> None:
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
            await user.send(embed=embed)
        except discord.Forbidden, discord.HTTPException:
            pass

    async def _notify_submitter_rejected(
        self,
        interaction: discord.Interaction,
        sub: "TileSubmission",
        reason: str,
    ) -> None:
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

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class BoardProgressView(discord.ui.View):
    """Persistent 'View Progress' button attached to a team's board panel."""

    def __init__(self, service: "BingoService", team_id: int) -> None:
        super().__init__(timeout=None)
        self._service = service
        self._team_id = team_id

        btn = discord.ui.Button(
            label="View Progress",
            style=discord.ButtonStyle.primary,
            emoji="📋",
            custom_id=f"board_progress:{team_id}",
        )
        btn.callback = self._progress_callback
        self.add_item(btn)

    async def _progress_callback(self, interaction: discord.Interaction) -> None:
        team = self._service._get_team(self._team_id)
        if team is None:
            await interaction.response.send_message("Team not found.", ephemeral=True)
            return

        in_progress_data = await self._service._collect_in_progress_data(self._team_id)
        if not in_progress_data:
            await interaction.response.send_message(
                "No tiles currently in progress.", ephemeral=True
            )
            return

        member_ids = [m.discord_user_id for m in team.members]
        embeds = [
            _make_tile_detail_embed(tile_def, approved, member_ids)
            for _, tile_def, approved in in_progress_data
        ]

        await interaction.response.send_message(embeds=embeds[:10], ephemeral=True)
        for i in range(10, len(embeds), 10):
            await interaction.followup.send(embeds=embeds[i : i + 10], ephemeral=True)


def _copy_embed_with(
    message: discord.Message | None,
    color: discord.Color,
    footer: str,
) -> discord.Embed:
    """Return a copy of the first embed from *message* with updated color and footer."""
    if message and message.embeds:
        embed = message.embeds[0].copy()
    else:
        embed = discord.Embed(title="Submission")
    embed.color = color
    embed.set_footer(text=footer)
    return embed
