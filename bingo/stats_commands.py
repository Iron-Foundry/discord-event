"""Stats subgroup for /bingo — generates plotly chart images."""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from loguru import logger

from bingo.stats_graphs import (
    render_leaderboard_chart,
    render_player_submissions_chart,
    render_submissions_chart,
    render_tiles_chart,
)
from bingo.tile_defs import TILE_DEFINITIONS

if TYPE_CHECKING:
    from bingo.service import BingoService


_TIME_CHOICES = [
    app_commands.Choice(name="Last 24 hours", value="1d"),
    app_commands.Choice(name="Last 3 days", value="3d"),
    app_commands.Choice(name="Last 7 days", value="7d"),
    app_commands.Choice(name="Last 14 days", value="14d"),
    app_commands.Choice(name="Last 30 days", value="30d"),
    app_commands.Choice(name="All time", value="all"),
]

_CHART_CHOICES = [
    app_commands.Choice(name="Grouped Bars (Horizontal)", value="bar_grouped_h"),
    app_commands.Choice(name="Stacked Bars (Horizontal)", value="bar_stacked_h"),
    app_commands.Choice(name="Grouped Bars (Vertical)", value="bar_grouped_v"),
    app_commands.Choice(name="Stacked Bars (Vertical)", value="bar_stacked_v"),
    app_commands.Choice(name="Pie Charts", value="pie"),
    app_commands.Choice(name="Scatter Plot", value="scatter"),
    app_commands.Choice(name="Treemap", value="treemap"),
    app_commands.Choice(name="Sunburst", value="sunburst"),
    app_commands.Choice(name="ECDF (All Time)", value="ecdf"),
]

_TIME_LABELS = {
    "1d": "Last 24 hours",
    "3d": "Last 3 days",
    "7d": "Last 7 days",
    "14d": "Last 14 days",
    "30d": "Last 30 days",
    "all": "All time",
}


def _cutoff(time_filter: str) -> datetime | None:
    """Return the UTC cutoff datetime, or None for 'all'."""
    if time_filter == "all":
        return None
    days = int(time_filter.rstrip("d"))
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)


async def _autocomplete_team_id(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[int]]:
    """Autocomplete for team_id parameters."""
    from bingo.service import BingoService  # noqa: PLC0415

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


def _resolve_player_names(
    interaction: discord.Interaction,
    subs: list,
) -> dict[int, str]:
    """Build a {user_id: display_name} map from the guild member cache."""
    names: dict[int, str] = {}
    guild = interaction.guild
    for s in subs:
        uid = s.submitted_by
        if uid in names:
            continue
        if guild is not None:
            member = guild.get_member(uid)
            names[uid] = member.display_name if member is not None else f"User {uid}"
        else:
            names[uid] = f"User {uid}"
    return names


class _BingoStatsGroup(
    app_commands.Group, name="stats", description="Event statistics and graphs"
):
    """Commands that render plotly chart images for bingo event data."""

    def __init__(self, service: "BingoService") -> None:
        super().__init__()
        self._service = service

    # ------------------------------------------------------------------
    # /bingo stats submissions
    # ------------------------------------------------------------------

    @app_commands.command(
        name="submissions",
        description="Submissions accepted/rejected over time",
    )
    @app_commands.describe(
        team_id="Filter to a specific team (omit for all teams)",
        time="Time window to show (default: all time)",
    )
    @app_commands.choices(time=_TIME_CHOICES)
    @app_commands.autocomplete(team_id=_autocomplete_team_id)
    async def stats_submissions(
        self,
        interaction: discord.Interaction,
        team_id: int | None = None,
        time: str = "all",
    ) -> None:
        await interaction.response.defer()
        guild_id = interaction.guild_id
        repo = self._service._repo

        subs = await repo.get_all_submissions(guild_id, team_id)

        cutoff = _cutoff(time)
        if cutoff is not None:
            subs = [s for s in subs if s.submitted_at >= cutoff]

        team_label = f"Team {team_id}" if team_id is not None else "All Teams"
        time_label = _TIME_LABELS.get(time, "All time")
        title = f"Submissions — {team_label}"

        png = render_submissions_chart(subs, title, time_label)

        approved = sum(1 for s in subs if s.status.value == "approved")
        rejected = sum(1 for s in subs if s.status.value == "rejected")
        pending = sum(1 for s in subs if s.status.value == "pending")

        embed = discord.Embed(
            title=title,
            description=f"**Time:** {time_label}\n**Approved:** {approved} | **Rejected:** {rejected} | **Pending:** {pending}",
            color=discord.Color.blurple(),
        )
        embed.set_image(url="attachment://stats.png")

        files = [discord.File(io.BytesIO(png), filename="stats.png")]

        if team_id is not None:
            player_names = _resolve_player_names(interaction, subs)
            player_pngs = render_player_submissions_chart(
                subs, player_names, title, time_label
            )
            files.append(
                discord.File(io.BytesIO(player_pngs[0]), filename="stats_players.png")
            )

        await interaction.followup.send(embed=embed, files=files)

    # ------------------------------------------------------------------
    # /bingo stats tiles
    # ------------------------------------------------------------------

    @app_commands.command(
        name="tiles",
        description="Tiles completed over time",
    )
    @app_commands.describe(
        team_id="Filter to a specific team (omit for all teams)",
        time="Time window to show (default: all time)",
    )
    @app_commands.choices(time=_TIME_CHOICES)
    @app_commands.autocomplete(team_id=_autocomplete_team_id)
    async def stats_tiles(
        self,
        interaction: discord.Interaction,
        team_id: int | None = None,
        time: str = "all",
    ) -> None:
        await interaction.response.defer()
        guild_id = interaction.guild_id
        repo = self._service._repo

        boards = await repo.get_all_boards(guild_id, team_id)

        cutoff = _cutoff(time)
        if cutoff is not None:
            from bingo.models import TileStatus  # noqa: PLC0415

            for board in boards:
                board.tile_states = {
                    key: state
                    for key, state in board.tile_states.items()
                    if not (
                        state.status == TileStatus.COMPLETE
                        and state.completed_at is not None
                        and state.completed_at < cutoff
                    )
                }

        team_label = f"Team {team_id}" if team_id is not None else "All Teams"
        time_label = _TIME_LABELS.get(time, "All time")
        title = f"Tiles Completed — {team_label}"

        png = render_tiles_chart(boards, title, time_label)

        total = sum(
            1
            for board in boards
            for state in board.tile_states.values()
            if state.status.value == "complete"
        )

        embed = discord.Embed(
            title=title,
            description=f"**Time:** {time_label}\n**Total tiles completed:** {total}",
            color=discord.Color.blurple(),
        )
        embed.set_image(url="attachment://stats.png")

        await interaction.followup.send(
            embed=embed,
            file=discord.File(io.BytesIO(png), filename="stats.png"),
        )

    # ------------------------------------------------------------------
    # /bingo stats players
    # ------------------------------------------------------------------

    @app_commands.command(
        name="players",
        description="Accepted/rejected submissions per player across all teams",
    )
    @app_commands.describe(
        time="Time window to show (default: all time)",
        chart="Chart type (default: grouped horizontal bars)",
    )
    @app_commands.choices(time=_TIME_CHOICES, chart=_CHART_CHOICES)
    async def stats_players(
        self,
        interaction: discord.Interaction,
        time: str = "all",
        chart: str = "bar_grouped_h",
    ) -> None:
        await interaction.response.defer()
        guild_id = interaction.guild_id
        repo = self._service._repo

        subs = await repo.get_all_submissions(guild_id, None)

        cutoff = _cutoff(time)
        if cutoff is not None and chart != "ecdf":
            subs = [s for s in subs if s.submitted_at >= cutoff]

        time_label = "All time" if chart == "ecdf" else _TIME_LABELS.get(time, "All time")
        title = "Submissions by Player — All Teams"

        player_names = _resolve_player_names(interaction, subs)
        pngs = render_player_submissions_chart(subs, player_names, title, time_label, chart)

        approved = sum(1 for s in subs if s.status.value == "approved")
        rejected = sum(1 for s in subs if s.status.value == "rejected")
        pending = sum(1 for s in subs if s.status.value == "pending")

        embed = discord.Embed(
            title=title,
            description=f"**Time:** {time_label}\n**Approved:** {approved} | **Rejected:** {rejected} | **Pending:** {pending}",
            color=discord.Color.blurple(),
        )
        embed.set_image(url="attachment://stats_players_0.png")

        files = [
            discord.File(io.BytesIO(png), filename=f"stats_players_{i}.png")
            for i, png in enumerate(pngs)
        ]
        await interaction.followup.send(embed=embed, files=files)

    # ------------------------------------------------------------------
    # /bingo stats leaderboard
    # ------------------------------------------------------------------

    @app_commands.command(
        name="leaderboard",
        description="Top submitted items, most completed tiles, and team standings",
    )
    @app_commands.describe(
        team_id="Filter to a specific team (omit for all teams)",
    )
    @app_commands.autocomplete(team_id=_autocomplete_team_id)
    async def stats_leaderboard(
        self,
        interaction: discord.Interaction,
        team_id: int | None = None,
    ) -> None:
        await interaction.response.defer()
        guild_id = interaction.guild_id
        repo = self._service._repo

        subs = await repo.get_all_submissions(guild_id, team_id)
        boards = await repo.get_all_boards(guild_id, team_id)

        png = render_leaderboard_chart(subs, boards, TILE_DEFINITIONS)

        team_label = f"Team {team_id}" if team_id is not None else "All Teams"
        embed = discord.Embed(
            title=f"Bingo Leaderboard — {team_label}",
            description="All-time statistics",
            color=discord.Color.gold(),
        )
        embed.set_image(url="attachment://leaderboard.png")

        await interaction.followup.send(
            embed=embed,
            file=discord.File(io.BytesIO(png), filename="leaderboard.png"),
        )
