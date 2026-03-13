"""Pure service-loading functions; no access to DiscordClient internals."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from loguru import logger

from command_infra.help_registry import HelpRegistry

if TYPE_CHECKING:
    from bingo.service import BingoService
    from core.discord_client import DiscordClient
    from events.service import EventService


async def load_event_service(
    guild: discord.Guild,
    tree: app_commands.CommandTree,
    registry: HelpRegistry,
    mongo_uri: str,
    db_name: str,
    client: DiscordClient,
) -> EventService:
    """Initialise the event service and register its slash commands."""
    from events.commands import EventGroup
    from events.commands import register_help as register_event_help
    from events.repository import MongoEventRepository
    from events.service import EventService

    repo = MongoEventRepository(mongo_uri=mongo_uri, db_name=db_name)
    service = EventService(guild=guild, repo=repo, client=client)
    await service.initialize()

    register_event_help(registry)
    tree.add_command(EventGroup(service=service), guild=guild)
    logger.info("Event service initialised and commands registered")
    return service


async def load_bingo_service(
    guild: discord.Guild,
    tree: app_commands.CommandTree,
    registry: HelpRegistry,
    mongo_uri: str,
    db_name: str,
    client: DiscordClient,
    event_service: EventService,
) -> BingoService:
    """Initialise the bingo service and register its slash commands."""
    from bingo.commands import BingoGroup
    from bingo.commands import register_help as register_bingo_help
    from bingo.repository import BingoRepository
    from bingo.service import BingoService

    repo = BingoRepository(mongo_uri=mongo_uri, db_name=db_name)
    service = BingoService(
        guild=guild, repo=repo, event_service=event_service, client=client
    )
    await service.initialize()

    register_bingo_help(registry)
    tree.add_command(BingoGroup(service=service), guild=guild)
    logger.info("Bingo service initialised and commands registered")
    return service


def _load_help_command(
    guild: discord.Guild,
    tree: app_commands.CommandTree,
    registry: HelpRegistry,
) -> None:
    from command_infra.help import make_help_command, register_help

    register_help(registry)
    tree.add_command(make_help_command(registry), guild=guild)
    logger.info("Help command registered")


async def load_all_services(
    guild: discord.Guild,
    tree: app_commands.CommandTree,
    registry: HelpRegistry,
    client: DiscordClient,
    mongo_uri: str,
    db_name: str,
) -> tuple[EventService, BingoService]:
    """Load all services, then register the help command.

    Event service is loaded first; bingo service depends on it.
    """
    event = await load_event_service(guild, tree, registry, mongo_uri, db_name, client)
    bingo = await load_bingo_service(
        guild, tree, registry, mongo_uri, db_name, client, event
    )
    _load_help_command(guild, tree, registry)
    return event, bingo
