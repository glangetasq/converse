from __future__ import annotations

import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROFILE_PATH = re.compile(r"^/in/[^/]+/?$")


def resolve_page(path: str) -> Path | None:
    if path.startswith("/messaging"):
        return ROOT / "messaging.html"
    if PROFILE_PATH.match(path):
        return ROOT / "profile.html"
    if path == "/":
        return ROOT / "home.html"
    return None


class MiniLinkedInHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        page = resolve_page(self.path.split("?", 1)[0])
        if page is None or not page.is_file():
            self.send_error(404, "Not Found")
            return

        body = page.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    server = ThreadingHTTPServer(("127.0.0.1", port), MiniLinkedInHandler)
    print(f"mini-linkedin serving on http://localhost:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
