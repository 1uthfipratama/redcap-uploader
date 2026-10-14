"""Handle identifier columns straight after parsing.

- record_id: keyed hash (HMAC-SHA256) of the form code and the patient register
  number, so each episode is its own REDCap record.
- patient_pid: keyed hash of the cleaned NIK, so one patient's episodes link.
- other pseudonymised columns: keyed hash into their own field.
- dropped columns and quasi-identifiers (unless kept): removed.

After apply_identifiers() returns, no raw identifier value exists in the table,
the report, the issues or the log. Reports carry counts and row numbers only.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from core.issues import ERROR, WARNING, Issue
from core.parse import ROW
from core.profile import PATIENT_ID_FIELD, RECORD_ID_FIELD, Profile, Role

log = logging.getLogger("redcap_uploader.identifiers")

KEY_ENV = "REDCAP_UPLOADER_PSEUDONYM_KEY"  # hex string
KEY_FILE_ENV = "REDCAP_UPLOADER_KEY_FILE"  # path to a file holding the hex key
MIN_KEY_BYTES = 32
PSEUDONYM_HEX_CHARS = 16  # 64 bits; collisions are checked anyway
NIK_DIGITS = 16
FLOAT_EXACT_LIMIT = 2**53  # larger whole numbers stored as floats may have lost digits
REPO_ROOT = Path(__file__).resolve().parent.parent


class PseudonymKeyMissing(RuntimeError):
    """No pseudonym key is configured; pseudonymising is refused."""


class PseudonymKeyInvalid(RuntimeError):
    """The configured key is too short, unreadable, or stored inside the repo."""


def load_key() -> bytes:
    """Read the project key from the environment or a key file outside the repo.

    There is no default key. Tests pass their own clearly named test key to
    apply_identifiers() directly instead of calling this.
    """
    if os.environ.get(KEY_ENV):
        return _parse_key(os.environ[KEY_ENV])
    if os.environ.get(KEY_FILE_ENV):
        return read_key_file(os.environ[KEY_FILE_ENV])
    raise PseudonymKeyMissing(f"set {KEY_ENV} or {KEY_FILE_ENV}")


def read_key_file(path: str | Path) -> bytes:
    """A key file holds the key as hex. It must live outside the repo."""
    path = Path(path).resolve()
    if REPO_ROOT in path.parents:
        raise PseudonymKeyInvalid("key file must be outside the repo")
    try:
        return _parse_key(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise PseudonymKeyInvalid("key file cannot be read") from exc


def _parse_key(text: str) -> bytes:
    try:
        key = bytes.fromhex(text.strip())
    except ValueError as exc:
        raise PseudonymKeyInvalid("key must be hex") from exc
    if len(key) < MIN_KEY_BYTES:
        raise PseudonymKeyInvalid(f"key must be at least {MIN_KEY_BYTES} bytes")
    return key


def pseudonym(key: bytes, purpose: str, *parts: str) -> str:
    message = "\x1f".join((purpose, *parts)).encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()[:PSEUDONYM_HEX_CHARS]


def clean_nik(value: object) -> tuple[str | None, str]:
    """Return (cleaned NIK or None, status). Status is a reason code, never the value."""
    if value is None:
        return None, "blank"
    if isinstance(value, float):
        if not value.is_integer():
            return None, "not_digits"
        if abs(value) >= FLOAT_EXACT_LIMIT:
            return None, "precision_lost"
        value = int(value)
    text = str(value).strip().lstrip("'").strip()
    if not text:
        return None, "blank"
    if re.search(r"\d[.,]?\d*e[+-]?\d+", text, re.IGNORECASE):
        return None, "scientific"
    text = re.sub(r"[\s-]", "", text)
    if not text.isdigit():
        return None, "not_digits"
    if len(text) != NIK_DIGITS:
        return None, "wrong_length"
    if set(text) == {"0"}:
        return None, "all_zero"
    return text, "ok"


def clean_register_number(value: object) -> str | None:
    """Register numbers as text: whole-number floats lose their '.0', apostrophes and spaces go."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip().lstrip("'").strip()
    return text or None


@dataclass
class IdentifierReport:
    dropped: list[str] = field(default_factory=list)  # column keys
    quasi_dropped: list[str] = field(default_factory=list)
    quasi_kept: list[str] = field(default_factory=list)
    pseudonymised: dict[str, int] = field(default_factory=dict)  # field -> rows given a pseudonym
    record_id_missing_rows: list[int] = field(default_factory=list)
    nik_status: Counter = field(default_factory=Counter)
    nik_problem_rows: list[int] = field(default_factory=list)


def apply_identifiers(frame: pd.DataFrame, profile: Profile, key: bytes) -> tuple[pd.DataFrame, IdentifierReport, list[Issue]]:
    """Return a copy of the table with identifiers dropped or pseudonymised."""
    if not key or len(key) < MIN_KEY_BYTES:
        raise PseudonymKeyInvalid(f"key must be at least {MIN_KEY_BYTES} bytes")
    out = frame.copy()
    report = IdentifierReport()
    issues: list[Issue] = []
    form = profile.identity.form_code
    rows = [int(r) for r in out[ROW]]
    for spec in profile.columns:
        if spec.key not in out.columns:
            continue
        if spec.role == Role.record_id_source:
            cleaned = [_scoped(x, scope_row) for x, scope_row in zip(out[spec.key], _scope_values(out, profile))]
            ids = _hash_all(key, ("record", form), cleaned, issues)
            out[RECORD_ID_FIELD] = pd.Series(ids, index=out.index, dtype=object)
            report.record_id_missing_rows = [r for r, i in zip(rows, ids) if i is None]
            report.pseudonymised[RECORD_ID_FIELD] = len(ids) - len(report.record_id_missing_rows)
            issues += [Issue("record_id_source_blank", ERROR, row=r, params={"column": spec.label})
                       for r in report.record_id_missing_rows]
            out = out.drop(columns=spec.key)
        elif spec.role == Role.patient_id_source:
            cleaned = []
            for row, raw in zip(rows, out[spec.key]):
                nik, status = clean_nik(raw)
                report.nik_status[status] += 1
                cleaned.append(nik)
                if nik is None:
                    report.nik_problem_rows.append(row)
                    issues.append(Issue(f"nik_{status}", WARNING, row=row))
            pids = _hash_all(key, ("patient",), cleaned, issues)
            out[PATIENT_ID_FIELD] = pd.Series(pids, index=out.index, dtype=object)
            report.pseudonymised[PATIENT_ID_FIELD] = sum(p is not None for p in pids)
            out = out.drop(columns=spec.key)
        elif spec.role == Role.identifier_pseudonymise:
            cleaned = [clean_register_number(x) for x in out[spec.key]]
            values = _hash_all(key, (spec.field,), cleaned, issues)
            out[spec.key] = pd.Series(values, index=out.index, dtype=object)
            report.pseudonymised[spec.field] = sum(v is not None for v in values)
        elif spec.role == Role.identifier_drop:
            out = out.drop(columns=spec.key)
            report.dropped.append(spec.key)
        elif spec.role == Role.quasi_identifier:
            if spec.keep:
                report.quasi_kept.append(spec.key)
            else:
                out = out.drop(columns=spec.key)
                report.quasi_dropped.append(spec.key)
    log.info(
        "identifiers handled: %d dropped, %d quasi dropped, pseudonymised %s, NIK status %s",
        len(report.dropped), len(report.quasi_dropped), report.pseudonymised, dict(report.nik_status),
    )
    return out, report, issues


def _scope_values(frame: pd.DataFrame, profile: Profile) -> list[tuple[str, ...]]:
    """Per row, the cleaned values of the record_id scope columns (for example the facility code)."""
    keys = [k for k in profile.record_id_scope if k in frame.columns]
    return [tuple(clean_register_number(frame.at[i, k]) or "" for k in keys) for i in frame.index]


def _scoped(register_number: object, scope: tuple[str, ...]) -> str | None:
    """The text hashed into record_id: scope values, then the register number. None if no number."""
    number = clean_register_number(register_number)
    return None if number is None else "".join((*scope, number))


def _hash_all(key: bytes, purpose: tuple[str, ...], cleaned: list[str | None], issues: list[Issue]) -> list[str | None]:
    """Hash each cleaned value; two different values giving one pseudonym is reported as an error."""
    seen: dict[str, str] = {}
    out: list[str | None] = []
    for value in cleaned:
        if value is None:
            out.append(None)
            continue
        digest = pseudonym(key, *purpose, value)
        if seen.setdefault(digest, value) != value:
            issues.append(Issue("pseudonym_collision", ERROR, params={"purpose": purpose[0]}))
        out.append(digest)
    return out
