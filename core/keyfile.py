"""Creating, protecting and backing up the pseudonym key.

The key turns NIKs and register numbers into pseudonyms (core/identifiers.py). Losing it
means next month's pseudonyms no longer match this month's; leaking it, together with a
list of NIKs, lets someone find those people in REDCap. So a key the app creates is:

- random (32 bytes from the operating system's secure generator);
- never written in plain text: the file holds it encrypted with a passphrase
  (scrypt to derive a key-encryption key, the key XORed with it, and an HMAC that
  detects a wrong passphrase or a damaged file), using only Python's standard library;
- never written over an existing file, and never inside the app's own folder;
- known to people by its fingerprint, a short code that shows whether two copies are
  the same key without revealing it.

Plain hex key files (an older format, and the environment variables) still load.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

from core.identifiers import MIN_KEY_BYTES, REPO_ROOT, PseudonymKeyInvalid, _parse_key

FORMAT = "redcap-uploader-pseudonym-key"
VERSION = 1
KEY_BYTES = 32
MIN_PASSPHRASE = 10
SCRYPT = {"n": 2**15, "r": 8, "p": 1}  # about 32 MB and a fraction of a second per unlock
KEY_SUFFIX = ".key"


class PassphraseNeeded(Exception):
    """The key file is protected; ask the person for its passphrase."""


class WrongPassphrase(Exception):
    """The passphrase does not open this key file (or the file was changed)."""


class KeyFileExists(Exception):
    """A file is already there; a key file is never written over."""


def new_key() -> bytes:
    return secrets.token_bytes(KEY_BYTES)


def fingerprint(key: bytes) -> str:
    """A short code, such as 7F3A-91C2, that is the same for the same key and reveals nothing about it."""
    digest = hashlib.sha256(b"redcap-uploader key fingerprint\x00" + key).hexdigest().upper()
    return f"{digest[:4]}-{digest[4:8]}"


def _derive(passphrase: str, salt: bytes, length: int, params: dict) -> tuple[bytes, bytes]:
    derived = hashlib.scrypt(passphrase.encode("utf-8"), salt=salt, n=params["n"], r=params["r"], p=params["p"],
                             maxmem=128 * 1024 * 1024, dklen=length + 32)
    return derived[:length], derived[length:]


def protect(key: bytes, passphrase: str) -> str:
    """The key, encrypted with the passphrase, as the text of a key file."""
    if len(passphrase) < MIN_PASSPHRASE:
        raise ValueError(f"passphrase shorter than {MIN_PASSPHRASE} characters")
    salt = secrets.token_bytes(16)
    stream, mac_key = _derive(passphrase, salt, len(key), SCRYPT)
    sealed = bytes(a ^ b for a, b in zip(key, stream))
    mac = hmac.new(mac_key, salt + sealed, hashlib.sha256).hexdigest()
    return json.dumps({
        "format": FORMAT, "version": VERSION, "kdf": "scrypt", **SCRYPT,
        "salt": salt.hex(), "sealed_key": sealed.hex(), "mac": mac, "fingerprint": fingerprint(key),
    }, indent=2) + "\n"


def is_protected(text: str) -> bool:
    return text.lstrip().startswith("{") and FORMAT in text


def unprotect(text: str, passphrase: str) -> bytes:
    try:
        data = json.loads(text)
        salt, sealed = bytes.fromhex(data["salt"]), bytes.fromhex(data["sealed_key"])
        params = {k: int(data[k]) for k in ("n", "r", "p")}
    except (ValueError, KeyError, TypeError) as exc:
        raise PseudonymKeyInvalid("key file is damaged") from exc
    if data.get("format") != FORMAT or data.get("kdf") != "scrypt":
        raise PseudonymKeyInvalid("not a key file of this app")
    stream, mac_key = _derive(passphrase, salt, len(sealed), params)
    expected = hmac.new(mac_key, salt + sealed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(data.get("mac", ""))):
        raise WrongPassphrase()
    key = bytes(a ^ b for a, b in zip(sealed, stream))
    if len(key) < MIN_KEY_BYTES:
        raise PseudonymKeyInvalid("key too short")
    return key


def _check_location(path: Path) -> Path:
    path = Path(path).resolve()
    if REPO_ROOT in path.parents:
        raise PseudonymKeyInvalid("key file must be outside the app's folder")
    return path


def read_key(path: str | Path, passphrase: str | None = None) -> bytes:
    """A key from a protected key file (needs the passphrase) or a plain hex one."""
    path = _check_location(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PseudonymKeyInvalid("key file cannot be read") from exc
    if is_protected(text):
        if passphrase is None:
            raise PassphraseNeeded()
        return unprotect(text, passphrase)
    return _parse_key(text)


def write_key(path: str | Path, key: bytes, passphrase: str) -> Path:
    """Save the key, protected by the passphrase. Never writes over a file, never inside the app's folder."""
    path = _check_location(path)
    text = protect(key, passphrase)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "x", encoding="utf-8", newline="\n") as fh:  # "x": fail if the file exists
            fh.write(text)
    except FileExistsError as exc:
        raise KeyFileExists(str(path)) from exc
    if os.name == "posix":
        os.chmod(path, 0o600)  # only the owner may read it
    return path
