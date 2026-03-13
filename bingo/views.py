"""Discord UI views for bingo submission review."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bingo.models import TileSubmission
    from bingo.service import BingoService


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
        except (discord.Forbidden, discord.HTTPException):
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
        except (discord.Forbidden, discord.HTTPException):
            pass

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


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
