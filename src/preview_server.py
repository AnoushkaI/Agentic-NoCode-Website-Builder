"""
Lightweight local HTTP preview server for SitePilot AI.
Serves the latest rendered WebsiteState HTML on a local localhost port
so users can open and interact with the generated website in a separate browser tab.
Thread-safe, zero external dependencies, non-blocking background daemon thread.
"""

import http.server
import logging
import socket
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_PORT = 8765
_LATEST_HTML: str = "<!DOCTYPE html><html><body><h3>No website generated yet.</h3></body></html>"
_HTML_LOCK = threading.Lock()
_SERVER_INSTANCE: Optional[http.server.HTTPServer] = None
_SERVER_THREAD: Optional[threading.Thread] = None
_SERVER_PORT: Optional[int] = None


class _PreviewRequestHandler(http.server.BaseHTTPRequestHandler):
    """Simple HTTP request handler that serves the latest in-memory website HTML."""

    def do_GET(self):
        with _HTML_LOCK:
            content = _LATEST_HTML.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        # Suppress standard HTTP request logging to avoid cluttering console
        pass


def _find_free_port(start_port: int = _DEFAULT_PORT, max_attempts: int = 30) -> int:
    """Find an available TCP port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    # Fallback to OS-assigned port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_preview_server(port: Optional[int] = None) -> int:
    """
    Start the local preview HTTP server in a daemon background thread if not already running.
    Returns the active port number.
    """
    global _SERVER_INSTANCE, _SERVER_THREAD, _SERVER_PORT

    if _SERVER_INSTANCE is not None and _SERVER_PORT is not None:
        return _SERVER_PORT

    chosen_port = port or _find_free_port()
    try:
        server = http.server.HTTPServer(("127.0.0.1", chosen_port), _PreviewRequestHandler)
        _SERVER_INSTANCE = server
        _SERVER_PORT = chosen_port

        thread = threading.Thread(target=server.serve_forever, daemon=True, name="SitePilotPreviewServer")
        thread.start()
        _SERVER_THREAD = thread
        logger.info("SitePilot preview server started at http://localhost:%d/", chosen_port)
    except Exception as e:
        logger.warning("Could not start preview server on port %d: %s. Using OS free port.", chosen_port, e)
        server = http.server.HTTPServer(("127.0.0.1", 0), _PreviewRequestHandler)
        _SERVER_PORT = server.server_address[1]
        _SERVER_INSTANCE = server
        thread = threading.Thread(target=server.serve_forever, daemon=True, name="SitePilotPreviewServer")
        thread.start()
        _SERVER_THREAD = thread

    return _SERVER_PORT


def update_preview_html(html_content: str) -> str:
    """
    Update the HTML content currently being served by the preview server.
    Ensures server is running and returns the full preview URL (e.g. http://localhost:8765/).
    """
    global _LATEST_HTML

    with _HTML_LOCK:
        _LATEST_HTML = html_content or ""

    port = start_preview_server()
    return f"http://localhost:{port}/"


def get_preview_url() -> Optional[str]:
    """Return the current preview URL if the server is active."""
    if _SERVER_PORT is not None:
        return f"http://localhost:{_SERVER_PORT}/"
    return None


def get_latest_preview_html() -> str:
    """Return the current in-memory preview HTML."""
    with _HTML_LOCK:
        return _LATEST_HTML
