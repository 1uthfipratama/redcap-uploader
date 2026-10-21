"""Run the mock REDCap on 127.0.0.1 and a free port, in a background thread."""

from __future__ import annotations

import secrets
import threading

from werkzeug.serving import WSGIRequestHandler, make_server

from mock_redcap.server import MockProject, create_app


class _QuietHandler(WSGIRequestHandler):
    """No per-request lines on the console; the client keeps its own request log."""

    def log_request(self, *args, **kwargs) -> None:
        pass


def new_demo_token() -> str:
    """A random token in REDCap's format (32 hex characters), new for every run."""
    return secrets.token_hex(16).upper()


class MockRedcap:
    """Start with `with MockRedcap(dictionary) as mock:`; then use mock.url and mock.token."""

    def __init__(self, dictionary: list[dict[str, str]], title: str = "Demo project (mock REDCap)"):
        self.project = MockProject(token=new_demo_token(), dictionary=dictionary, title=title)
        self._server = None
        self._thread = None

    @property
    def token(self) -> str:
        return self.project.token

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/api/"

    def start(self) -> "MockRedcap":
        app = create_app(self.project)
        self._server = make_server("127.0.0.1", 0, app, threaded=True, request_handler=_QuietHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, name="mock-redcap", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._thread.join(timeout=5)
            self._server = None

    def __enter__(self) -> "MockRedcap":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()
