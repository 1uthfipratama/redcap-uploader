"""Run the contract tests against a real REDCap test project.

    python -m tools.contract_check

Asks for the API URL and the API token, keeps them in this process's environment
only, and runs tests/contract. At each question you can type the answer, or copy it
and just press Enter: the value is then read from the clipboard. The token is never
shown, printed or written to a file. If REDCAP_TEST_URL and REDCAP_TEST_TOKEN are
already set, they are used without asking.

Use a project in Development status whose fields were set up from the TBC.03 SO
dictionary (python -m tools.export_dictionary). Never use a project that holds real
data: the tests import a few fake records (IDs starting with "ct").
"""

from __future__ import annotations

import getpass
import os
import re
import subprocess
import sys

import pytest

TOKEN_RE = re.compile(r"[0-9A-Fa-f]{32}")  # REDCap project tokens: 32 hexadecimal characters


def read_clipboard() -> str:
    """The clipboard's text, or "" if it cannot be read."""
    if sys.platform == "win32":
        command = ["powershell", "-NoProfile", "-Command", "Get-Clipboard"]
    elif sys.platform == "darwin":
        command = ["pbpaste"]
    else:
        command = ["xclip", "-o", "-selection", "clipboard"]
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def ask(prompt: str, *, secret: bool) -> str:
    typed = (getpass.getpass(prompt) if secret else input(prompt)).strip()
    return typed or read_clipboard()


def main() -> int:
    url = os.environ.get("REDCAP_TEST_URL") or ask("REDCap API URL (type it, or copy it and press Enter): ", secret=False)
    if not re.match(r"https?://", url) or len(url.split()) != 1:
        print("That is not a web address. It looks like https://redcap.example.org/api/")
        return 2
    print(f"Using {url}")
    token = os.environ.get("REDCAP_TEST_TOKEN") or ask("API token (copy it and press Enter; nothing is shown): ", secret=True)
    if not TOKEN_RE.fullmatch(token):
        print("That is not an API token (32 characters, 0-9 and A-F). Copy the token from the project's API page and try again.")
        return 2
    print("Token read (not shown).")
    os.environ["REDCAP_TEST_URL"] = url
    os.environ["REDCAP_TEST_TOKEN"] = token
    return pytest.main(["tests/contract", "-v", "-p", "no:cacheprovider"])


if __name__ == "__main__":
    sys.exit(main())
