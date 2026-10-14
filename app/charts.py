"""Quiet, readable charts for the Explore screen (matplotlib, imported lazily).

One look everywhere:
- a title inside the figure, so a saved PNG explains itself;
- a legend (two or more series) in one row under the title, never over the data;
- thin bars with air between them, a hairline grid on the value axis only;
- text in ink colours and the app's font at a readable size; long labels wrap;
- the brand blue for a single series, grey for "unknown", "blank" and "other".
Layout is matplotlib's constrained layout, so labels, legend and title never overlap.
Every chart sits next to a table with the same numbers.
"""

from __future__ import annotations

import textwrap

from app.theme import Brand

BAR_HEIGHT = 0.62  # share of a row a bar fills; the rest is air
ROW_PX = 34  # height per row in horizontal charts
MIN_PX = 320
HEADER_PX = 70  # title and legend
AXIS_PX = 70  # value axis and its label
LABEL_WIDTH = 28  # characters before a category label wraps
FONT_SIZE = 10


def wrap(label: str, width: int = LABEL_WIDTH) -> str:
    return "\n".join(textwrap.wrap(str(label), width)) or str(label)


class Chart:
    """A matplotlib figure inside a Qt widget. Created only when the Explore screen opens."""

    def __init__(self, brand: Brand):
        import matplotlib
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        matplotlib.rcParams["font.family"] = [brand.body_font, "Segoe UI", "DejaVu Sans"]
        matplotlib.rcParams["font.size"] = FONT_SIZE
        self.brand = brand
        self.figure = Figure(figsize=(7.4, 3.6), dpi=100, facecolor=brand.colors["surface"], layout="constrained")
        self.figure.get_layout_engine().set(w_pad=0.12, h_pad=0.12)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(MIN_PX)

    # ---- shared look -----------------------------------------------------------
    def _start(self, title: str, value_axis: str, rows: int | None = None, row_px: int = ROW_PX):
        c, chart = self.brand.colors, self.brand.chart
        height = MIN_PX if rows is None else max(MIN_PX, rows * row_px + HEADER_PX + AXIS_PX)
        self.canvas.setMinimumHeight(height)
        self.canvas.setMaximumHeight(height)
        self.figure.clear()
        self.figure.suptitle(title, x=0.01, ha="left", fontsize=FONT_SIZE + 1.5, fontweight="bold", color=c["navy"])
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(c["surface"])
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(chart["grid"])
        ax.tick_params(colors=c["muted"], labelsize=FONT_SIZE, length=0, pad=6)
        ax.grid(axis=value_axis, color=chart["grid"], linewidth=1, linestyle="-")
        ax.set_axisbelow(True)
        return ax

    def _axis_label(self, ax, xlabel: str = "", ylabel: str = "") -> None:
        muted = self.brand.colors["muted"]
        if xlabel:
            ax.set_xlabel(xlabel, color=muted, labelpad=8)
        if ylabel:
            ax.set_ylabel(ylabel, color=muted, labelpad=8)

    def _legend(self, ax, handles_labels) -> None:
        """One row just above the plot, under the title; the layout makes room for it."""
        handles, labels = handles_labels
        ax.legend(handles, labels, loc="lower left", bbox_to_anchor=(0, 1.02), ncols=min(len(labels), 5),
                  frameon=False, borderaxespad=0, fontsize=FONT_SIZE, labelcolor=self.brand.colors["text"],
                  handlelength=1.2, columnspacing=1.6)

    @staticmethod
    def _whole_numbers(axis) -> None:
        """Record counts never show steps like 2.5."""
        from matplotlib.ticker import MaxNLocator

        axis.set_major_locator(MaxNLocator(integer=True))

    def draw(self) -> None:
        self.canvas.draw_idle()

    def save_png(self, path: str) -> None:
        self.figure.savefig(path, dpi=200, facecolor=self.brand.colors["surface"])

    def message(self, text: str) -> None:
        self.canvas.setMinimumHeight(140)
        self.canvas.setMaximumHeight(140)
        self.figure.clear()
        self.figure.text(0.5, 0.5, text, ha="center", va="center", color=self.brand.colors["muted"],
                         fontsize=FONT_SIZE + 1)
        self.canvas.draw_idle()

    # ---- forms -------------------------------------------------------------------
    def histogram(self, title: str, starts, ends, counts, xlabel: str, ylabel: str) -> None:
        ax = self._start(title, "y")
        widths = [(e - s) for s, e in zip(starts, ends)]
        ax.bar(starts, counts, width=[w * 0.9 for w in widths], align="edge", color=self.brand.chart["series"][0])
        self._whole_numbers(ax.yaxis)
        self._axis_label(ax, xlabel, ylabel)
        self.draw()

    def horizontal_bars(self, title: str, labels, values, value_text, context_mask, xlabel: str) -> None:
        """One bar per category, in the form's order from the top; context categories in grey."""
        wrapped = sum(len(str(lab)) > LABEL_WIDTH for lab in labels)
        ax = self._start(title, "x", rows=len(labels) + wrapped // 2)
        colors = [self.brand.chart["neutral"] if n else self.brand.chart["series"][0] for n in context_mask]
        positions = list(range(len(labels)))[::-1]
        ax.barh(positions, values, height=BAR_HEIGHT, color=colors)
        ax.set_yticks(positions, [wrap(lab) for lab in labels])
        top = max(values) if len(values) else 0
        for y, v, text in zip(positions, values, value_text):
            ax.text(v + top * 0.012, y, text, va="center", fontsize=FONT_SIZE, color=self.brand.colors["text"])
        ax.set_xlim(0, top * 1.22 if top else 1)
        ax.set_ylim(-0.6, len(labels) - 0.4)
        self._whole_numbers(ax.xaxis)
        self._axis_label(ax, xlabel)
        self.draw()

    def columns(self, title: str, labels, values, ylabel: str) -> None:
        ax = self._start(title, "y")
        ax.bar(range(len(labels)), values, width=BAR_HEIGHT, color=self.brand.chart["series"][0])
        step = max(1, -(-len(labels) // 10))  # at most about ten labels
        ax.set_xticks(range(0, len(labels), step), labels[::step])
        self._whole_numbers(ax.yaxis)
        self._axis_label(ax, ylabel=ylabel)
        self.draw()

    def ranges(self, title: str, groups, q1, median, q3, xlabel: str, legend: tuple[str, str]) -> None:
        """Median as a dot and the middle half (quartile 1 to 3) as a line, one row per group."""
        ax = self._start(title, "x", rows=len(groups), row_px=ROW_PX + 8)
        color = self.brand.chart["series"][0]
        positions = list(range(len(groups)))[::-1]
        line = dot = None
        for y, lo, mid, hi in zip(positions, q1, median, q3):
            if mid is None or mid != mid:
                continue
            (line,) = ax.plot([lo, hi], [y, y], color=color, linewidth=2.5, solid_capstyle="round")
            (dot,) = ax.plot([mid], [y], "o", markersize=9, color=color, markeredgecolor=self.brand.colors["surface"],
                             markeredgewidth=2)
        ax.set_yticks(positions, [wrap(g) for g in groups])
        ax.set_ylim(-0.6, len(groups) - 0.4)
        if line is not None:
            self._legend(ax, ([dot, line], list(legend)))
        self._axis_label(ax, xlabel)
        self.draw()

    def grouped_bars(self, title: str, answers, groups, percents, context_mask, xlabel: str) -> None:
        """One row per answer; within it one bar per group (at most four groups, each its own colour).
        percents[a][g] is the share of group g giving answer a."""
        n_groups = max(len(groups), 1)
        ax = self._start(title, "x", rows=len(answers), row_px=18 + 12 * n_groups)
        palette = self.brand.chart["series"]
        slot = BAR_HEIGHT / n_groups
        positions = list(range(len(answers)))[::-1]
        for g, name in enumerate(groups):
            offsets = [y + BAR_HEIGHT / 2 - slot * (g + 0.5) for y in positions]
            values = [percents[a][g] for a in range(len(answers))]
            ax.barh(offsets, values, height=slot * 0.86, color=palette[g % len(palette)], label=wrap(name, 24))
        labels = [wrap(a) for a in answers]
        ax.set_yticks(positions, labels)
        for tick, context in zip(ax.get_yticklabels(), context_mask):
            if context:
                tick.set_color(self.brand.chart["neutral"])
        top = max((v for row in percents for v in row), default=0)
        ax.set_xlim(0, min(100, top * 1.15) if top else 1)
        ax.set_ylim(-0.6, len(answers) - 0.4)
        self._legend(ax, ax.get_legend_handles_labels())
        self._axis_label(ax, xlabel)
        self.draw()

    def stacked_two(self, title: str, labels, first, second, names: tuple[str, str], xlabel: str) -> None:
        """Two parts of each row's total side by side in one bar (blank, then unknown)."""
        ax = self._start(title, "x", rows=len(labels))
        positions = list(range(len(labels)))[::-1]
        series = self.brand.chart["series"]
        ax.barh(positions, first, height=BAR_HEIGHT, color=series[0], label=names[0])
        ax.barh(positions, second, left=first, height=BAR_HEIGHT, color=series[1], label=names[1],
                edgecolor=self.brand.colors["surface"], linewidth=1.5)
        ax.set_yticks(positions, [wrap(lab) for lab in labels])
        ax.set_xlim(0, 100)
        ax.set_ylim(-0.6, len(labels) - 0.4)
        self._legend(ax, ax.get_legend_handles_labels())
        self._axis_label(ax, xlabel)
        self.draw()
