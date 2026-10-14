"""Contract tests check the assumptions in docs/REDCAP_ASSUMPTIONS.md.

By default they run against the mock. Set REDCAP_TEST_URL and REDCAP_TEST_TOKEN in
your own terminal to run the same tests against a real REDCap *test* project whose
fields were set up from the TBC.03 SO dictionary (python -m tools.export_dictionary).
Never point them at a project holding real data.
"""

from __future__ import annotations

import os
import uuid

import pytest

from core.client import RedcapClient
from core.dictionary import build_dictionary
from core.profile import load_all_profiles
from mock_redcap.runner import MockRedcap


@pytest.fixture(scope="session")
def target():
    url, token = os.environ.get("REDCAP_TEST_URL"), os.environ.get("REDCAP_TEST_TOKEN")
    if url and token:
        yield {"kind": "real", "url": url, "token": token}
        return
    dictionary = build_dictionary(load_all_profiles()["tbc03_so"])
    with MockRedcap(dictionary) as mock:
        yield {"kind": "mock", "url": mock.url, "token": mock.token}


@pytest.fixture
def client(target):
    return RedcapClient(target["url"], target["token"])


@pytest.fixture
def new_id():
    """Record IDs unique to this run, so tests never collide with each other or old data."""
    prefix = uuid.uuid4().hex[:8]
    counter = iter(range(1, 10_000))
    return lambda: f"ct{prefix}{next(counter):03d}"
