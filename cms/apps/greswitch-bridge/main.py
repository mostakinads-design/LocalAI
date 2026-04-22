import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def _send(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send({"status": "ok", "service": "greswitch-bridge"})
            return
        if self.path == "/capabilities":
            self._send(
                {
                    "supports": [
                        "task-updates",
                        "prompt-creation",
                        "model-options",
                    ]
                }
            )
            return
        self._send({"error": "not found"}, status=404)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8011
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()
