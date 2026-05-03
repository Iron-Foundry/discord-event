from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from loguru import logger

from command_infra.checks import handle_check_failure, is_senior_staff
from command_infra.help_registry import HelpEntry, HelpGroup, HelpRegistry

if TYPE_CHECKING:
    from events.service import EventService


def register_help(registry: HelpRegistry) -> None:
    """Register help entries for the event command group."""
    registry.add_group(
        HelpGroup(
            name="event",
            description="Create and manage clan bingo events",
            commands=[
                HelpEntry(
                    "/event setup", "Seed teams + create all channels", "Event Host"
                ),
                HelpEntry("/event teardown", "Delete all event channels", "Event Host"),
                HelpEntry(
                    "/event status", "Show event state and team count", "Everyone"
                ),
                HelpEntry("/event host add", "Add a user to the host list", "Staff"),
                HelpEntry(
                    "/event host remove", "Remove a user from the host list", "Staff"
                ),
                HelpEntry("/event host list", "List current hosts", "Staff"),
                HelpEntry(
                    "/event host setrole", "Set role fallback for host check", "Staff"
                ),
                HelpEntry(
                    "/event team list", "Show all teams and member counts", "Everyone"
                ),
                HelpEntry(
                    "/event team info", "Show full member list for a team", "Everyone"
                ),
                HelpEntry(
                    "/event team setcaptain", "Designate a team captain", "Event Host"
                ),
                HelpEntry(
                    "/event team addmember", "Add a member to a team", "Event Host"
                ),
                HelpEntry(
                    "/event team removemember",
                    "Remove a member from their team",
                    "Event Host",
                ),
                HelpEntry(
                    "/event team rename",
                    "Rename a team (and its channels)",
                    "Event Host",
                ),
            ],
        )
    )


# ------------------------------------------------------------------
# Autocomplete
# ------------------------------------------------------------------


async def _autocomplete_team_id(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[int]]:
    """Autocomplete for team_id parameters."""
    client = interaction.client
    service: EventService | None = getattr(client, "event_service", None)
    if service is None:
        return []
    teams = service.get_all_teams()
    choices = [
        app_commands.Choice(
            name=f"Team {t.team_id} - {len(t.members)} members",
            value=t.team_id,
        )
        for t in teams
        if not current or str(t.team_id).startswith(current)
    ]
    return choices[:25]


# ------------------------------------------------------------------
# /event host subgroup
# ------------------------------------------------------------------


class _EventHostGroup(
    app_commands.Group, name="host", description="Manage event hosts"
):
    """Commands for managing who counts as an event host."""

    def __init__(self, service: "EventService") -> None:
        super().__init__()
        self._service = service

    @app_commands.command(name="add", description="Add a user to the event host list")
    @is_senior_staff()
    async def host_add(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        await self._service.add_host(user.id)
        await interaction.response.send_message(
            f"{user.mention} added to event hosts.", ephemeral=True
        )

    @app_commands.command(
        name="remove", description="Remove a user from the event host list"
    )
    @is_senior_staff()
    async def host_remove(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        await self._service.remove_host(user.id)
        await interaction.response.send_message(
            f"{user.mention} removed from event hosts.", ephemeral=True
        )

    @app_commands.command(name="list", description="List current event hosts")
    @is_senior_staff()
    async def host_list(self, interaction: discord.Interaction) -> None:
        config = self._service._ensure_config()
        guild = interaction.guild
        lines: list[str] = []
        for uid in config.host_user_ids:
            member = guild.get_member(uid) if guild else None
            lines.append(member.mention if member else f"<@{uid}>")
        if config.host_role_id:
            role = guild.get_role(config.host_role_id) if guild else None
            lines.append(
                f"Role fallback: {role.mention if role else f'<@&{config.host_role_id}>'}"
            )
        body = "\n".join(lines) if lines else "No hosts configured."
        embed = discord.Embed(
            title="Event Hosts", description=body, color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="setrole", description="Set a Discord role as host fallback"
    )
    @is_senior_staff()
    async def host_setrole(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        await self._service.set_host_role(role.id)
        await interaction.response.send_message(
            f"{role.mention} set as event host role.", ephemeral=True
        )


# ------------------------------------------------------------------
# /event team subgroup
# ------------------------------------------------------------------


class _EventTeamGroup(
    app_commands.Group, name="team", description="Manage event teams"
):
    """Commands for viewing and managing bingo teams."""

    def __init__(self, service: "EventService") -> None:
        super().__init__()
        self._service = service

    @app_commands.command(name="list", description="Show all teams and member counts")
    async def team_list(self, interaction: discord.Interaction) -> None:
        teams = self._service.get_all_teams()
        if not teams:
            await interaction.response.send_message("No teams found.", ephemeral=True)
            return
        lines = [
            f"**Team {t.team_id}** - {t.name} ({len(t.members)} members)" for t in teams
        ]
        embed = discord.Embed(
            title="Bingo Teams",
            description="\n".join(lines),
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="info", description="Show full member list for a team")
    @app_commands.autocomplete(team_id=_autocomplete_team_id)
    async def team_info(self, interaction: discord.Interaction, team_id: int) -> None:
        teams = self._service._teams
        team = teams.get(team_id)
        if team is None:
            await interaction.response.send_message(
                f"Team {team_id} not found.", ephemeral=True
            )
            return
        lines = []
        for m in team.members:
            captain_tag = " 👑" if m.is_captain else ""
            lines.append(f"<@{m.discord_user_id}> - `{m.rsn}`{captain_tag}")
        embed = discord.Embed(
            title=f"Team {team.team_id} - {team.name}",
            description="\n".join(lines) if lines else "No members.",
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setcaptain", description="Designate a team captain")
    @app_commands.autocomplete(team_id=_autocomplete_team_id)
    async def team_setcaptain(
        self,
        interaction: discord.Interaction,
        team_id: int,
        user: discord.Member,
    ) -> None:
        # Defer with is_event_host check inline - decorator approach below
        if not self._service.is_host(interaction.user):  # type: ignore[arg-type]
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        ok = await self._service.set_captain(team_id, user.id)
        if not ok:
            await interaction.response.send_message(
                f"{user.mention} is not a member of Team {team_id}.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"{user.mention} is now captain of Team {team_id}.", ephemeral=True
        )

    @app_commands.command(name="addmember", description="Add a member to a team")
    @app_commands.autocomplete(team_id=_autocomplete_team_id)
    async def team_addmember(
        self,
        interaction: discord.Interaction,
        team_id: int,
        user: discord.Member,
        rsn: str,
    ) -> None:
        if not self._service.is_host(interaction.user):  # type: ignore[arg-type]
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        ok = await self._service.add_member(team_id, user.id, rsn)
        if not ok:
            await interaction.response.send_message(
                f"Team {team_id} not found.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"{user.mention} (`{rsn}`) added to Team {team_id}.", ephemeral=True
        )

    @app_commands.command(
        name="removemember", description="Remove a member from their team"
    )
    async def team_removemember(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        if not self._service.is_host(interaction.user):  # type: ignore[arg-type]
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        ok = await self._service.remove_member(user.id)
        if not ok:
            await interaction.response.send_message(
                f"{user.mention} is not on any team.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"{user.mention} removed from their team.", ephemeral=True
        )

    @app_commands.command(name="rename", description="Rename a team and its channels")
    @app_commands.autocomplete(team_id=_autocomplete_team_id)
    async def team_rename(
        self, interaction: discord.Interaction, team_id: int, name: str
    ) -> None:
        if not self._service.is_host(interaction.user):  # type: ignore[arg-type]
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok = await self._service.rename_team(team_id, name)
        if not ok:
            await interaction.followup.send(
                f"Team {team_id} not found.", ephemeral=True
            )
            return
        await interaction.followup.send(
            f"Team {team_id} renamed to **{name}**.", ephemeral=True
        )


# ------------------------------------------------------------------
# /event top-level group
# ------------------------------------------------------------------


class EventGroup(app_commands.Group, name="event", description="Manage clan events"):
    """Slash commands for creating and managing clan events."""

    def __init__(self, service: "EventService") -> None:
        super().__init__()
        self._service = service
        self.add_command(_EventHostGroup(service))
        self.add_command(_EventTeamGroup(service))

    async def on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        await handle_check_failure(interaction, error)

    @app_commands.command(
        name="setup", description="Seed teams and create all event channels"
    )
    async def setup(self, interaction: discord.Interaction) -> None:
        if not self._service.is_host(interaction.user):  # type: ignore[arg-type]
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await self._service.setup_event(interaction)
        except Exception as e:
            logger.exception("Error during /event setup")
            await interaction.followup.send(f"Setup failed: {e}", ephemeral=True)

    @app_commands.command(name="teardown", description="Delete all event channels")
    async def teardown(self, interaction: discord.Interaction) -> None:
        if not self._service.is_host(interaction.user):  # type: ignore[arg-type]
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        await self._service.teardown_event(interaction)

    @app_commands.command(
        name="status", description="Show event name, active state, team count"
    )
    async def status(self, interaction: discord.Interaction) -> None:
        config = self._service._ensure_config()
        teams = self._service.get_all_teams()
        embed = discord.Embed(
            title=config.event_name,
            color=discord.Color.green() if config.event_active else discord.Color.red(),
        )
        embed.add_field(
            name="Status",
            value="Active" if config.event_active else "Inactive",
            inline=True,
        )
        embed.add_field(name="Teams", value=str(len(teams)), inline=True)
        total_members = sum(len(t.members) for t in teams)
        embed.add_field(name="Total Members", value=str(total_members), inline=True)
        await interaction.response.send_message(embed=embed)
