from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import discord
from loguru import logger

from core.service_base import Service
from events.models import EventConfig, HostAccessGrant, Team, TeamMember
from events.repository import MongoEventRepository
from events.seeder import load_teams_from_json

if TYPE_CHECKING:
    from core.discord_client import DiscordClient

_24H = 86400  # seconds


class EventService(Service):
    """Manages clan events for the Iron Foundry."""

    def __init__(
        self,
        guild: discord.Guild,
        repo: MongoEventRepository,
        client: DiscordClient,
    ) -> None:
        self._guild = guild
        self._repo = repo
        self._client = client
        self._config: EventConfig | None = None
        self._teams: dict[int, Team] = {}
        self._team_channels: set[int] = set()
        # (channel_id, user_id) → revocation task
        self._host_grants: dict[tuple[int, int], asyncio.Task] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Load config and ensure DB indexes."""
        await self._repo.ensure_indexes()
        self._config = await self._repo.get_config(self._guild.id)
        logger.info("EventService initialised")

    async def post_ready(self) -> None:
        """Re-attach to live guild state after on_ready."""
        self._config = await self._repo.get_config(self._guild.id)
        teams = await self._repo.get_all_teams(self._guild.id)
        self._teams = {t.team_id: t for t in teams}
        self._rebuild_channel_set()

        grants = await self._repo.get_active_grants(self._guild.id)
        now = datetime.now(UTC)
        for grant in grants:
            remaining = max(0.0, (grant.expires_at - now).total_seconds())
            channel = self._guild.get_channel(grant.channel_id)
            member = self._guild.get_member(grant.host_user_id)
            if channel and member:
                task = asyncio.create_task(
                    self._revoke_after(channel, member, grant, remaining)
                )
                self._host_grants[(grant.channel_id, grant.host_user_id)] = task
        logger.info(f"EventService post_ready: {len(self._teams)} teams loaded")

        self._client.add_listener(self._handle_message, "on_message")

    def _rebuild_channel_set(self) -> None:
        """Rebuild the fast-lookup set of team channel IDs."""
        self._team_channels = set()
        for team in self._teams.values():
            for ch_id in (
                team.general_channel_id,
                team.forum_channel_id,
                team.board_channel_id,
            ):
                if ch_id is not None:
                    self._team_channels.add(ch_id)

    # ------------------------------------------------------------------
    # Host checks
    # ------------------------------------------------------------------

    def is_host(self, member: discord.Member) -> bool:
        """Return True if member is a configured event host."""
        if self._config is None:
            return False
        if member.id in self._config.host_user_ids:
            return True
        if self._config.host_role_id is not None:
            return any(r.id == self._config.host_role_id for r in member.roles)
        return False

    # ------------------------------------------------------------------
    # Host management
    # ------------------------------------------------------------------

    async def add_host(self, user_id: int) -> None:
        """Add a user to the host list."""
        config = self._ensure_config()
        if user_id not in config.host_user_ids:
            config.host_user_ids.append(user_id)
            await self._repo.save_config(config)

    async def remove_host(self, user_id: int) -> None:
        """Remove a user from the host list."""
        config = self._ensure_config()
        if user_id in config.host_user_ids:
            config.host_user_ids.remove(user_id)
            await self._repo.save_config(config)

    async def set_host_role(self, role_id: int | None) -> None:
        """Set the Discord role used as fallback for host checks."""
        config = self._ensure_config()
        config.host_role_id = role_id
        await self._repo.save_config(config)

    # ------------------------------------------------------------------
    # Event setup / teardown
    # ------------------------------------------------------------------

    async def setup_event(self, interaction: discord.Interaction) -> None:
        """Seed teams and create all Discord channels."""
        config = self._ensure_config()

        if config.category_id is not None:
            await interaction.followup.send(
                "Event channels already exist. Run `/event teardown` first.",
                ephemeral=True,
            )
            return

        guild = self._guild

        senior_staff_role = self._get_senior_staff_role()
        bot_member = guild.me

        teams = load_teams_from_json(guild.id)
        for team in teams:
            await self._repo.upsert_team(team)
            self._teams[team.team_id] = team

        # Create main category
        category = await guild.create_category(config.event_name)
        config.category_id = category.id

        # general (event-wide, read-only for @everyone, hosts can send)
        general_overwrites = self._make_general_overwrites(
            guild, senior_staff_role, bot_member
        )
        general_ch = await guild.create_text_channel(
            "general", category=category, overwrites=general_overwrites
        )
        config.general_channel_id = general_ch.id

        # event-staff (hidden from everyone except Senior Staff + hosts)
        staff_overwrites = self._make_staff_overwrites(
            guild, senior_staff_role, bot_member
        )
        staff_ch = await guild.create_text_channel(
            "event-staff", category=category, overwrites=staff_overwrites
        )
        config.staff_channel_id = staff_ch.id

        config.event_active = True
        await self._repo.save_config(config)

        # Create team roles + channels
        for team in teams:
            team_role = await guild.create_role(
                name=team.name, mentionable=True, reason="Bingo event team role"
            )
            team.role_id = team_role.id

            # Assign role to all members already in the guild
            for tm in team.members:
                member = guild.get_member(tm.discord_user_id)
                if member:
                    try:
                        await member.add_roles(
                            team_role, reason="Bingo event team assignment"
                        )
                    except discord.HTTPException as e:
                        logger.warning(f"Could not assign role to {member}: {e}")

            gen_ch, forum_ch, board_ch, vc_ch = await self._create_team_channels(
                guild, category, team, team_role, senior_staff_role, bot_member
            )
            team.general_channel_id = gen_ch.id
            team.forum_channel_id = forum_ch.id
            team.board_channel_id = board_ch.id
            team.voice_channel_id = vc_ch.id
            await self._repo.upsert_team(team)
            self._teams[team.team_id] = team

        self._rebuild_channel_set()

        await interaction.followup.send(
            f"Event **{config.event_name}** set up with {len(teams)} teams "
            f"and {2 + len(teams) * 4} channels.",
            ephemeral=True,
        )
        logger.info(f"Event setup complete: {len(teams)} teams")

    async def teardown_event(self, interaction: discord.Interaction) -> None:
        """Delete all event channels after ephemeral confirmation."""
        view = _ConfirmTeardownView(self)
        await interaction.response.send_message(
            "Are you sure you want to delete all event channels?",
            view=view,
            ephemeral=True,
        )

    async def _do_teardown(self) -> None:
        """Execute the actual channel deletion."""
        config = self._ensure_config()

        # Cancel all host grants
        for task in self._host_grants.values():
            task.cancel()
        self._host_grants.clear()

        guild = self._guild
        category = guild.get_channel(config.category_id) if config.category_id else None

        if category and isinstance(category, discord.CategoryChannel):
            for ch in list(category.channels):
                try:
                    await ch.delete()
                except discord.HTTPException:
                    pass
            try:
                await category.delete()
            except discord.HTTPException:
                pass

        config.category_id = None
        config.general_channel_id = None
        config.staff_channel_id = None
        config.event_active = False
        await self._repo.save_config(config)

        # Delete team roles and clear stored IDs
        for team in self._teams.values():
            if team.role_id:
                role = guild.get_role(team.role_id)
                if role:
                    try:
                        await role.delete(reason="Bingo event teardown")
                    except discord.HTTPException:
                        pass
            team.role_id = None
            team.general_channel_id = None
            team.forum_channel_id = None
            team.board_channel_id = None
            team.voice_channel_id = None
            await self._repo.upsert_team(team)

        self._rebuild_channel_set()
        logger.info("Event teardown complete")

    # ------------------------------------------------------------------
    # Team mutations
    # ------------------------------------------------------------------

    async def set_captain(self, team_id: int, discord_user_id: int) -> bool:
        """Designate a captain; clears any previous captain. Returns False if user not on team."""
        team = self._teams.get(team_id)
        if team is None:
            return False
        found = False
        for m in team.members:
            m.is_captain = m.discord_user_id == discord_user_id
            if m.is_captain:
                found = True
        if not found:
            return False
        await self._repo.upsert_team(team)
        return True

    async def add_member(self, team_id: int, discord_user_id: int, rsn: str) -> bool:
        """Add a member to a team. Returns False if team not found."""
        team = self._teams.get(team_id)
        if team is None:
            return False
        team.members.append(TeamMember(discord_user_id=discord_user_id, rsn=rsn))
        await self._repo.upsert_team(team)
        if team.role_id:
            member = self._guild.get_member(discord_user_id)
            role = self._guild.get_role(team.role_id)
            if member and role:
                try:
                    await member.add_roles(role, reason="Added to bingo team")
                except discord.HTTPException as e:
                    logger.warning(f"Could not assign team role to {member}: {e}")
        return True

    async def remove_member(self, discord_user_id: int) -> bool:
        """Remove a member from whichever team they belong to. Returns False if not found."""
        for team in self._teams.values():
            for m in team.members:
                if m.discord_user_id == discord_user_id:
                    team.members.remove(m)
                    await self._repo.upsert_team(team)
                    if team.role_id:
                        member = self._guild.get_member(discord_user_id)
                        role = self._guild.get_role(team.role_id)
                        if member and role:
                            try:
                                await member.remove_roles(
                                    role, reason="Removed from bingo team"
                                )
                            except discord.HTTPException as e:
                                logger.warning(
                                    f"Could not remove team role from {member}: {e}"
                                )
                    return True
        return False

    async def rename_team(self, team_id: int, name: str) -> bool:
        """Rename a team and its Discord channels if they exist."""
        team = self._teams.get(team_id)
        if team is None:
            return False
        old_name = team.name
        team.name = name
        await self._repo.upsert_team(team)

        # Rename Discord role if it exists
        if team.role_id:
            role = self._guild.get_role(team.role_id)
            if role:
                try:
                    await role.edit(name=name, reason="Bingo team renamed")
                except discord.HTTPException as e:
                    logger.warning(f"Could not rename team role {team.role_id}: {e}")

        # Rename Discord channels if they exist
        if team.general_channel_id:
            await self._rename_channel(
                team.general_channel_id, old_name, name, "general"
            )
        if team.forum_channel_id:
            await self._rename_channel(team.forum_channel_id, old_name, name, "forum")
        if team.board_channel_id:
            await self._rename_channel(team.board_channel_id, old_name, name, "board")
        if team.voice_channel_id:
            await self._rename_channel(team.voice_channel_id, old_name, name, "")
        return True

    async def _rename_channel(
        self, channel_id: int, old_team_name: str, new_team_name: str, suffix: str
    ) -> None:
        """Rename a Discord channel based on old and new team names."""
        channel = self._guild.get_channel(channel_id)
        if channel is None:
            return
        old_slug = old_team_name.lower().replace(" ", "-")
        new_slug = new_team_name.lower().replace(" ", "-")
        new_ch_name = f"{new_slug}-{suffix}" if suffix else new_slug
        old_ch_name = f"{old_slug}-{suffix}" if suffix else old_slug
        if channel.name == old_ch_name:
            try:
                await channel.edit(name=new_ch_name)
            except discord.HTTPException as e:
                logger.warning(f"Could not rename channel {channel_id}: {e}")

    # ------------------------------------------------------------------
    # on_message handler: host mention → temporary access
    # ------------------------------------------------------------------

    async def _handle_message(self, message: discord.Message) -> None:
        """Grant temporary host access when a host is @mentioned in a team channel."""
        if message.author.bot:
            return
        if not message.guild:
            return

        channel_id = message.channel.id
        # Check if this is a team text channel OR a thread inside a team forum
        effective_channel_id = channel_id
        if isinstance(message.channel, discord.Thread) and message.channel.parent_id:
            effective_channel_id = message.channel.parent_id

        if effective_channel_id not in self._team_channels:
            return

        # Resolve the actual text/forum channel for permission edits
        target_channel = self._guild.get_channel(effective_channel_id)
        if target_channel is None:
            return

        for mentioned in message.mentions:
            if not isinstance(mentioned, discord.Member):
                continue
            if not self.is_host(mentioned):
                continue

            key = (effective_channel_id, mentioned.id)
            if key in self._host_grants:
                continue  # already granted

            now = datetime.now(UTC)
            expires_at = now + timedelta(seconds=_24H)
            grant = HostAccessGrant(
                guild_id=self._guild.id,
                channel_id=effective_channel_id,
                host_user_id=mentioned.id,
                granted_at=now,
                expires_at=expires_at,
            )

            try:
                await target_channel.set_permissions(
                    mentioned,
                    view_channel=True,
                    send_messages=True,
                )
            except discord.HTTPException as e:
                logger.warning(f"Could not grant host access to {mentioned}: {e}")
                continue

            await self._repo.save_host_grant(grant)
            task = asyncio.create_task(
                self._revoke_after(target_channel, mentioned, grant, _24H)
            )
            self._host_grants[key] = task
            logger.info(
                f"Host {mentioned} granted 24h access to channel {effective_channel_id}"
            )

    async def _revoke_after(
        self,
        channel: discord.abc.GuildChannel,
        host_member: discord.Member,
        grant: HostAccessGrant,
        delay: float,
    ) -> None:
        """Wait delay seconds then revoke host access."""
        await asyncio.sleep(delay)
        await self._revoke_host_access(channel, host_member, grant)

    async def _revoke_host_access(
        self,
        channel: discord.abc.GuildChannel,
        host_member: discord.Member,
        grant: HostAccessGrant,
    ) -> None:
        """Remove host permission overwrite and clean up grant."""
        try:
            await channel.set_permissions(host_member, overwrite=None)
        except discord.HTTPException as e:
            logger.warning(f"Could not revoke host access for {host_member}: {e}")

        await self._repo.delete_host_grant(
            grant.guild_id, grant.channel_id, grant.host_user_id
        )
        self._host_grants.pop((grant.channel_id, grant.host_user_id), None)
        logger.info(f"Host {host_member} access revoked from channel {channel.id}")

    # ------------------------------------------------------------------
    # Channel creation helpers
    # ------------------------------------------------------------------

    async def _create_team_channels(
        self,
        guild: discord.Guild,
        category: discord.CategoryChannel,
        team: Team,
        team_role: discord.Role,
        senior_staff_role: discord.Role | None,
        bot_member: discord.Member,
    ) -> tuple[
        discord.TextChannel,
        discord.ForumChannel,
        discord.TextChannel,
        discord.VoiceChannel,
    ]:
        """Create the 4 channels for a single team using team_role for access control."""
        slug = team.name.lower().replace(" ", "-")

        hidden = discord.PermissionOverwrite(view_channel=False)
        team_perms = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            send_messages_in_threads=True,
            create_public_threads=True,
            attach_files=True,
            embed_links=True,
            add_reactions=True,
            pin_messages=True,
        )
        staff_full = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_messages=True,
            attach_files=True,
        )
        bot_full = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_messages=True,
            attach_files=True,
            manage_channels=True,
        )

        def text_overwrites() -> dict[
            discord.abc.Snowflake, discord.PermissionOverwrite
        ]:
            ow: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
                guild.default_role: hidden,
                team_role: team_perms,
                bot_member: bot_full,
            }
            if senior_staff_role:
                ow[senior_staff_role] = staff_full
            return ow

        gen_ch = await guild.create_text_channel(
            f"{slug}-general", category=category, overwrites=text_overwrites()
        )
        forum_ch = await guild.create_forum(
            f"{slug}-forum", category=category, overwrites=text_overwrites()
        )
        board_ch = await guild.create_text_channel(
            f"{slug}-board", category=category, overwrites=text_overwrites()
        )

        # Voice: visible to all but only team role + staff can connect
        vc_overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=True, connect=False
            ),
            team_role: discord.PermissionOverwrite(
                view_channel=True, connect=True, speak=True
            ),
            bot_member: discord.PermissionOverwrite(
                view_channel=True, connect=True, speak=True, manage_channels=True
            ),
        }
        if senior_staff_role:
            vc_overwrites[senior_staff_role] = discord.PermissionOverwrite(
                view_channel=True, connect=True, speak=True, manage_channels=True
            )

        vc_ch = await guild.create_voice_channel(
            slug, category=category, overwrites=vc_overwrites
        )

        return gen_ch, forum_ch, board_ch, vc_ch

    def _make_general_overwrites(
        self,
        guild: discord.Guild,
        senior_staff_role: discord.Role | None,
        bot_member: discord.Member,
    ) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
        """Overwrites for the event-wide general channel."""
        ow: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=True, send_messages=False
            ),
            bot_member: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True
            ),
        }
        if senior_staff_role:
            ow[senior_staff_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True
            )
        return ow

    def _make_staff_overwrites(
        self,
        guild: discord.Guild,
        senior_staff_role: discord.Role | None,
        bot_member: discord.Member,
    ) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
        """Overwrites for the event-staff channel."""
        ow: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            bot_member: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True
            ),
        }
        if senior_staff_role:
            ow[senior_staff_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True
            )
        return ow

    def _get_senior_staff_role(self) -> discord.Role | None:
        """Look up the Senior Staff role from env, if configured."""
        role_id_str = os.getenv("SENIOR_STAFF_ROLE_ID")
        if not role_id_str:
            return None
        role_id = int(role_id_str)
        return self._guild.get_role(role_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_config(self) -> EventConfig:
        """Return config, creating a default one if none exists yet."""
        if self._config is None:
            self._config = EventConfig(guild_id=self._guild.id)
        return self._config

    def get_all_teams(self) -> list[Team]:
        """Return all teams sorted by team_id."""
        return sorted(self._teams.values(), key=lambda t: t.team_id)


# ------------------------------------------------------------------
# Teardown confirmation view
# ------------------------------------------------------------------


class _ConfirmTeardownView(discord.ui.View):
    """Ephemeral confirmation buttons for event teardown."""

    def __init__(self, service: EventService) -> None:
        super().__init__(timeout=60)
        self._service = service

    @discord.ui.button(label="Confirm Teardown", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:  # noqa: ARG002
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self._service._do_teardown()
        await interaction.followup.send("Event channels deleted.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:  # noqa: ARG002
        await interaction.response.send_message("Cancelled.", ephemeral=True)
        self.stop()
