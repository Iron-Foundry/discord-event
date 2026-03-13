"""Pillow-based renderer that overlays tile status markers onto the board PNG."""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from bingo.models import TileStatus
from common.tiles import TILE_PIXEL_POSITIONS

if TYPE_CHECKING:
    from bingo.models import TeamBoard

_ASSETS_DIR = Path(__file__).parent.parent / "common" / "bingo_assets"
_BASE_IMAGE = _ASSETS_DIR / "BingoBoardNoCoords-1920x1080.png"
_MARKER_PATHS = {
    TileStatus.COMPLETE: _ASSETS_DIR / "CompletedTileMarker.png",
    TileStatus.IN_REVIEW: _ASSETS_DIR / "InProgressMarker.png",
}

# Module-level cache: loaded on first use
_marker_cache: dict[TileStatus, Image.Image] = {}


def _get_marker(status: TileStatus) -> Image.Image | None:
    if status not in _MARKER_PATHS:
        return None
    if status not in _marker_cache:
        _marker_cache[status] = Image.open(_MARKER_PATHS[status]).convert("RGBA")
    return _marker_cache[status]


def _render_with_states(tile_states: dict[str, TileStatus]) -> Image.Image:
    """Composite all markers onto the base board. Returns an RGBA Image."""
    base = Image.open(_BASE_IMAGE).convert("RGBA")

    for r in range(1, 8):
        for c in range(1, 8):
            key = f"{r},{c}"
            status = tile_states.get(key, TileStatus.INCOMPLETE)

            marker = _get_marker(status)
            if marker is None:
                continue

            y_px, x_px = TILE_PIXEL_POSITIONS[(r, c)]
            paste_x = x_px - marker.width // 2
            paste_y = y_px - marker.height // 2

            layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
            layer.paste(marker, (paste_x, paste_y))
            base = Image.alpha_composite(base, layer)

    return base


def render_board(board: TeamBoard) -> bytes:
    """Render the 7×7 bingo board with status markers and return PNG bytes.

    Markers are centered on each tile's pixel position from TILE_PIXEL_POSITIONS.
    COMPLETE tiles get CompletedTileMarker.png, IN_REVIEW tiles get
    InProgressMarker.png, and INCOMPLETE tiles receive no overlay.
    """
    tile_states = {key: state.status for key, state in board.tile_states.items()}
    img = _render_with_states(tile_states)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def render_test_board(tile_states: dict[str, TileStatus]) -> bytes:
    """Render a test board with a legend panel on the right listing marked tiles.

    The output image is wider than the standard board: 1920+320 = 2240px wide.
    The right panel shows which tiles are COMPLETE and which are IN_REVIEW.
    """
    board_img = _render_with_states(tile_states)

    # Append a dark legend panel to the right of the board
    PANEL_W = 320
    canvas = Image.new("RGBA", (board_img.width + PANEL_W, board_img.height), (15, 15, 15, 255))
    canvas.paste(board_img, (0, 0))

    draw = ImageDraw.Draw(canvas)
    panel_x = board_img.width

    # Separator line
    draw.line([(panel_x, 0), (panel_x, canvas.height)], fill=(70, 70, 70, 255), width=2)

    # Fonts (Pillow 10+ supports load_default(size=N))
    try:
        font_title = ImageFont.load_default(size=22)
        font_head = ImageFont.load_default(size=18)
        font_body = ImageFont.load_default(size=16)
    except TypeError:  # older Pillow fallback
        font_title = font_head = font_body = ImageFont.load_default()

    complete = sorted(k for k, s in tile_states.items() if s == TileStatus.COMPLETE)
    in_review = sorted(k for k, s in tile_states.items() if s == TileStatus.IN_REVIEW)

    x = panel_x + 16
    y = 20

    draw.text((x, y), "TEST BOARD", font=font_title, fill=(255, 255, 255, 255))
    y += 30
    draw.text((x, y), f"Marked: {len(tile_states)} / 49", font=font_body, fill=(160, 160, 160, 255))
    y += 36

    draw.text((x, y), f"■ COMPLETE  ({len(complete)})", font=font_head, fill=(80, 255, 120, 255))
    y += 26
    for key in complete:
        draw.text((x + 14, y), f"({key})", font=font_body, fill=(190, 255, 200, 255))
        y += 21
    y += 12

    draw.text((x, y), f"○ IN REVIEW  ({len(in_review)})", font=font_head, fill=(80, 180, 255, 255))
    y += 26
    for key in in_review:
        draw.text((x + 14, y), f"({key})", font=font_body, fill=(180, 220, 255, 255))
        y += 21

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()
