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
        s
        for s in subs
        if s.status in (SubmissionStatus.APPROVED, SubmissionStatus.REJECTED)
    ]

    if not filtered:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            title=f"{title} — No Data",
            annotations=[
                {
                    "text": "No approved or rejected submissions found.",
                    "showarrow": False,
                    "font": {"size": 16},
                }
            ],
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
    fig.add_trace(
        go.Bar(
            name="Approved",
            x=labels,
            y=[approved_by_day.get(d, 0) for d in date_range],
            marker_color="#2ecc71",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Rejected",
            x=labels,
            y=[rejected_by_day.get(d, 0) for d in date_range],
            marker_color="#e74c3c",
        )
    )
    fig.update_layout(
        template="plotly_dark",
        title=f"{title} ({time_label})",
        barmode="group",
        xaxis_title="Date",
        yaxis_title="Submissions",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
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
            annotations=[
                {
                    "text": "No completed tiles found.",
                    "showarrow": False,
                    "font": {"size": 16},
                }
            ],
        )
        return pio.to_image(fig, format="png", width=1000, height=600)

    all_dates = sorted(completions_by_day.keys())
    date_range = _date_range(all_dates[0], all_dates[-1])
    labels = [d.strftime("%b %d") for d in date_range]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Tiles Completed",
            x=labels,
            y=[completions_by_day.get(d, 0) for d in date_range],
            marker_color="#3498db",
        )
    )
    fig.update_layout(
        template="plotly_dark",
        title=f"{title} ({time_label})",
        xaxis_title="Date",
        yaxis_title="Tiles Completed",
    )
    return pio.to_image(fig, format="png", width=1000, height=600)


def _no_data_figure(title: str, msg: str = "No data found.") -> bytes:
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        title=f"{title} — No Data",
        annotations=[{"text": msg, "showarrow": False, "font": {"size": 16}}],
    )
    return pio.to_image(fig, format="png", width=1000, height=600)


def render_player_submissions_chart(
    subs: list[TileSubmission],
    player_names: dict[int, str],
    title: str,
    time_label: str,
    chart_type: str = "bar_grouped_h",
) -> list[bytes]:
    """Render approved/rejected submissions per player.

    Returns a list of PNG bytes — one image for most chart types, two for ``pie``
    (approved chart first, rejected chart second).
    """
    approved_by_player: Counter[int] = Counter()
    rejected_by_player: Counter[int] = Counter()
    for s in subs:
        if s.status == SubmissionStatus.APPROVED:
            approved_by_player[s.submitted_by] += 1
        elif s.status == SubmissionStatus.REJECTED:
            rejected_by_player[s.submitted_by] += 1

    all_players = sorted(
        approved_by_player.keys() | rejected_by_player.keys(),
        key=lambda uid: -(approved_by_player[uid] + rejected_by_player[uid]),
    )

    if not all_players:
        return [_no_data_figure(title, "No submissions found.")]

    labels = [player_names.get(uid, f"User {uid}") for uid in all_players]
    approved_vals = [approved_by_player.get(uid, 0) for uid in all_players]
    rejected_vals = [rejected_by_player.get(uid, 0) for uid in all_players]
    total_vals = [a + r for a, r in zip(approved_vals, rejected_vals)]
    chart_title = f"{title} — By Player ({time_label})"
    legend_cfg = {
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.02,
        "xanchor": "right",
        "x": 1,
    }

    # ── Horizontal bars ────────────────────────────────────────────────
    if chart_type in ("bar_grouped_h", "bar_stacked_h"):
        height = max(400, 60 * len(all_players) + 150)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Approved", x=approved_vals, y=labels,
            orientation="h", marker_color="#2ecc71",
        ))
        fig.add_trace(go.Bar(
            name="Rejected", x=rejected_vals, y=labels,
            orientation="h", marker_color="#e74c3c",
        ))
        fig.update_layout(
            template="plotly_dark",
            title=chart_title,
            barmode="group" if chart_type == "bar_grouped_h" else "stack",
            xaxis_title="Submissions",
            yaxis={"autorange": "reversed"},
            legend=legend_cfg,
            height=height,
        )
        return [pio.to_image(fig, format="png", width=1000, height=height)]

    # ── Vertical bars ──────────────────────────────────────────────────
    if chart_type in ("bar_grouped_v", "bar_stacked_v"):
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Approved", x=labels, y=approved_vals, marker_color="#2ecc71",
        ))
        fig.add_trace(go.Bar(
            name="Rejected", x=labels, y=rejected_vals, marker_color="#e74c3c",
        ))
        fig.update_layout(
            template="plotly_dark",
            title=chart_title,
            barmode="group" if chart_type == "bar_grouped_v" else "stack",
            xaxis_title="Player",
            yaxis_title="Submissions",
            xaxis_tickangle=-45,
            legend=legend_cfg,
        )
        return [pio.to_image(fig, format="png", width=1000, height=600)]

    # ── Pie charts (one per status) ────────────────────────────────────
    if chart_type == "pie":
        results: list[bytes] = []
        for status_label, vals, color in [
            ("Approved", approved_vals, "#2ecc71"),
            ("Rejected", rejected_vals, "#e74c3c"),
        ]:
            players_with_data = [(l, v) for l, v in zip(labels, vals) if v > 0]
            if not players_with_data:
                results.append(_no_data_figure(
                    f"{title} — {status_label}",
                    f"No {status_label.lower()} submissions.",
                ))
                continue
            pie_labels = [p[0] for p in players_with_data]
            pie_vals = [p[1] for p in players_with_data]
            fig = go.Figure(go.Pie(
                labels=pie_labels,
                values=pie_vals,
                textinfo="label+percent",
                hole=0.3,
                marker_colors=[color] * len(pie_labels),
            ))
            fig.update_traces(
                marker={"colors": None},  # let Plotly pick distinct colours
            )
            fig.update_layout(
                template="plotly_dark",
                title=f"{title} — {status_label} by Player ({time_label})",
            )
            results.append(pio.to_image(fig, format="png", width=1000, height=600))
        return results

    # ── Scatter: approved (x) vs rejected (y), bubble = total ─────────
    if chart_type == "scatter":
        approval_rates = [a / t if t > 0 else 0.0 for a, t in zip(approved_vals, total_vals)]
        fig = go.Figure(go.Scatter(
            x=approved_vals,
            y=rejected_vals,
            mode="markers+text",
            text=labels,
            textposition="top center",
            marker={
                "size": [max(12, t * 3) for t in total_vals],
                "color": approval_rates,
                "colorscale": "RdYlGn",
                "cmin": 0,
                "cmax": 1,
                "showscale": True,
                "colorbar": {"title": "Approval Rate"},
                "line": {"width": 1, "color": "white"},
            },
        ))
        fig.update_layout(
            template="plotly_dark",
            title=chart_title,
            xaxis_title="Approved",
            yaxis_title="Rejected",
        )
        return [pio.to_image(fig, format="png", width=1000, height=600)]

    # ── Treemap: area = total, colour = approval % ─────────────────────
    if chart_type == "treemap":
        approval_pct = [round(a / t * 100, 1) if t > 0 else 0.0 for a, t in zip(approved_vals, total_vals)]
        fig = go.Figure(go.Treemap(
            labels=labels,
            parents=[""] * len(labels),
            values=total_vals,
            customdata=list(zip(approved_vals, rejected_vals, approval_pct)),
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Total: %{value}<br>"
                "Approved: %{customdata[0]}<br>"
                "Rejected: %{customdata[1]}<br>"
                "Approval: %{customdata[2]}%"
                "<extra></extra>"
            ),
            marker={
                "colors": approval_pct,
                "colorscale": "RdYlGn",
                "cmin": 0,
                "cmax": 100,
                "showscale": True,
                "colorbar": {"title": "Approval %"},
            },
        ))
        fig.update_layout(template="plotly_dark", title=chart_title)
        return [pio.to_image(fig, format="png", width=1000, height=600)]

    # ── Sunburst: status → player hierarchy ───────────────────────────
    if chart_type == "sunburst":
        approved_total = sum(approved_vals)
        rejected_total = sum(rejected_vals)
        ids = ["root", "approved", "rejected"]
        sun_labels = ["All", "Approved", "Rejected"]
        parents = ["", "root", "root"]
        values = [approved_total + rejected_total, approved_total, rejected_total]
        colors = ["#888888", "#2ecc71", "#e74c3c"]
        for uid, label, a, r in zip(all_players, labels, approved_vals, rejected_vals):
            if a > 0:
                ids.append(f"a_{uid}")
                sun_labels.append(label)
                parents.append("approved")
                values.append(a)
                colors.append("#2ecc71")
            if r > 0:
                ids.append(f"r_{uid}")
                sun_labels.append(label)
                parents.append("rejected")
                values.append(r)
                colors.append("#e74c3c")
        fig = go.Figure(go.Sunburst(
            ids=ids,
            labels=sun_labels,
            parents=parents,
            values=values,
            marker_colors=colors,
            branchvalues="total",
        ))
        fig.update_layout(template="plotly_dark", title=chart_title)
        return [pio.to_image(fig, format="png", width=1000, height=600)]

    return [_no_data_figure(title, f"Unknown chart type: {chart_type}")]


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
        rows=3,
        cols=1,
        subplot_titles=(
            "Top 10 Most Submitted Items",
            "Top 10 Most Completed Tiles",
            "Approved Submissions per Team",
        ),
        vertical_spacing=0.12,
    )

    if top_items_labels:
        fig.add_trace(
            go.Bar(
                x=top_items_values,
                y=top_items_labels,
                orientation="h",
                marker_color="#9b59b6",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

    if top_tile_labels:
        fig.add_trace(
            go.Bar(
                x=top_tile_values,
                y=top_tile_labels,
                orientation="h",
                marker_color="#1abc9c",
                showlegend=False,
            ),
            row=2,
            col=1,
        )

    if team_labels:
        fig.add_trace(
            go.Bar(
                x=team_labels,
                y=team_values,
                marker_color="#e67e22",
                showlegend=False,
            ),
            row=3,
            col=1,
        )

    fig.update_layout(
        template="plotly_dark",
        title="Bingo Leaderboard",
        height=1400,
    )
    return pio.to_image(fig, format="png", width=1000, height=1400)
