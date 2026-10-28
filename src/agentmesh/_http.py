"""Small JSON-over-HTTP helpers shared by the reference agent, registry and client.

Only the Python standard library is used, so the reference services run anywhere the
``agentmesh`` package installs.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

logger = logging.getLogger("agentmesh")

MAX_BODY_BYTES = 1024 * 1024  # 1 MiB


@dataclass
class Request:
    method: str
    path: str
    params: dict[str, str]
    query: dict[str, str]
    body: Any


@dataclass
class Response:
    status: int
    body: Any = None


class HTTPError(Exception):
    """An error a route raises to produce a JSON error response."""

    def __init__(self, status: int, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details

    def to_body(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            error["details"] = self.details
        return {"error": error}


Route = Callable[[Request], Response]


class Router:
    """Maps ``(method, path pattern)`` to route functions; ``{name}`` matches one segment."""

    def __init__(self) -> None:
        self._routes: list[tuple[str, re.Pattern[str], Route]] = []

    def add(self, method: str, pattern: str, func: Route) -> None:
        regex = "^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern) + "$"
        self._routes.append((method, re.compile(regex), func))

    def resolve(self, method: str, path: str) -> tuple[Route, dict[str, str]]:
        allowed = False
        for route_method, regex, func in self._routes:
            match = regex.match(path)
            if not match:
                continue
            if route_method == method:
                return func, {k: unquote(v) for k, v in match.groupdict().items()}
            allowed = True
        if allowed:
            raise HTTPError(
                HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", "method not allowed"
            )
        raise HTTPError(HTTPStatus.NOT_FOUND, "not_found", f"no route for {path}")


def _parse_json(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPError(
            HTTPStatus.BAD_REQUEST, "invalid_json", f"request body is not JSON: {exc}"
        ) from exc


def _make_handler(router: Router, max_body_bytes: int) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "AgentMesh"
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:
            logger.debug("%s - %s", self.address_string(), format % args)

        def _send(self, status: int, body: Any) -> None:
            data = b"" if body is None else json.dumps(body).encode("utf-8")
            self.send_response(status)
            if body is not None:
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if data:
                self.wfile.write(data)

        def _read_raw(self) -> bytes:
            """Read the whole request body so a kept-alive connection stays in sync."""
            if self.headers.get("Transfer-Encoding"):
                self.close_connection = True
                raise HTTPError(
                    HTTPStatus.LENGTH_REQUIRED,
                    "length_required",
                    "chunked request bodies are not supported; send Content-Length",
                )
            length_header = self.headers.get("Content-Length")
            if not length_header:
                return b""
            try:
                length = int(length_header)
            except ValueError:
                length = -1
            if length < 0:
                self.close_connection = True
                raise HTTPError(HTTPStatus.BAD_REQUEST, "bad_request", "invalid Content-Length")
            if length > max_body_bytes:
                self.close_connection = True
                raise HTTPError(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "payload_too_large",
                    f"request body exceeds {max_body_bytes} bytes",
                )
            return self.rfile.read(length)

        def _dispatch(self) -> None:
            try:
                raw = self._read_raw()
                split = urlsplit(self.path)
                path = split.path.rstrip("/") or "/"
                func, params = router.resolve(self.command, path)
                query = {k: v[-1] for k, v in parse_qs(split.query).items()}
                response = func(Request(self.command, path, params, query, _parse_json(raw)))
                self._send(response.status, response.body)
            except HTTPError as exc:
                self._send(exc.status, exc.to_body())
            except Exception:  # pragma: no cover - defensive: never leak a traceback
                logger.exception("unhandled error serving %s %s", self.command, self.path)
                self._send(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": {"code": "internal_error", "message": "internal server error"}},
                )

        do_GET = do_POST = do_PUT = do_DELETE = _dispatch

    return Handler


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    # socketserver's default listen backlog of 5 resets connections under modest bursts.
    request_queue_size = 128


class RunningServer:
    """A JSON HTTP server running in a background thread."""

    def __init__(self, router: Router, host: str, port: int, max_body_bytes: int = MAX_BODY_BYTES):
        self._httpd = _Server((host, port), _make_handler(router, max_body_bytes))
        self.host = host
        self.port = self._httpd.server_address[1]
        self._thread: threading.Thread | None = None
        self._on_close: list[Callable[[], None]] = []

    @property
    def url(self) -> str:
        host = self.host
        if host in ("0.0.0.0", ""):
            host = "127.0.0.1"
        elif host == "::":
            host = "::1"
        if ":" in host:
            host = f"[{host}]"
        return f"http://{host}:{self.port}"

    def start(self) -> RunningServer:
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            kwargs={"poll_interval": 0.1},  # how quickly close() can stop the loop
            name=f"agentmesh-http-{self.port}",
            daemon=True,
        )
        self._thread.start()
        return self

    def serve_forever(self) -> None:
        """Serve in the calling thread until interrupted (used by the CLI)."""
        try:
            self._httpd.serve_forever()
        finally:
            self.close()

    def on_close(self, callback: Callable[[], None]) -> None:
        self._on_close.append(callback)

    def close(self) -> None:
        if self._thread is not None:
            self._httpd.shutdown()
            self._thread.join(timeout=5)
            self._thread = None
        self._httpd.server_close()
        callbacks, self._on_close = self._on_close, []
        for callback in callbacks:
            callback()

    def __enter__(self) -> RunningServer:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class AgentMeshHTTPError(Exception):
    """Raised by the clients when a service answers with an HTTP error."""

    def __init__(self, status: int, body: Any, url: str):
        self.status = status
        self.body = body
        self.url = url
        error = body.get("error") if isinstance(body, dict) else None
        self.code = error.get("code") if isinstance(error, dict) else None
        detail = error.get("message") if isinstance(error, dict) else body
        super().__init__(f"HTTP {status} from {url}: {detail}")


def request_json(method: str, url: str, body: Any = None, timeout: float = 10.0) -> tuple[int, Any]:
    """Send a JSON request and return ``(status, parsed body)``.

    Raises :class:`AgentMeshHTTPError` for 4xx/5xx answers and ``OSError`` (for example
    ``urllib.error.URLError``) when the service cannot be reached.
    """
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw.decode("utf-8", "replace")
        raise AgentMeshHTTPError(exc.code, parsed, url) from None
