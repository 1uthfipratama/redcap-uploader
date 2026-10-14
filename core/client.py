"""The only module that imports PyCap.

A thin wrapper over PyCap's Project that:
- records every request (content type and parameters, token masked, record data
  reduced to a count) for the "What's happening?" panels;
- turns PyCap's errors into ConnectionFailed or ApiError, with REDCap's import
  error lines parsed into (record, field, value, message);
- never puts the token in a log entry, an exception or a repr.
"""

from __future__ import annotations

import csv
import io
import json
import time
from dataclasses import dataclass, field

import requests
from redcap import Project

MASK = "********"


@dataclass
class RequestLog:
    content: str
    params: dict[str, str]  # token masked, data reduced to a count
    ok: bool = True
    message: str = ""
    seconds: float = 0.0


@dataclass
class ImportProblem:
    record: str
    field: str
    value: str
    message: str


class ConnectionFailed(Exception):
    """The server could not be reached (wrong URL, no network, VPN off, timeout)."""


class InvalidSettings(ValueError):
    """The URL or token has the wrong shape. The message never contains the token."""

    def __init__(self, what: str):
        super().__init__(what)
        self.what = what  # "url" or "token"


class ApiError(Exception):
    """REDCap answered with an error."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        self.problems = parse_error_lines(message)


@dataclass
class ProjectInfo:
    title: str
    version: str
    is_longitudinal: bool
    record_id_field: str
    fields: list[str]
    dictionary: list[dict[str, str]] = field(repr=False)


class _LoggedProject(Project):
    """PyCap's Project with every API call recorded in a shared log."""

    def __init__(self, url: str, token: str, log: list[RequestLog], timeout: float):
        super().__init__(url, token, verify_ssl=True, timeout=timeout)
        self._log = log

    def _call_api(self, payload, return_type, file=None):
        entry = RequestLog(content=str(payload.get("content", "")), params=mask_payload(payload))
        self._log.append(entry)
        start = time.perf_counter()
        try:
            return super()._call_api(payload, return_type, file)
        except Exception as exc:
            entry.ok = False
            entry.message = _error_text(exc)
            raise
        finally:
            entry.seconds = round(time.perf_counter() - start, 3)


def check_settings(url: str, token: str) -> None:
    """Our own checks, so PyCap's assertion (whose message quotes the token) never fires."""
    if not url or not url.rstrip().endswith("/api/") or not url.startswith(("http://", "https://")):
        raise InvalidSettings("url")
    if not token or len(token) != 32 or not token.isalnum():
        raise InvalidSettings("token")


def mask_payload(payload: dict) -> dict[str, str]:
    out = {}
    for key, value in payload.items():
        if key == "token":
            out[key] = MASK
        elif key == "data":
            out[key] = f"<{_count_records(value)} records>"
        else:
            out[key] = str(value)
    return out


def _count_records(data) -> int:
    try:
        parsed = json.loads(data) if isinstance(data, str) else data
        return len(parsed)
    except (TypeError, ValueError):
        return max(len(str(data).splitlines()) - 1, 0)


def _error_text(exc: Exception) -> str:
    arg = exc.args[0] if exc.args else ""
    if isinstance(arg, dict) and "error" in arg:
        return str(arg["error"])
    return str(arg) if arg else type(exc).__name__


def parse_error_lines(message: str) -> list[ImportProblem]:
    """REDCap import errors: one '"record","field","value","message"' line per problem (A07)."""
    problems = []
    for row in csv.reader(io.StringIO(message)):
        if len(row) == 4:
            problems.append(ImportProblem(*[x.strip() for x in row]))
    if not problems and message.strip():
        problems.append(ImportProblem("", "", "", message.strip()))
    return problems


class RedcapClient:
    """One REDCap project, reached by URL and token. Switching Demo to Real changes only these two."""

    def __init__(self, url: str, token: str, timeout: float = 60):
        check_settings(url, token)
        self.url = url
        self.log: list[RequestLog] = []
        try:
            self._project = _LoggedProject(url, token, self.log, timeout)
        except AssertionError:
            # PyCap's own message quotes the token; never let it through.
            raise InvalidSettings("token") from None

    def __repr__(self) -> str:
        return f"RedcapClient(url={self.url!r}, token={MASK})"

    def _call(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            raise ConnectionFailed(f"Could not reach {self.url}") from None
        except requests.exceptions.RequestException as exc:  # PyCap's RedcapError is this class
            raise ApiError(_error_text(exc)) from None

    def connect(self) -> ProjectInfo:
        version = self._call(lambda: self._project.redcap_version)
        info = self._call(self._project.export_project_info)
        dictionary = self._call(self._project.export_metadata)
        return ProjectInfo(
            title=str(info.get("project_title", "")),
            version=str(version) if version else "",
            is_longitudinal=bool(int(info.get("is_longitudinal", 0) or 0)),
            record_id_field=dictionary[0]["field_name"] if dictionary else "",
            fields=[r["field_name"] for r in dictionary],
            dictionary=dictionary,
        )

    def existing_record_ids(self, record_id_field: str) -> set[str]:
        rows = self._call(self._project.export_records, fields=[record_id_field])
        return {str(r[record_id_field]) for r in rows}

    def import_records(self, records: list[dict[str, str]], overwrite: str = "normal") -> list[str]:
        """Import one batch; returns the saved record IDs. All-or-nothing (A06)."""
        return self._call(self._project.import_records, records, overwrite=overwrite,
                          return_content="ids", date_format="YMD")

    def export_records(self, fields: list[str] | None = None, records: list[str] | None = None) -> list[dict]:
        return self._call(self._project.export_records, fields=fields, records=records)
