"""Pure functions that generate plotly chart images for bingo event stats."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import TYPE_CHECKING

import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from bingo.models import SubmissionStatus, TileStatus

if TYPE_CHECKING:
    from bingo.models import TeamBoard, TileSubmission
    from bingo.tile_defs import TileDefinition


def _date_range(start: date, end: date) -> list[date]:
    """Return inclusive list of dates from start to end."""
    days = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def render_submissions_chart(
    subs: list[TileSubmission],
    title: str,
    time_label: str,
) -> bytes:
    """Grouped bar chart of approved vs rejected submissions per day."""
    filtered = [
        s for s in subs
        if s.status in (SubmissionStatus.APPROVED, SubmissionStatus.REJECTED)
    ]

    if not filtered:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            title=f"{title} — No Data",
            annotations=[{"text": "No approved or rejected submissions found.", "showarrow": False, "font": {"size": 16}}],
        )
        return pio.to_image(fig, format="png", width=1000, height=600)

    approved_by_day: Counter[date] = Counter()
    rejected_by_day: Counter[date] = Counter()
    for s in filtered:
        d = s.submitted_at.date()
        if s.status == SubmissionStatus.APPROVED:
            approved_by_day[d] += 1
        else:
            rejected_by_day[d] += 1

    all_dates = sorted(approved_by_day.keys() | rejected_by_day.keys())
    date_range = _date_range(all_dates[0], all_dates[-1])
    labels = [d.strftime("%b %d") for d in date_range]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Approved",
        x=labels,
        y=[approved_by_day.get(d, 0) for d in date_range],
        marker_color="#2ecc71",
    ))
    fig.add_trace(go.Bar(
        name="Rejected",
        x=labels,
        y=[rejected_by_day.get(d, 0) for d in date_range],
        marker_color="#e74c3c",
    ))
    fig.update_layout(
        template="plotly_dark",
        title=f"{title} ({time_label})",
        barmode="group",
        xaxis_title="Date",
        yaxis_title="Submissions",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    return pio.to_image(fig, format="png", width=1000, height=600)


def render_tiles_chart(
    boards: list[TeamBoard],
    title: str,
    time_label: str,
) -> bytes:
    """Bar chart of tiles completed per day."""
    completions_by_day: Counter[date] = Counter()
    for board in boards:
        for state in board.tile_states.values():
            if state.status == TileStatus.COMPLETE and state.completed_at is not None:
                completions_by_day[state.completed_at.date()] += 1

    if not completions_by_day:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            title=f"{title} — No Data",
            annotations=[{"text": "No completed tiles found.", "showarrow": False, "font": {"size": 16}}],
        )
        return pio.to_image(fig, format="png", width=1000, height=600)

    all_dates = sorted(completions_by_day.keys())
    date_range = _date_range(all_dates[0], all_dates[-1])
    labels = [d.strftime("%b %d") for d in date_range]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Tiles Completed",
        x=labels,
        y=[completions_by_day.get(d, 0) for d in date_range],
        marker_color="#3498db",
    ))
    fig.update_layout(
        template="plotly_dark",
        title=f"{title} ({time_label})",
        xaxis_title="Date",
        yaxis_title="Tiles Completed",
    )
    return pio.to_image(fig, format="png", width=1000, height=600)


def render_leaderboard_chart(
    subs: list[TileSubmission],
    boards: list[TeamBoard],
    tile_defs: dict[str, TileDefinition],
) -> bytes:
    """Three-panel leaderboard: top items, top completed tiles, team standings."""
    # Panel 1: Top 10 most submitted items (all statuses)
    item_counts: Counter[str] = Counter()
    for s in subs:
        label = s.item_label or "(no label)"
        item_counts[label] += 1
    top_items = item_counts.most_common(10)
    top_items_labels = [item[0] for item in reversed(top_items)]
    top_items_values = [item[1] for item in reversed(top_items)]

    # Panel 2: Top 10 most completed tiles (# teams that completed it)
    tile_completions: Counter[str] = Counter()
    for board in boards:
        for key, state in board.tile_states.items():
            if state.status == TileStatus.COMPLETE:
                tile_completions[key] += 1
    top_tiles = tile_completions.most_common(10)
    top_tile_labels = [
        tile_defs[key].description[:40] if key in tile_defs else key
        for key, _ in reversed(top_tiles)
    ]
    top_tile_values = [count for _, count in reversed(top_tiles)]

    # Panel 3: Team comparison — approved submissions per team
    team_approved: Counter[int] = Counter()
    for s in subs:
        if s.status == SubmissionStatus.APPROVED:
            team_approved[s.team_id] += 1
    sorted_teams = sorted(team_approved.items(), key=lambda x: x[1], reverse=True)
    team_labels = [f"Team {tid}" for tid, _ in sorted_teams]
    team_values = [count for _, count in sorted_teams]

    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=("Top 10 Most Submitted Items", "Top 10 Most Completed Tiles", "Approved Submissions per Team"),
        vertical_spacing=0.12,
    )

    if top_items_labels:
        fig.add_trace(go.Bar(
            x=top_items_values, y=top_items_labels,
            orientation="h", marker_color="#9b59b6", showlegend=False,
        ), row=1, col=1)

    if top_tile_labels:
        fig.add_trace(go.Bar(
            x=top_tile_values, y=top_tile_labels,
            orientation="h", marker_color="#1abc9c", showlegend=False,
        ), row=2, col=1)

    if team_labels:
        fig.add_trace(go.Bar(
            x=team_labels, y=team_values,
            marker_color="#e67e22", showlegend=False,
        ), row=3, col=1)

    fig.update_layout(
        template="plotly_dark",
        title="Bingo Leaderboard",
        height=1400,
    )
    return pio.to_image(fig, format="png", width=1000, height=1400)
