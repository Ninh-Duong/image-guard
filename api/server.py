"""
api/server.py - Multi-threaded HTTP Server for Image Guard & User Profiling.
Uses Python Standard Library ThreadingHTTPServer with CORS, DoS Protection & AI Process Log APIs.
"""
from typing import Dict, Any
import io
import sys
import json
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

from core.config import INDEX_HTML_PATH, MAX_UPLOAD_SIZE
from core.process_logger import ProcessLogger
from core.i18n import get_supported_languages, DEFAULT_LANGUAGE, DEFAULT_TIMEZONE
from services.pipeline import ImageGuardService

# Global service instance initialized once in memory
service = ImageGuardService()


class ModerationHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests with full CORS support and size limit guardrails."""

    def _set_cors_headers(self):
        """Applies CORS headers for mobile and web clients."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, status_code: int, data: Dict[str, Any]):
        """Helper to send JSON response with standard headers."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """CORS Preflight request handler."""
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/index.html"):
            if INDEX_HTML_PATH.exists():
                content = INDEX_HTML_PATH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"index.html not found.")

        elif parsed.path == "/rules":
            self._send_json(200, service.default_rules)

        elif parsed.path == "/blocklist":
            self._send_json(200, {
                "total": len(service.blocklist.str_hashes),
                "hashes": list(service.blocklist.str_hashes),
            })

        # Source Supported Languages Metadata Endpoint
        elif parsed.path in ("/languages", "/locales"):
            self._send_json(200, {
                "supported_languages": get_supported_languages(),
                "default_language": DEFAULT_LANGUAGE,
                "default_timezone": DEFAULT_TIMEZONE,
            })

        # AI Agent Telemetry & Process Logs Endpoints
        elif parsed.path == "/logs/latest":
            latest = ProcessLogger.get_latest_run()
            if latest:
                self._send_json(200, latest)
            else:
                self._send_json(200, {"status": "No process runs recorded yet."})

        elif parsed.path == "/logs/summary":
            self._send_json(200, ProcessLogger.get_summary())

        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        parsed = urlparse(self.path)

        # 1. Enforce payload size limit (DoS guardrail)
        try:
            content_len = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._send_json(400, {"error": "Invalid Content-Length header"})
            return

        if content_len > MAX_UPLOAD_SIZE:
            self._send_json(413, {
                "error": f"Payload too large. Maximum allowed size is {MAX_UPLOAD_SIZE // (1024 * 1024)}MB."
            })
            return

        body = self.rfile.read(content_len) if content_len > 0 else b""

        # 2. Endpoint: /check (Image Guard & Profile Analysis)
        if parsed.path == "/check":
            params = parse_qs(parsed.query)
            rules = dict(service.default_rules)

            # Safely parse query parameter overrides
            try:
                if "max_nsfw" in params:
                    rules["max_nsfw"] = float(params["max_nsfw"][0])
                if "min_safe" in params:
                    rules["min_safe"] = float(params["min_safe"][0])
            except ValueError:
                self._send_json(400, {"error": "Invalid threshold parameter. Must be float between 0.0 and 1.0."})
                return

            skip_profiling = params.get("skip_profile", ["false"])[0].lower() in ("true", "1", "yes")

            # Extract Language and Timezone (from query param or headers)
            lang = params.get("lang", [None])[0] or params.get("language", [None])[0]
            timezone_param = (
                params.get("timezone", [None])[0]
                or params.get("tz", [None])[0]
                or self.headers.get("X-Timezone")
                or self.headers.get("X-User-Timezone")
            )

            client_info = {
                "client_ip": self.client_address[0] if hasattr(self, "client_address") else "unknown",
                "endpoint": "/check",
                "query": parsed.query,
                "user_agent": self.headers.get("User-Agent", "unknown"),
                "accept_language": self.headers.get("Accept-Language"),
                "raw_timezone": timezone_param,
                "raw_language": lang,
            }

            # Process through the unified pipeline with AI agent telemetry & i18n
            response = service.process_image(
                body,
                rules=rules,
                skip_profiling=skip_profiling,
                client_info=client_info,
                lang=lang,
                timezone_str=timezone_param,
            )
            res_dict = response.to_dict()

            # Return 400 if client supplied non-image payload
            if res_dict.get("reason") == "INVALID_IMAGE_PAYLOAD":
                self._send_json(400, res_dict)
            else:
                self._send_json(200, res_dict)

        # 3. Endpoint: /blocklist (Manual ban)
        elif parsed.path == "/blocklist":
            try:
                data = json.loads(body.decode("utf-8"))
                target_hash = data.get("hash")
                reason = data.get("reason", "MANUAL_BLOCK")
                scores = data.get("scores", {})

                if not target_hash or not isinstance(target_hash, str):
                    self._send_json(400, {"error": "Missing or invalid 'hash' field."})
                    return

                added = service.blocklist.add(target_hash, reason=reason, scores=scores)
                self._send_json(200, {
                    "success": True,
                    "added": added,
                    "total_blocked": len(service.blocklist.str_hashes),
                })
            except Exception as err:
                self._send_json(400, {"error": f"Failed to parse request body: {err}"})

        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def log_message(self, format, *args):
        """Concise log output."""
        sys.stdout.write(f"[{self.log_date_time_string()}] {args[0]} {args[1]} {args[2]}\n")


def run_server(port: int = 8000):
    """Starts the multi-threaded HTTP server."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, ModerationHandler)
    print("\n========================================================")
    print(f"  [Image Guard] Threaded Server running at: http://localhost:{port}")
    print("  Endpoints:")
    print("    - POST /check           (Image Guard & User Profiling)")
    print("    - GET  /rules           (Active moderation thresholds)")
    print("    - POST /blocklist       (Add banned image hash)")
    print("    - GET  /logs/latest     (AI Agent: Latest execution trace)")
    print("    - GET  /logs/summary    (AI Agent: Rolling metrics summary)")
    print("  Press Ctrl+C to stop.")
    print("========================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Info] Server stopped gracefully.")
        httpd.server_close()
