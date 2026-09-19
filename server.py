"""
server.py - Lightweight HTTP server for Image Guard (100% Python Standard Library).
Serves the web dashboard and exposes the /check API without any third-party web frameworks.
"""
import io
import os
import sys
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from bootstrap import ensure_environment

# Self-bootstrap environment before loading engine
ensure_environment()

from moderator import LocalModerationEngine

# Initialize the moderation engine once in RAM
engine = LocalModerationEngine()
INDEX_FILE = Path(__file__).parent / "index.html"


class ModerationHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for image moderation and configuration."""

    def do_OPTIONS(self):
        """Handles CORS preflight requests from external frontends (e.g. React/Vue)."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/index.html"):
            if INDEX_FILE.exists():
                content = INDEX_FILE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"index.html not found.")

        elif parsed.path == "/rules":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(engine.default_rules).encode("utf-8"))

        elif parsed.path == "/blocklist":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(list(engine.blocklist_hashes)).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b""

        if parsed.path == "/check":
            # Extract override rules from query parameters, falling back to system rules
            params = parse_qs(parsed.query)
            rules = dict(engine.default_rules)
            if "max_nsfw" in params:
                rules["max_nsfw"] = float(params["max_nsfw"][0])
            if "max_violence" in params:
                rules["max_violence"] = float(params["max_violence"][0])
            if "min_safe" in params:
                rules["min_safe"] = float(params["min_safe"][0])

            # In-memory execution: zero-disk writes
            result = engine.check(io.BytesIO(body), rules=rules)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))

        elif parsed.path == "/blocklist":
            # Manually ban a hash and persist to blocklist.jsonl
            try:
                data = json.loads(body.decode("utf-8"))
                target_hash = data.get("hash")
                reason = data.get("reason", "MANUAL_BLOCK")
                scores = data.get("scores", {})
                if target_hash:
                    engine.add_to_blocklist(target_hash, reason=reason, scores=scores)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "total_blocked": len(engine.blocklist_hashes)
                }).encode("utf-8"))
            except Exception as err:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(err)}).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Concise single-line HTTP log
        sys.stdout.write(f"[{self.log_date_time_string()}] {args[0]} {args[1]} {args[2]}\n")


def run_server(port: int = 8000):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    server_address = ("", port)
    httpd = HTTPServer(server_address, ModerationHandler)
    print("\n========================================================")
    print(f"  [Image Guard] Server running at: http://localhost:{port}")
    print("  Open browser to evaluate images.")
    print("  Press Ctrl+C to stop.")
    print("========================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Info] Server stopped gracefully.")
        httpd.server_close()


if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port)
