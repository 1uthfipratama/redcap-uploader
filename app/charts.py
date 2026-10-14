"""Quiet, consistent charts for the Explore screen (matplotlib, imported lazily).

One look everywhere: thin bars with a small gap, hairline grid on the value axis
only, no top or right frame, text in ink colours (never the series colour),
the brand blue for a single series, grey for "unknown", "blank" and "other".
Every chart sits next to a table with the same numbers.
"""

from __future__ import annotations

from app.theme import Brand

BAR_HEIGHT = 0.6  # share of the slot a bar fills; the rest is air
ROW_PX = 30  # height per bar in horizontal charts
MIN_PX = 300


class Chart:
    """A matplotlib figure inside a Qt widget. Created only when the Explore screen opens."""

    def __init__(self, brand: Brand):
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        self.brand = brand
        self.figure = Figure(figsize=(7.2, 3.4), dpi=100, facecolor=brand.colors["surface"])
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(300)

    # ---- shared look -----------------------------------------------------------
    def _axes(self, value_axis: str):
        c, chart = self.brand.colors, self.brand.chart
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(c["surface"])
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(chart["grid"])
            ax.spines[side].set_linewidth(1)
        ax.tick_params(colors=c["muted"], labelsize=9, length=0)
        ax.grid(axis=value_axis, color=chart["grid"], linewidth=1, linestyle="-")
        ax.set_axisbelow(True)
        return ax

    def _label(self, ax, xlabel: str = "", ylabel: str = "") -> None:
        muted = self.brand.colors["muted"]
        if xlabel:
            ax.set_xlabel(xlabel, color=muted, fontsize=9)
        if ylabel:
            ax.set_ylabel(ylabel, color=muted, fontsize=9)

    def fit_rows(self, rows: int, extra: int = 110) -> None:
        """Horizontal charts get taller with more bars instead of squeezing them."""
        self.canvas.setMinimumHeight(max(MIN_PX, rows * ROW_PX + extra))

    def draw(self) -> None:
        self.figure.tight_layout(pad=1.2)
        self.canvas.draw_idle()

    def save_png(self, path: str) -> None:
        self.figure.savefig(path, dpi=200, facecolor=self.brand.colors["surface"], bbox_inches="tight")

    def message(self, text: str) -> None:
        self.figure.clear()
        self.figure.text(0.5, 0.5, text, ha="center", va="center", color=self.brand.colors["muted"], fontsize=10)
        self.canvas.draw_idle()

    # ---- forms -------------------------------------------------------------------
    def histogram(self, starts, ends, counts, xlabel: str, ylabel: str) -> None:
        self.canvas.setMinimumHeight(MIN_PX)
        ax = self._axes("y")
        widths = [(e - s) for s, e in zip(starts, ends)]
        ax.bar(starts, counts, width=[w * 0.92 for w in widths], align="edge", color=self.brand.chart["series"][0])
        self._label(ax, xlabel, ylabel)
        self.draw()

    def horizontal_bars(self, labels, values, value_text, neutral_mask, xlabel: str) -> None:
        """One bar per category, in the form's order from the top; context categories in grey."""
        self.fit_rows(len(labels))
        ax = self._axes("x")
        colors = [self.brand.chart["neutral"] if n else self.brand.chart["series"][0] for n in neutral_mask]
        positions = list(range(len(labels)))[::-1]
        ax.barh(positions, values, height=BAR_HEIGHT, color=colors)
        ax.set_yticks(positions, labels)
        top = max(values) if len(values) else 0
        for y, v, text in zip(positions, values, value_text):
            ax.text(v + top * 0.01, y, text, va="center", fontsize=9, color=self.brand.colors["text"])
        ax.set_xlim(0, top * 1.18 if top else 1)
        self._label(ax, xlabel)
        self.draw()

    def columns(self, labels, values, ylabel: str) -> None:
        self.canvas.setMinimumHeight(MIN_PX)
        ax = self._axes("y")
        ax.bar(range(len(labels)), values, width=BAR_HEIGHT, color=self.brand.chart["series"][0])
        step = max(1, len(labels) // 12)
        ax.set_xticks(range(0, len(labels), step), labels[::step], rotation=0)
        self._label(ax, ylabel=ylabel)
        self.draw()

    def ranges(self, groups, q1, median, q3, xlabel: str) -> None:
        """Median as a dot and the middle half (quartile 1 to 3) as a line, one row per group."""
        self.fit_rows(len(groups))
        ax = self._axes("x")
        color = self.brand.chart["series"][0]
        positions = list(range(len(groups)))[::-1]
        for y, lo, mid, hi in zip(positions, q1, median, q3):
            if mid is None:
                continue
            ax.plot([lo, hi], [y, y], color=color, linewidth=2, solid_capstyle="round")
            ax.plot([mid], [y], "o", markersize=8, color=color, markeredgecolor=self.brand.colors["surface"],
                    markeredgewidth=2)
        ax.set_yticks(positions, groups)
        ax.set_ylim(-0.6, len(groups) - 0.4)
        self._label(ax, xlabel)
        self.draw()

    def stacked_shares(self, groups, series: list[tuple[str, list[float], bool]], xlabel: str) -> None:
        """100% bars per group. series = (name, percent per group, is_context). Legend always shown."""
        self.fit_rows(len(groups), extra=150)
        ax = self._axes("x")
        positions = list(range(len(groups)))[::-1]
        left = [0.0] * len(groups)
        palette = iter(self.brand.chart["series"])
        for name, values, context in series:
            color = self.brand.chart["neutral"] if context else next(palette)
            ax.barh(positions, values, left=left, height=BAR_HEIGHT, color=color, label=name,
                    edgecolor=self.brand.colors["surface"], linewidth=2)
            left = [a + b for a, b in zip(left, values)]
        ax.set_yticks(positions, groups)
        ax.set_xlim(0, 100)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=min(len(series), 5), frameon=False,
                  fontsize=9, labelcolor=self.brand.colors["text"])
        self._label(ax, xlabel)
        self.draw()
