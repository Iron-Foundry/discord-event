# Iron Foundry — Discord Event Bot

Dedicated Discord bot for clan event management. Handles bingo events, team coordination,
and submission review workflows.

---

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (package manager)
- A running MongoDB instance

---

## Setup

1. Clone the repository and install dependencies:

   ```bash
   uv sync
   ```

2. Copy `.env.example` to `.env` and fill in the values.

3. Run the bot:

   ```bash
   uv run python main.py
   ```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | Yes | Bot token from the Discord Developer Portal. |
| `GUILD_ID` | Yes | The ID of the Discord server the bot operates in. |
| `MONGO_URI` | Yes | MongoDB connection string. |
| `MONGO_DB` | No | MongoDB database name. Defaults to `foundry`. |
| `STAFF_ROLE_ID` | Yes | Role ID for Staff. |
| `SENIOR_STAFF_ROLE_ID` | Yes | Role ID for Senior Staff. |
| `OWNER_ROLE_ID` | No | Role ID for Owners. |
| `DEBUG_MODE` | No | Enable debug logging. |

---

## Commands

| Group | Description |
|---|---|
| `/bingo` | Submit tile screenshots and view board progress. |
| `/bingo host` | Host tools — review, approve, and reject submissions. |
| `/event` | Create and manage clan events with team channels. |
| `/event host` | Manage event hosts and host role fallback. |
| `/event team` | Manage event teams and members. |
