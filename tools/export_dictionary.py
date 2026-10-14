"""Write a profile's REDCap data dictionary as the CSV REDCap's Data Dictionary page accepts.

    python -m tools.export_dictionary tbc03_so out/tbc03_so_dictionary.csv

Use it to set up a REDCap test project with the same fields the app uploads.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.dictionary import build_dictionary
from core.export_csv import write_dictionary_csv
from core.profile import load_all_profiles


def main(argv: list[str] | None = None) -> None:
    profiles = load_all_profiles()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("form", choices=sorted(k for k, p in profiles.items() if not p.is_generic))
    parser.add_argument("out", type=Path)
    args = parser.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    dictionary = build_dictionary(profiles[args.form])
    write_dictionary_csv(dictionary, args.out)
    print(f"Wrote {len(dictionary)} fields to {args.out}")


if __name__ == "__main__":
    main()
