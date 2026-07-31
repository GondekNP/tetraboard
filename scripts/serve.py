#!/usr/bin/env python3
"""No-cache static file server with live-reload for local Sketchingpy / PyScript dev.

Run with:
    python scripts/serve.py [port]

Serves the ./web directory (defaults to port 8000).

* No-cache headers on every response.
* Auto-reload: injects a small JS snippet into HTML responses that polls
  /livereload-version and reloads when any file in web/ changes.
* File watching via `watchfiles` (event-driven, no polling).
"""
import http.server
import socketserver
import sys
import threading
from pathlib import Path

import watchfiles

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
DEFAULT_PORT = 8000

# ── live-reload state ────────────────────────────────────────────────
_version_lock = threading.Lock()
_version = 0


def _watch_files() -> None:
    global _version
    for _ in watchfiles.watch(WEB_DIR):
        with _version_lock:
            _version += 1


_LIVERELOAD_SNIPPET = b"""
<script>
(function(){
  var v = null;
  function poll(){
    fetch('/livereload-version')
      .then(function(r){ return r.text(); })
      .then(function(t){
        if(v === null){ v = t; }
        else if(v !== t){ location.reload(); }
      })
      .catch(function(){})
      .finally(function(){ setTimeout(poll, 800); });
  }
  poll();
})();
</script>
"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        # ── live-reload version endpoint ──────────────────────────────
        if self.path == "/livereload-version":
            with _version_lock:
                v = str(_version).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(v)))
            self.end_headers()
            self.wfile.write(v)
            return

        # ── HTML files: inject live-reload snippet ────────────────────
        path = self.translate_path(self.path)
        if Path(path).is_dir():
            for index in ("index.html", "index.htm"):
                candidate = Path(path) / index
                if candidate.is_file():
                    path = str(candidate)
                    break

        if Path(path).suffix in (".html", ".htm") and Path(path).is_file():
            content = Path(path).read_bytes()
            content = content.replace(b"</body>", _LIVERELOAD_SNIPPET + b"</body>", 1)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        super().do_GET()

    def log_message(self, fmt, *args):
        first = str(args[0]) if args else ""
        if "/livereload-version" in first:
            return
        super().log_message(fmt, *args)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT

    threading.Thread(target=_watch_files, daemon=True).start()

    def handler_factory(*args, **kwargs):
        return Handler(*args, directory=str(WEB_DIR), **kwargs)

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), handler_factory) as httpd:
        print(f"Serving {WEB_DIR} at http://localhost:{port}")
        print("Auto-reload enabled – save any file in web/ to trigger a browser refresh.")
        print("Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
