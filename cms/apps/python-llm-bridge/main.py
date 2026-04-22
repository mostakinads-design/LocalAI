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
            self.send_json_response({"status": "ok", "service": "python-llm-bridge"})
            return
        if self.path == "/models/options":
            self.send_json_response(
                {
                    "models": [
                        {"id": "qwen3", "provider": "localai"},
                        {"id": "llama3", "provider": "localai"},
                    ]
                }
            )
            return
        self.send_json_response({"error": "not found"}, status=404)

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len else b"{}"
        data = json.loads(body.decode("utf-8"))

        if self.path == "/tasks/update":
            self.send_json_response({"accepted": True, "task": data})
            return
        if self.path == "/prompts/create":
            self.send_json_response({"accepted": True, "prompt": data})
            return
        self.send_json_response({"error": "not found"}, status=404)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8010
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"python-llm-bridge listening on {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
