"""Log exactly which API requests PyCap sends, so the mock implements those and nothing it guesses.

Starts a throwaway local HTTP server that records every POST (token masked) and
answers with minimal, plausible bodies, then drives PyCap through what the app
does: connect, read project info and the data dictionary, import, export.

    python -m tools.observe_pycap

Re-run after upgrading PyCap and compare with docs/REDCAP_ASSUMPTIONS.md.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

SEEN: list[dict] = []
FAKE_TOKEN = "0" * 32

RESPONSES = {
    "version": "14.5.0",
    "project": json.dumps({"project_id": 1, "project_title": "Observer", "is_longitudinal": 0,
                           "has_repeating_instruments_or_events": 0}),
    "metadata": json.dumps([{"field_name": "record_id", "form_name": "f", "field_type": "text"}]),
    "exportFieldNames": json.dumps([{"original_field_name": "record_id", "export_field_name": "record_id"}]),
    "record": json.dumps([]),
}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 (http.server API)
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        form = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(body).items()}
        form["token"] = "***"
        if "data" in form:
            form["data"] = f"<{len(form['data'])} chars>"
        SEEN.append(form)
        content = form.get("content", "")
        if content == "record" and form.get("action") == "import":
            reply = json.dumps({"count": 1})
        else:
            reply = RESPONSES.get(content, json.dumps({"error": f"observer: no reply for {content}"}))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(reply.encode())

    def log_message(self, *args):
        pass


def main() -> None:
    from redcap import Project

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/api/"

    steps = [
        ("Project(url, token)", lambda p: None),
        ("redcap_version", lambda p: p.redcap_version),
        ("export_project_info()", lambda p: p.export_project_info()),
        ("export_metadata()", lambda p: p.export_metadata()),
        ("field_names / def_field", lambda p: (p.field_names, p.def_field)),
        ("is_longitudinal", lambda p: p.is_longitudinal),
        ("export_records(fields=[def_field])", lambda p: p.export_records(fields=[p.def_field])),
        ("import_records(normal, count)", lambda p: p.import_records([{"record_id": "a"}], overwrite="normal",
                                                                      return_content="count")),
        ("import_records(normal, ids)", lambda p: p.import_records([{"record_id": "a"}], overwrite="normal",
                                                                    return_content="ids")),
        ("export_records()", lambda p: p.export_records()),
    ]
    project = None
    for name, step in steps:
        before = len(SEEN)
        project = project or Project(url, FAKE_TOKEN)
        try:
            step(project)
        except Exception as exc:  # noqa: BLE001 - we only want to log what happened
            print(f"{name}: raised {type(exc).__name__}: {exc}")
        print(f"{name}: {len(SEEN) - before} request(s)")
        for form in SEEN[before:]:
            print("   ", json.dumps(form, sort_keys=True))
    server.shutdown()


if __name__ == "__main__":
    main()
