"""Write the documentation diagrams (docs/*.svg) in English.

    python -m tools.make_diagrams
"""

from __future__ import annotations

from pathlib import Path

from app.diagrams import DIAGRAMS, svg
from core.messages import text

DOCS = Path(__file__).resolve().parent.parent / "docs"


def main() -> None:
    for name in DIAGRAMS:
        path = DOCS / f"{name}.svg"
        path.write_text(svg(name, lambda key: text(key, "en")) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(DOCS.parent)}")


if __name__ == "__main__":
    main()
