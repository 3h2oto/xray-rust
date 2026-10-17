#!/usr/bin/env python3
"""Controlled delayed HTTP responses for the opt-in issue #69 Apple device check."""

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18669)
    parser.add_argument("--delay-seconds", type=float, default=5)
    args = parser.parse_args()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            print(json.dumps({"event": "request", "path": path, "time": time.time()}), flush=True)
            if path in ("/success", "/failure"):
                time.sleep(args.delay_seconds)
            elif path in ("/timeout", "/cancel"):
                time.sleep(20)
            status = 503 if path == "/failure" else 204
            try:
                self.send_response(status)
                self.send_header("Content-Length", "0")
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError):
                pass
            print(json.dumps({"event": "response", "path": path, "status": status, "time": time.time()}), flush=True)

    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
