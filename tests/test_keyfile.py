"""Creating, protecting and backing up the pseudonym key."""

import json

import pytest

from core.identifiers import PseudonymKeyInvalid
from core.keyfile import (
    KeyFileExists,
    PassphraseNeeded,
    WrongPassphrase,
    fingerprint,
    is_protected,
    new_key,
    protect,
    read_key,
    unprotect,
    write_key,
)

PASS = "correct horse battery"


def test_a_protected_key_opens_only_with_its_passphrase():
    key = new_key()
    text = protect(key, PASS)
    assert is_protected(text) and key.hex() not in text.casefold()
    assert unprotect(text, PASS) == key
    with pytest.raises(WrongPassphrase):
        unprotect(text, PASS + "!")


def test_a_damaged_file_is_detected():
    data = json.loads(protect(new_key(), PASS))
    data["sealed_key"] = ("00" if not data["sealed_key"].startswith("00") else "11") + data["sealed_key"][2:]
    with pytest.raises(WrongPassphrase):
        unprotect(json.dumps(data), PASS)
    with pytest.raises(PseudonymKeyInvalid):
        unprotect('{"format": "redcap-uploader-pseudonym-key"}', PASS)


def test_short_passphrases_are_refused():
    with pytest.raises(ValueError):
        protect(new_key(), "short")


def test_fingerprint_is_stable_and_tells_keys_apart():
    key = new_key()
    assert fingerprint(key) == fingerprint(bytes(key))
    assert fingerprint(key) != fingerprint(new_key())
    assert len(fingerprint(key)) == 9 and fingerprint(key)[4] == "-"
    assert json.loads(protect(key, PASS))["fingerprint"] == fingerprint(key)


def test_written_keys_read_back_and_never_overwrite(tmp_path):
    key = new_key()
    path = write_key(tmp_path / "study.key", key, PASS)
    with pytest.raises(PassphraseNeeded):
        read_key(path)
    assert read_key(path, PASS) == key
    with pytest.raises(KeyFileExists):
        write_key(path, new_key(), PASS)
    assert read_key(path, PASS) == key  # the first key is untouched


def test_keys_are_never_written_inside_the_app_folder():
    from core.identifiers import REPO_ROOT

    with pytest.raises(PseudonymKeyInvalid):
        write_key(REPO_ROOT / "out" / "study.key", new_key(), PASS)


def test_plain_hex_key_files_still_load(tmp_path):
    key = new_key()
    path = tmp_path / "old.txt"
    path.write_text(key.hex() + "\n", encoding="utf-8")
    assert read_key(path) == key
