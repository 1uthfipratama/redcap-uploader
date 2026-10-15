"""List the third-party libraries the app ships with, and their licences.

    python -m tools.third_party_notices                      # rewrite THIRD_PARTY_NOTICES.md
    python -m tools.third_party_notices --collect DIR        # also copy every licence file into DIR

The installers bundle these libraries, so their notices must travel with them
(PySide6/Qt is LGPL-3.0: its licence text is included and its libraries stay
separate, replaceable files in the one-folder build). The list follows
requirements.txt and everything those packages need at run time, as installed
in the current environment.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from importlib import metadata
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement

REPO = Path(__file__).resolve().parent.parent
LICENSE_FILE_RE = re.compile(r"(LICEN[CS]E|COPYING|NOTICE|AUTHORS)", re.IGNORECASE)


def top_level_requirements() -> list[str]:
    names = []
    for line in (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line and not line.startswith("-"):
            names.append(Requirement(line).name)
    return names


def runtime_closure(names: list[str]) -> dict[str, metadata.Distribution]:
    """Every installed distribution needed at run time, following dependencies (no extras)."""
    env = default_environment()
    env["extra"] = ""
    seen: dict[str, metadata.Distribution] = {}
    queue = list(names)
    while queue:
        name = queue.pop()
        key = name.lower().replace("_", "-")
        if key in seen:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        seen[key] = dist
        for raw in dist.requires or []:
            req = Requirement(raw)
            if req.marker is None or req.marker.evaluate(env):
                queue.append(req.name)
    return dict(sorted(seen.items()))


def licence_of(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    if meta.get("License-Expression"):
        return meta["License-Expression"]
    text = (meta.get("License") or "").strip()
    if text and len(text) <= 60 and "\n" not in text:
        return text
    classifiers = [c.split(" :: ")[-1] for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    return "; ".join(classifiers) or "see licence file"


def homepage_of(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    if meta.get("Home-page"):
        return meta["Home-page"]
    for entry in meta.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        if label.strip().lower() in ("homepage", "home", "source", "repository", "source code"):
            return url.strip()
    return ""


def write_notices(dists: dict[str, metadata.Distribution], path: Path) -> None:
    lines = [
        "# Third-party notices",
        "",
        "REDCap Uploader is MIT-licensed (see `LICENSE`). The installers also include the libraries below, each under",
        "its own licence. The full licence texts are in the `licenses` folder of an installed copy.",
        "",
        "PySide6 and Qt are used under the GNU LGPL v3. They are shipped as separate library files that can be replaced",
        "with other builds of the same version; their source is available from https://download.qt.io and",
        "https://code.qt.io/cgit/pyside/pyside-setup.git/.",
        "",
        f"Python {sys.version_info.major}.{sys.version_info.minor} itself is under the PSF License.",
        "",
        "| Library | Version | Licence | Website |",
        "| --- | --- | --- | --- |",
    ]
    for dist in dists.values():
        name = dist.metadata["Name"]
        lines.append(f"| {name} | {dist.version} | {licence_of(dist)} | {homepage_of(dist)} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def collect(dists: dict[str, metadata.Distribution], folder: Path) -> int:
    """Copy each library's licence and notice files into folder/<library>/."""
    folder.mkdir(parents=True, exist_ok=True)
    copied = 0
    for dist in dists.values():
        target = folder / dist.metadata["Name"]
        for file in dist.files or []:
            path = str(file).replace("\\", "/")
            in_licenses_dir = ".dist-info/licenses/" in path
            if ".dist-info" in path and (in_licenses_dir or LICENSE_FILE_RE.search(Path(path).name)):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    target.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target / Path(str(file)).name)
                    copied += 1
    qt = folder / "Qt-and-PySide6"
    for text in sorted((REPO / "licenses").glob("*.txt")):
        qt.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(text, qt / text.name)
        copied += 1
    return copied


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--collect", type=Path, help="also copy every licence file into this folder")
    args = parser.parse_args(argv)
    dists = runtime_closure(top_level_requirements())
    write_notices(dists, REPO / "THIRD_PARTY_NOTICES.md")
    print(f"{len(dists)} libraries listed in THIRD_PARTY_NOTICES.md")
    if args.collect:
        print(f"{collect(dists, args.collect)} licence files copied to {args.collect}")


if __name__ == "__main__":
    main()
