"""The three documentation diagrams as SVG text.

One source for the images in docs/ (tools/make_diagrams.py, English) and for the tutorial tab,
which draws them in the language of the interface. Only rectangles, lines, paths and text are
used, so Qt's SVG renderer draws them too. `t` turns a key into text.
"""

from __future__ import annotations

from typing import Callable
from xml.sax.saxutils import escape

NAVY, TEXT, MUTED, BORDER = "#002157", "#1D1E20", "#5B6573", "#DDE3EB"
PRIMARY, PRIMARY_SOFT, CANVAS, ARROW = "#1E6BBD", "#E8F0FA", "#F4F7FB", "#9AA4B2"
FONT = "Segoe UI, -apple-system, Helvetica, Arial, sans-serif"

Translate = Callable[[str], str]


def _text(x: float, y: float, s: str, size: float = 12, fill: str = MUTED, bold: bool = False,
          anchor: str = "start") -> str:
    weight = ' font-weight="600"' if bold else ""
    return f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" fill="{fill}"{weight} text-anchor="{anchor}">{escape(s)}</text>'


def _lines(x: float, y: float, s: str, size: float = 12, fill: str = MUTED, gap: float = 17) -> str:
    return "".join(_text(x, y + i * gap, line, size, fill) for i, line in enumerate(s.split("\n")))


def _rect(x: float, y: float, w: float, h: float, fill: str = "#FFFFFF", stroke: str = BORDER, r: float = 10) -> str:
    return f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{r:g}" fill="{fill}" stroke="{stroke}"/>'


def _arrow(x1: float, x2: float, y: float) -> str:
    return (f'<line x1="{x1:g}" y1="{y:g}" x2="{x2 - 6:g}" y2="{y:g}" stroke="{ARROW}" stroke-width="1.5"/>'
            f'<path d="M{x2 - 7:g},{y - 4:g} L{x2:g},{y:g} L{x2 - 7:g},{y + 4:g} Z" fill="{ARROW}"/>')


def _step(x: float, y: float, w: float, h: float, title: str, sub: str, number: int | None = None,
          focus: bool = False) -> str:
    """A rounded box with a title and up to two lines under it; `focus` marks the step a person does."""
    out = [_rect(x, y, w, h, PRIMARY_SOFT if focus else "#FFFFFF", PRIMARY if focus else BORDER)]
    top = y + 26
    if number is not None:
        out.append(_text(x + 14, top, str(number), 12, PRIMARY, bold=True))
        left = x + 30
    else:
        left = x + 14
    out.append(_text(left, top, title, 14, NAVY, bold=True))
    out.append(_lines(x + 14, y + 48, sub, 11.5))
    return "".join(out)


def _svg(width: int, height: int, body: str, title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'font-family="{FONT}" role="img"><title>{escape(title)}</title>'
            f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>{body}</svg>')


def pipeline(t: Translate) -> str:
    steps = ["read", "recognise", "deidentify", "map", "review", "upload"]
    w, gap, x0, y, h = 136, 24, 22, 20, 84
    body = []
    for i, key in enumerate(steps):
        x = x0 + i * (w + gap)
        body.append(_step(x, y, w, h, t(f"ui.dg.{key}.t"), t(f"ui.dg.{key}.s"), i + 1, focus=key == "review"))
        if i:
            body.append(_arrow(x - gap + 3, x - 3, y + h / 2))
    local_w = 5 * w + 4 * gap
    body.append(_rect(x0, 126, local_w, 36, CANVAS))
    body.append(_text(x0 + 16, 149, t("ui.dg.local"), 12.5))
    last = x0 + 5 * (w + gap)
    body.append(_rect(last, 126, w, 36, PRIMARY, PRIMARY))
    body.append(_text(last + w / 2, 149, t("ui.dg.redcap"), 12.5, "#FFFFFF", bold=True, anchor="middle"))
    return _svg(980, 184, "".join(body), t("ui.dg.pipeline.title"))


def identifiers(t: Translate) -> str:
    body = [_text(22, 22, t("ui.dg.id.in_file"), 12, MUTED, bold=True), _text(668, 22, t("ui.dg.id.in_redcap"), 12, MUTED, bold=True)]
    for i, key in enumerate(["drop", "pseudo", "keep"]):
        y = 34 + i * 84
        body.append(_rect(22, y, 300, 68))
        body.append(_lines(38, y + 28, t(f"ui.dg.id.{key}.in"), 13, NAVY, 21))
        body.append(_arrow(330, 660, y + 44))
        if key == "pseudo":
            body.append(_rect(440, y + 4, 100, 22, PRIMARY_SOFT, PRIMARY, 11))
            body.append(_text(490, y + 19, t("ui.dg.id.key"), 11.5, PRIMARY, anchor="middle"))
        head, _, rest = t(f"ui.dg.id.{key}.out").partition("\n")
        body.append(_rect(668, y, 290, 68, CANVAS))
        body.append(_text(684, y + 28, head, 13, NAVY, bold=True))
        body.append(_lines(684, y + 47, rest, 12, MUTED, 17))
    y = 34 + 3 * 84 + 8
    for key in ("known", "other"):
        lead, _, rest = t(f"ui.dg.id.{key}").partition("\n")
        name, sep, first = lead.partition(":")
        body.append(f'<text x="22" y="{y:g}" font-size="12" fill="{MUTED}"><tspan fill="{NAVY}" font-weight="600">{escape(name + sep)}</tspan>{escape(first)}</text>')
        y += 17
        if rest:
            body.append(_lines(22, y, rest, 12, MUTED, 17))
            y += 17 * len(rest.split("\n"))
        y += 8
    return _svg(980, int(y + 8), "".join(body), t("ui.dg.id.title"))


def lifecycle(t: Translate) -> str:
    w, gap, x0 = 200, 40, 30
    body = []
    for row, (label, keys, top) in enumerate([("once", ["create", "fields", "test", "prod"], 36),
                                              ("every", ["choose", "review", "upload", "result"], 164)]):
        body.append(_text(22, top - 12, t(f"ui.dg.life.{label}"), 12, MUTED, bold=True))
        for i, key in enumerate(keys):
            x = x0 + i * (w + gap)
            body.append(_step(x, top, w, 84, t(f"ui.dg.life.{key}.t"), t(f"ui.dg.life.{key}.s"), focus=key == "review"))
            if i:
                body.append(_arrow(x - gap + 3, x - 3, top + 42))
    return _svg(980, 262, "".join(body), t("ui.dg.life.title"))


DIAGRAMS = {"pipeline": pipeline, "identifiers": identifiers, "lifecycle": lifecycle}


def svg(name: str, t: Translate) -> str:
    return DIAGRAMS[name](t)
