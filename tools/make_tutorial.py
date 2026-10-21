"""Write the Tutorial tab's screenshots: app/assets/tutorial/<language>/<step>.png.

    python -m tools.make_tutorial

Runs the app on this computer against the built-in practice REDCap and the synthetic sample file,
captures each step, and highlights what to press. It needs a real screen (for fonts) and shows
synthetic data only. Run it again after the screens change.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen
from PySide6.QtWidgets import QLabel, QRadioButton

from app.tutorial import ASSETS, STEPS

LANGUAGES = ("en", "id")
WINDOW = (1280, 1000)
MAX_WIDTH = 1100  # pictures are scaled down to this
KEY = b"TUTORIAL-ONLY-key-for-screenshots-0001"  # a fixed demo key, so the pseudonyms in the pictures repeat
PRIMARY, DIM = QColor("#1E6BBD"), QColor(0, 20, 60, 120)
PAD, BADGE = 4, 13


def annotate(image: QImage, rects: list[QRect]) -> QImage:
    """Dim everything except the given areas, outline them and number them 1, 2, 3 ..."""
    bounds = image.rect()
    areas = [(rect.adjusted(-PAD, -PAD, PAD, PAD)) & bounds for rect in rects]
    out = image.copy()
    painter = QPainter(out)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.fillRect(bounds, DIM)
    for area in areas:
        painter.drawImage(area, image, area)
    for number, area in enumerate(areas, start=1):
        painter.setPen(QPen(PRIMARY, 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(area, 8, 8)
        centre = QPoint(max(area.left(), BADGE + 2), max(area.top(), BADGE + 2))
        painter.setPen(Qt.NoPen)
        painter.setBrush(PRIMARY)
        painter.drawEllipse(centre, BADGE, BADGE)
        painter.setPen(QColor("white"))
        painter.setFont(QFont(painter.font().family(), 11, QFont.Bold))
        painter.drawText(QRect(centre.x() - BADGE, centre.y() - BADGE, 2 * BADGE, 2 * BADGE), Qt.AlignCenter, str(number))
    painter.end()
    return out


def area(target, window) -> QRect:
    """A widget (or several, joined) as a rectangle in the window's own coordinates."""
    widgets = target if isinstance(target, (list, tuple)) else [target]
    joined = QRect()
    for widget in widgets:
        if widget.isVisible():
            joined = joined.united(QRect(widget.mapTo(window, QPoint(0, 0)), _size(widget)))
    return joined


def _size(widget):
    """A label or radio button spans its whole row; the highlight should hug its text."""
    if isinstance(widget, (QLabel, QRadioButton)) and widget.text():
        width = QFontMetrics(widget.font()).horizontalAdvance(widget.text()) + (32 if isinstance(widget, QRadioButton) else 6)
        return widget.size().boundedTo(type(widget.size())(width, widget.height()))
    return widget.size()


def take(window, name: str, targets: list) -> QImage:
    """Grab the window (without its header and step rail), highlight the targets, fit it to MAX_WIDTH."""
    assert len(targets) == STEPS[name], f"{name}: {len(targets)} highlights, expected {STEPS[name]}"
    image = window.grab().toImage()
    ratio = image.devicePixelRatio()
    image.setDevicePixelRatio(1)
    origin = window.stack.mapTo(window, QPoint(0, 0))
    left, top = round(origin.x() * ratio), round(origin.y() * ratio)
    image = image.copy(left, top, image.width() - left, image.height() - top)
    rects = []
    for target in targets:
        rect = target if isinstance(target, QRect) else area(target, window)
        rect = QRect(round((rect.x() - origin.x()) * ratio), round((rect.y() - origin.y()) * ratio),
                     round(rect.width() * ratio), round(rect.height() * ratio))
        assert image.rect().contains(rect), f"{name}: a highlight is outside the picture (window too small?)"
        rects.append(rect)
    image = annotate(image, rects)
    return image.scaledToWidth(MAX_WIDTH, Qt.SmoothTransformation) if image.width() > MAX_WIDTH else image


def shoot(lang: str) -> dict[str, QImage]:
    from app.__main__ import build
    from app.review_table import EditCellDialog
    from app.smoke import _settle

    app, w = build(lang)
    w.resize(*WINDOW)
    w.show()

    def go(action) -> None:
        action()
        _settle(app, w)

    connect, choose, review, upload, result = w.pages
    shots: dict[str, QImage] = {}
    _settle(app, w)
    shots["connect"] = take(w, "connect", [connect.demo, w.next])
    connect.real.click()
    app.processEvents()
    keys = [connect.create_key_button, connect.key_button]
    shots["connect_real"] = take(w, "connect_real", [connect.url, connect.token, keys, w.next])
    connect.demo.click()
    w.state.key = KEY
    go(w._next)  # connect
    shots["connected"] = take(w, "connected", [connect.status, connect.checks, w.next])
    go(w._next)  # to Choose file
    go(lambda: choose._sample("messy"))
    shots["choose"] = take(w, "choose", [choose.pick, choose.summary, w.next])

    go(w._next)  # read and review
    problem = next(i for i in w.state.prepared.errors if i.code == "above_max")
    review._select(problem.row, problem.field)
    app.processEvents()
    cell = review.view.visualRect(review.model.index_of(problem.row, problem.field))
    cell = QRect(review.view.viewport().mapTo(w, cell.topLeft()), cell.size())
    shots["review"] = take(w, "review", [review.headline, cell, review.edit_button, review.skip_button, review.skip_errors])

    dialog = EditCellDialog(w.tr, review.model, problem.row, problem.field, w)
    dialog.show()
    app.processEvents()
    shots["edit"] = take_dialog(dialog)
    dialog.close()

    w.state.review.set_value(problem.row, problem.field, "21")  # what the edit window does on Save
    review._changed(problem.row, problem.field)
    review.skip_errors.click()
    app.processEvents()
    shots["ready"] = take(w, "ready", [review.headline, w.next])
    go(w._next)  # to Upload
    shots["upload"] = take(w, "upload", [[upload.plan, upload.detail], w.next])
    go(w._next)  # upload
    numbers = [result.headline, *result.numbers.values(), *result.captions.values()]
    shots["result"] = take(w, "result", [numbers, result.changes, [result.save, result.receipt]])
    w.close()
    return shots


def take_dialog(dialog) -> QImage:
    """The edit window on its own, with its two highlights."""
    image = dialog.grab().toImage()
    ratio = image.devicePixelRatio()
    image.setDevicePixelRatio(1)
    rects = []
    for widget in (dialog.input, dialog.save):
        rect = area(widget, dialog)
        rects.append(QRect(round(rect.x() * ratio), round(rect.y() * ratio),
                           round(rect.width() * ratio), round(rect.height() * ratio)))
    assert len(rects) == STEPS["edit"]
    return annotate(image, rects)


def main() -> None:
    os.environ["REDCAP_UPLOADER_HOME"] = tempfile.mkdtemp(prefix="tutorial-home-")  # none of the person's own forms
    for lang in LANGUAGES:
        folder = ASSETS / lang
        folder.mkdir(parents=True, exist_ok=True)
        for name, image in shoot(lang).items():
            path = folder / f"{name}.png"
            image.save(str(path))
            print(f"wrote {path.relative_to(ASSETS.parent.parent.parent)} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
