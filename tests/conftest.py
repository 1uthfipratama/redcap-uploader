"""Shared fixtures. Every value here is synthetic; identifiers are obvious placeholders."""

from __future__ import annotations

import datetime as dt

import pytest

from core.profile import load_all_profiles
from synthetic.register_writer import RegisterSpec, write_register

# A clearly named test-only key. core/identifiers.load_key() never returns this.
TEST_KEY = b"TEST-ONLY-pseudonym-key-never-use-for-real-data-0001"
OTHER_TEST_KEY = b"TEST-ONLY-pseudonym-key-never-use-for-real-data-0002"
TODAY = dt.date(2026, 10, 14)


@pytest.fixture(scope="session", autouse=True)
def app_home(tmp_path_factory):
    """The app's own folders (saved forms, dictionary backups) point at a temporary folder,
    never at the person's Documents."""
    import os

    folder = tmp_path_factory.mktemp("app_home")
    old = os.environ.get("REDCAP_UPLOADER_HOME")
    os.environ["REDCAP_UPLOADER_HOME"] = str(folder)
    yield folder
    if old is None:
        os.environ.pop("REDCAP_UPLOADER_HOME", None)
    else:
        os.environ["REDCAP_UPLOADER_HOME"] = old


@pytest.fixture(scope="session")
def profiles():
    return load_all_profiles()


@pytest.fixture(scope="session")
def so(profiles):
    return profiles["tbc03_so"]


@pytest.fixture(scope="session")
def ro(profiles):
    return profiles["tbc03_ro"]


def fake_nik(i: int) -> str:
    """16 digits starting 0000: the right shape, never a real NIK."""
    return f"0000{i:012d}"


def so_row(i: int, **overrides) -> dict:
    """One clean TBC.03 SO row with obviously fake identifiers."""
    row = {
        "c001": i,
        "c002": f"REG-FASKES-{i:04d}",
        "c003": f"REG-KAB-{i:04d}",
        "c004": "Maret",
        "c005": f"RM-SINTETIS-{i:04d}",
        "c006": fake_nik(i),
        "c007": f"9{i:011d}",
        "c008": f"8{i:011d}",
        "c009": f"7{i:011d}",
        "c011": "Sesuai standar",
        "c012": f"NAMA-SINTETIS-{i:04d}",
        "c013": 20 + i,
        "c014": "L" if i % 2 else "P",
        "c015": "Wiraswasta",
        "c017": "Provinsi Sintetis",
        "c018": "Kota Sintetis",
        "c019": "Rumah Sakit",
        "c020": "Kemenkes",
        "c021": "0000000",
        "c022": "FASYANKES SINTETIS",
        "c023": "Provinsi Sintetis",
        "c024": "Kota Sintetis",
        "c025": "Kecamatan Sintetis",
        "c026": "Kelurahan Sintetis",
        "c027": f"ALAMAT-SINTETIS-{i:04d}",
        "c028": "Ya",
        "c029": "Datang sendiri",
        "c030": "Terkonfirmasi bakteriologis",
        "c031": "TBC Paru",
        "c032": "Baru",
        "c033": "Tidak",
        "c034": "Bukan ODHIV",
        "c038": "Pos",
        "c039": dt.date(2025, 3, 1 + i),
        "c040": "Kategori 1",
        "c042": "Program TBC",
        "c044": "Neg",
        "c047": "TCM Xpert",
        "c074": dt.date(2025, 9, 1 + i),
        "c075": "Sembuh",
        "c084": f"CATATAN-SINTETIS-{i:04d}",
    }
    row.update(overrides)
    return row


IDENTIFIER_VALUES_SO = ("c002", "c003", "c005", "c006", "c007", "c008", "c009", "c012", "c027", "c084")


def raw_identifier_strings(rows: list[dict]) -> set[str]:
    """Every raw identifier value in the fixture rows, to search outputs and logs for."""
    out = set()
    for row in rows:
        for key in IDENTIFIER_VALUES_SO:
            if row.get(key) is not None:
                out.add(str(row[key]))
    return out


@pytest.fixture
def so_rows():
    return [so_row(i) for i in range(1, 6)]


@pytest.fixture
def so_file(tmp_path, so, so_rows):
    return write_register(tmp_path / "so_clean.xls", so, RegisterSpec(rows=so_rows))


@pytest.fixture
def so_file_xlsx(tmp_path, so, so_rows):
    return write_register(tmp_path / "so_clean.xlsx", so, RegisterSpec(rows=so_rows))
