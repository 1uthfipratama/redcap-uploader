# PyInstaller spec: one-folder build of the app, the same spec on Windows and macOS.
#
#   pyinstaller build/redcap_uploader.spec --noconfirm --workpath build/out/work --distpath dist
#
# Windows: dist/REDCap Uploader/REDCap Uploader.exe (wrapped by build/windows/installer.iss)
# macOS:   dist/REDCap Uploader.app (wrapped by build/macos/make_dmg.sh)

import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(SPECPATH).parent
BRAND = yaml.safe_load((ROOT / "config" / "brand.yaml").read_text(encoding="utf-8"))
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
NAME = BRAND["product_name"]

datas = [
    (str(ROOT / "profiles"), "profiles"),
    (str(ROOT / "config"), "config"),
    (str(ROOT / "i18n"), "i18n"),
    (str(ROOT / "synthetic" / "forms"), "synthetic/forms"),  # structure-only inventories, used for sample files
    (str(ROOT / "synthetic" / "distributions.yaml"), "synthetic"),
]
datas += [(str(ROOT / "LICENSE"), "."), (str(ROOT / "THIRD_PARTY_NOTICES.md"), ".")]
if (ROOT / "build" / "out" / "licenses").is_dir():  # filled by: python -m tools.third_party_notices --collect build/out/licenses
    datas.append((str(ROOT / "build" / "out" / "licenses"), "licenses"))
if (ROOT / "app" / "assets").is_dir():
    datas.append((str(ROOT / "app" / "assets"), "app/assets"))

hiddenimports = [
    "matplotlib.backends.backend_qtagg",  # imported lazily when Explore opens
    "xlrd",
    "openpyxl",
    "redcap",
    "flask",
    "werkzeug",
]

# Large parts of Qt and Python the app never uses.
excludes = [
    "tkinter", "pydoc_data", "IPython", "notebook", "pytest", "xlwt",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DExtras",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtGraphs", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtBluetooth", "PySide6.QtNfc",
    "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSensors", "PySide6.QtSerialPort",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtSpatialAudio",
    "PySide6.QtTextToSpeech", "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtStateMachine",
    "matplotlib.backends.backend_tkagg", "matplotlib.backends.backend_wx", "matplotlib.backends.backend_gtk3agg",
]

icon = None
key = "icon_macos" if sys.platform == "darwin" else "icon_windows"
if BRAND.get(key) and (ROOT / BRAND[key]).exists():
    icon = str(ROOT / BRAND[key])

a = Analysis(
    [str(ROOT / "build" / "launch.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    console=False,  # no console window
    icon=icon,
)
coll = COLLECT(exe, a.binaries, a.datas, name=NAME)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{NAME}.app",
        icon=icon,
        bundle_identifier=BRAND["bundle_id"],
        version=VERSION,
        info_plist={
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
            "NSHumanReadableCopyright": "Copyright (c) 2026 Luthfi Izza Pratama (Yayasan RPRI). MIT License.",
        },
    )
