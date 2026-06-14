"""Small HTTP server for the frontend and runtime state API."""

from __future__ import annotations

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Callable
from urllib.parse import unquote


StateProvider = Callable[[], dict[str, object]]
EventTrigger = Callable[[str, str], bool]
StartEventTrigger = Callable[[str], bool]
RuntimeKiller = Callable[[str], bool]
EventReloader = Callable[[], None]


class FrontendRequestHandler(SimpleHTTPRequestHandler):
    """Serve static frontend files and small JSON control API."""

    def __init__(
        self,
        *args,
        state_provider: StateProvider,
        event_trigger: EventTrigger,
        start_event_trigger: StartEventTrigger,
        runtime_killer: RuntimeKiller,
        event_reloader: EventReloader,
        **kwargs,
    ):
        """Create a request handler bound to runtime callbacks."""
        self.state_provider = state_provider
        self.event_trigger = event_trigger
        self.start_event_trigger = start_event_trigger
        self.runtime_killer = runtime_killer
        self.event_reloader = event_reloader
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args) -> None:
        """Keep routine frontend requests out of the event log."""
        return

    def do_GET(self):
        """Handle runtime state API requests or fall back to static files."""
        if self.path in ("/api/runtime", "/api/runtimes"):
            self._send_runtime_state()
            return

        super().do_GET()

    def do_POST(self):
        """Handle event trigger and config reload API requests."""
        parts = self.path.strip("/").split("/")

        if self.path == "/api/events/reload":
            self._reload_events()
            return

        if len(parts) == 3 and parts[0] == "api" and parts[1] == "events":
            self._trigger_start_event(unquote(parts[2]))
            return

        if len(parts) == 5 and parts[0] == "api" and parts[1] == "runtimes" and parts[3] == "events":
            self._trigger_runtime_event(unquote(parts[2]), unquote(parts[4]))
            return

        self.send_error(404)

    def do_DELETE(self):
        """Handle runtime deletion API requests."""
        parts = self.path.strip("/").split("/")

        if len(parts) == 3 and parts[0] == "api" and parts[1] == "runtimes":
            self._kill_runtime(unquote(parts[2]))
            return

        self.send_error(404)

    def _send_runtime_state(self) -> None:
        """Return current runtime state as JSON."""
        self._send_json(200, self.state_provider())

    def _reload_events(self) -> None:
        """Reload event config and report validation errors to the frontend."""
        try:
            self.event_reloader()
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})
            return

        self._send_ok()

    def _trigger_start_event(self, event_id: str) -> None:
        """Trigger a global start event that may create a runtime."""
        if not self.start_event_trigger(event_id):
            self.send_error(409)
            return

        self._send_ok()

    def _trigger_runtime_event(self, runtime_id: str, event_id: str) -> None:
        """Trigger an event inside one active runtime."""
        if not self.event_trigger(runtime_id, event_id):
            self.send_error(404)
            return

        self._send_ok()

    def _kill_runtime(self, runtime_id: str) -> None:
        """Stop and remove one active runtime."""
        if not self.runtime_killer(runtime_id):
            self.send_error(404)
            return

        self._send_ok()

    def _send_ok(self) -> None:
        """Return a standard successful JSON response."""
        self._send_json(200, {"ok": True})

    def _send_json(self, status: int, data: object) -> None:
        """Return JSON with common headers."""
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class FrontendServer:
    """Runs the frontend server separately from the main loop."""

    def __init__(
        self,
        frontend_dir: Path,
        state_provider: StateProvider,
        event_trigger: EventTrigger,
        start_event_trigger: StartEventTrigger,
        runtime_killer: RuntimeKiller,
        event_reloader: EventReloader,
        host: str,
        port: int,
    ):
        """Prepare the HTTP server for static files and API requests."""
        handler = partial(
            FrontendRequestHandler,
            directory=str(frontend_dir),
            state_provider=state_provider,
            event_trigger=event_trigger,
            start_event_trigger=start_event_trigger,
            runtime_killer=runtime_killer,
            event_reloader=event_reloader,
        )
        self.url = f"http://{host}:{port}"
        self.server = ThreadingHTTPServer((host, port), handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def start(self) -> None:
        """Start serving requests on a background thread."""
        self.thread.start()

    def stop(self) -> None:
        """Stop the HTTP server and close its socket."""
        self.server.shutdown()
        self.server.server_close()
