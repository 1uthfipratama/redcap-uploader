"""Brand tokens from config/brand.yaml, turned into fonts and a Qt style sheet."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from PySide6.QtGui import QFont, QFontDatabase

REPO = Path(__file__).resolve().parent.parent
BRAND_FILE = REPO / "config" / "brand.yaml"


@dataclass
class Brand:
    name: str
    product_name: str
    colors: dict[str, str]
    heading_font: str
    body_font: str
    button_radius: int
    panel_radius: int
    logo: Path | None
    chart: dict


def load_brand(path: Path = BRAND_FILE) -> Brand:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    _load_bundled_fonts(REPO / data.get("fonts_dir", "app/assets/fonts"))
    families = set(QFontDatabase.families())
    fallback = data["fonts"].get("fallback", [])

    def pick(name: str) -> str:
        return next((f for f in [name, *fallback] if f in families), QFont().defaultFamily())

    logo = REPO / data["logo"] if data.get("logo") else None
    return Brand(
        name=data["name"],
        product_name=data["product_name"],
        colors=data["colors"],
        heading_font=pick(data["fonts"]["heading"]),
        body_font=pick(data["fonts"]["body"]),
        button_radius=int(data["radius"]["button"]),
        panel_radius=int(data["radius"]["panel"]),
        logo=logo if logo and logo.exists() else None,
        chart=data["chart"],
    )


def _load_bundled_fonts(folder: Path) -> None:
    if folder.is_dir():
        for path in sorted(folder.glob("*.ttf")) + sorted(folder.glob("*.otf")):
            QFontDatabase.addApplicationFont(str(path))


ARROW = (Path(__file__).resolve().parent / "assets" / "chevron-down.png").as_posix()


def style_sheet(b: Brand) -> str:
    c = b.colors
    return f"""
    * {{ font-family: "{b.body_font}"; font-size: 10.5pt; color: {c['text']}; }}
    QMainWindow, #Canvas {{ background: {c['canvas']}; }}
    #Header {{ background: {c['surface']}; border-bottom: 1px solid {c['border']}; }}
    #Wordmark {{ font-family: "{b.heading_font}"; font-size: 17pt; font-weight: 700; color: {c['primary']}; }}
    #ProductName {{ font-family: "{b.heading_font}"; font-size: 11pt; color: {c['navy']}; }}
    #Panel {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: {b.panel_radius}px; }}
    #Footer {{ background: {c['surface']}; border-top: 1px solid {c['border']}; }}
    #PageTitle {{ font-family: "{b.heading_font}"; font-size: 17pt; font-weight: 700; color: {c['navy']}; }}
    #PageLead, #Muted {{ color: {c['muted']}; }}
    #SectionTitle {{ font-family: "{b.heading_font}"; font-size: 11.5pt; font-weight: 600; color: {c['navy']}; }}
    #BigNumber {{ font-family: "{b.heading_font}"; font-size: 22pt; font-weight: 700; color: {c['navy']}; }}
    #Error {{ color: {c['error']}; }}
    #Warning {{ color: {c['warning']}; }}
    #Success {{ color: {c['success']}; }}

    #StepRail {{ background: {c['surface']}; border-right: 1px solid {c['border']}; }}
    #Step {{ border-radius: 10px; padding: 8px 10px; color: {c['muted']}; }}
    #Step[state="current"] {{ background: {c['primary_soft']}; color: {c['navy']}; font-weight: 600; }}
    #Step[state="done"] {{ color: {c['text']}; }}
    #StepNumber {{ min-width: 26px; max-width: 26px; min-height: 26px; max-height: 26px; border-radius: 13px;
                   background: {c['canvas']}; color: {c['muted']}; font-weight: 600; qproperty-alignment: AlignCenter; }}
    #StepNumber[state="current"] {{ background: {c['primary']}; color: white; }}
    #StepNumber[state="done"] {{ background: {c['primary_soft']}; color: {c['primary']}; }}

    QPushButton {{ border-radius: {b.button_radius}px; padding: 8px 22px; min-height: 18px; font-family: "{b.heading_font}";
                   background: transparent; color: {c['primary']}; border: none; }}
    QPushButton:hover {{ background: {c['primary_soft']}; }}
    QPushButton:disabled {{ color: {c['border']}; }}
    QPushButton#Primary {{ background: {c['primary']}; color: white; }}
    QPushButton#Primary:hover {{ background: {c['primary_hover']}; }}
    QPushButton#Primary:disabled {{ background: {c['border']}; color: white; }}

    QLineEdit, QComboBox {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px;
                            padding: 6px 10px; min-height: 22px; }}
    QLineEdit:focus, QComboBox:focus {{ border: 1px solid {c['primary']}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox::down-arrow {{ image: url("{ARROW}"); width: 10px; height: 10px; }}
    QComboBox::down-arrow:disabled {{ image: none; }}
    QRadioButton {{ spacing: 8px; padding: 4px 0; }}
    QRadioButton::indicator {{ width: 14px; height: 14px; border-radius: 8px; border: 2px solid {c['muted']}; background: {c['surface']}; }}
    QRadioButton::indicator:checked {{ border: 2px solid {c['primary']};
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                                    stop:0 {c['primary']}, stop:0.5 {c['primary']}, stop:0.56 {c['surface']}, stop:1 {c['surface']}); }}

    QTableView, QTableWidget {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px;
                                gridline-color: {c['border']}; selection-background-color: {c['primary_soft']};
                                selection-color: {c['text']}; }}
    QPushButton#CellButton {{ padding: 2px 10px; min-height: 0; }}
    QComboBox#Cell {{ border: none; border-radius: 0; background: transparent; padding: 0 6px; min-height: 0; }}
    QComboBox#Cell:hover {{ background: {c['primary_soft']}; }}
    QComboBox#Cell:disabled {{ color: {c['muted']}; }}
    QHeaderView::section {{ background: {c['canvas']}; color: {c['muted']}; border: none;
                            border-bottom: 1px solid {c['border']}; padding: 6px 8px; font-weight: 600; }}
    QProgressBar {{ background: {c['canvas']}; border: none; border-radius: 4px; height: 8px; text-align: center; }}
    QProgressBar::chunk {{ background: {c['primary']}; border-radius: 4px; }}
    QToolButton#Tab {{ border: none; border-bottom: 2px solid transparent; padding: 6px 2px; margin-right: 18px;
                       color: {c['muted']}; font-family: "{b.heading_font}"; }}
    QToolButton#Tab:checked {{ color: {c['navy']}; border-bottom: 2px solid {c['primary']}; }}
    QToolButton#Tab:hover {{ color: {c['primary']}; }}
    QListWidget#TutorialList {{ background: {c['surface']}; border: none; border-right: 1px solid {c['border']};
                                padding: 14px 8px; outline: none; }}
    QListWidget#TutorialList::item {{ padding: 7px 8px; border-radius: 8px; color: {c['text']}; }}
    QListWidget#TutorialList::item:selected {{ background: {c['primary_soft']}; color: {c['navy']}; }}
    QToolButton#Disclosure {{ border: none; color: {c['primary']}; font-weight: 600; padding: 4px 0; }}
    #DropZone {{ border: 2px dashed {c['border']}; border-radius: {b.panel_radius}px; background: {c['canvas']}; }}
    QTabWidget::pane {{ border: none; }}
    QTabBar::tab {{ background: transparent; color: {c['muted']}; padding: 8px 14px; border: none;
                    border-bottom: 2px solid transparent; font-family: "{b.heading_font}"; }}
    QTabBar::tab:selected {{ color: {c['navy']}; border-bottom: 2px solid {c['primary']}; }}
    QTabBar::tab:hover {{ color: {c['primary']}; }}
    #DropZone[hover="true"] {{ border-color: {c['primary']}; background: {c['primary_soft']}; }}
    """
