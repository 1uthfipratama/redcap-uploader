"""Run the contract tests against a real REDCap test project.

    python -m tools.contract_check

Asks for the API URL and the API token (typed without being shown), keeps them in
this process's environment only, and runs tests/contract. The token is never
written to a file or printed. If REDCAP_TEST_URL and REDCAP_TEST_TOKEN are already
set, they are used without asking.

Use a project in Development status whose fields were set up from the TBC.03 SO
dictionary (python -m tools.export_dictionary). Never use a project that holds real
data: the tests import a few fake records (IDs starting with "ct").
"""

from __future__ import annotations

import getpass
import os
import sys

import pytest


def main() -> int:
    url = os.environ.get("REDCAP_TEST_URL") or input("REDCap API URL (ends in /api/): ").strip()
    token = os.environ.get("REDCAP_TEST_TOKEN") or getpass.getpass("API token (not shown): ").strip()
    if not url or not token:
        print("Both the API URL and the token are needed.")
        return 2
    os.environ["REDCAP_TEST_URL"] = url
    os.environ["REDCAP_TEST_TOKEN"] = token
    return pytest.main(["tests/contract", "-v", "-p", "no:cacheprovider"])


if __name__ == "__main__":
    sys.exit(main())
