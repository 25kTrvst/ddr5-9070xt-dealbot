from __future__ import annotations

import io
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # headless: no display server needed, just render to bytes

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

DISCORD_DARK = "#2b2d31"
LINE_COLOR = "#5865F2"
TEXT_COLOR = "#dbdee1"
GRID_COLOR = "#4e5058"


def render_price_history(points: list[tuple[str, float]], label: str) -> bytes | None:
    """Renders a small price-over-time line chart as PNG bytes, styled to sit
    naturally inside a dark Discord embed. Returns None when there isn't
    enough history yet to draw a meaningful trend."""
    if len(points) < 2:
        return None
    dates = [datetime.fromisoformat(ts) for ts, _ in points]
    prices = [price for _, price in points]

    fig, ax = plt.subplots(figsize=(6, 2.4), dpi=140)
    fig.patch.set_facecolor(DISCORD_DARK)
    ax.set_facecolor(DISCORD_DARK)

    ax.plot(dates, prices, color=LINE_COLOR, linewidth=1.8, marker="o", markersize=3)
    ax.set_title(f"{label} — price history", fontsize=10, color=TEXT_COLOR, loc="left")
    ax.set_ylabel("Price ($)", fontsize=8, color=TEXT_COLOR)
    ax.tick_params(labelsize=7, colors=TEXT_COLOR)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.grid(True, color=GRID_COLOR, alpha=0.4, linewidth=0.6)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    fig.autofmt_xdate()
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=DISCORD_DARK)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
