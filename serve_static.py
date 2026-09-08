#!/usr/bin/env python3
"""Serve web/ as a plain static site — the browser-only mode, with no backend.

Same as `python3 -m http.server --directory web`, minus the caching: the whole
application is a single HTML file, and a cached copy has already made fixed bugs
look unfixed more than once.
"""
import sys
from http.server import SimpleHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
WEB_DIR = Path(__file__).resolve().parent / "web"


class NoCacheHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    print(f"SlidePunch (navigateur seul) : http://localhost:{PORT}")
    print(f"Dossier servi : {WEB_DIR}")
    try:
        ThreadingHTTPServer(("", PORT), NoCacheHandler).serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
