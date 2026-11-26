# Changelog

All notable changes to discord-event are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

`pyproject.toml` holds the version and is the single source of truth for it.
Bump with `uv version --bump patch|minor` (or `alpha|beta|rc` for a
prerelease, `stable` to drop the tag). A MAJOR bump is the maintainer's call
and is never made automatically.

## [Unreleased]

### Removed

- The `/bingo`, `/bingo host` and `/bingo stats` commands, with tile submissions, the board image and the stats charts. The `/event` commands stay. The `bingo_*` Mongo collections keep their names and data.
- The pillow, plotly and kaleido dependencies, which only the bingo board and charts used.

### Changed

- The default event name is "Clan Event", and the role audit reasons and team titles say "event team".

## [0.1.1] - 2026-08-01

### Security

- aiohttp 3.13.3 -> 3.14.3, pillow 12.1.1 -> 12.3.0 and idna 3.11 -> 3.18,
  clearing all 40 Dependabot advisories. Lockfile only - no declared
  constraint moved, and `kaleido==0.2.1` / `plotly<6` are untouched, neither
  being a dependant of any upgraded package.

## [0.1.0] - 2026-07-28

Versioning baseline. Stays pre-1.0 until the service has a stable feature set.
