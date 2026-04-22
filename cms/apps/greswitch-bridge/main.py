import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def send_json_response(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.send_json_response({"status": "ok", "service": "greswitch-bridge"})
            return
        if self.path == "/capabilities":
            self.send_json_response(
                {
                    "supports": [
                        "task-updates",
                        "prompt-creation",
                        "model-options",
                    ]
                }
            )
            return
        self.send_json_response({"error": "not found"}, status=404)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8011
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"greswitch-bridge listening on {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
