import json
import os
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

_config_lock = threading.Lock()
_config = {}

_tasks_lock = threading.Lock()
_tasks = {}


def load_config():
    global _config
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        with _config_lock:
            _config = data
        print(f"[config] loaded from {CONFIG_PATH}")
    except FileNotFoundError:
        print(f"[config] {CONFIG_PATH} not found, using empty config")
    except json.JSONDecodeError as e:
        print(f"[config] failed to parse {CONFIG_PATH}: {e}")


def get_config():
    with _config_lock:
        return dict(_config)


class Handler(BaseHTTPRequestHandler):
    def send_json_response(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # Health
        if self.path == "/health":
            self.send_json_response({"status": "ok", "service": "python-llm-bridge"})
            return

        # List available AI model options
        if self.path == "/models/options":
            cfg = get_config()
            self.send_json_response({"models": cfg.get("models", [])})
            return

        # List all tracked task processes
        if self.path == "/tasks":
            with _tasks_lock:
                self.send_json_response({"tasks": list(_tasks.values())})
            return

        # Get individual task by id: /tasks/<id>
        if self.path.startswith("/tasks/"):
            task_id = self.path[len("/tasks/"):]
            with _tasks_lock:
                task = _tasks.get(task_id)
            if task is None:
                self.send_json_response({"error": "task not found"}, status=404)
            else:
                self.send_json_response(task)
            return

        # View current dynamic config
        if self.path == "/config":
            self.send_json_response(get_config())
            return

        self.send_json_response({"error": "not found"}, status=404)

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len else b"{}"
        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_json_response({"error": "invalid json body"}, status=400)
            return

        # Update or create a task with status tracking
        if self.path == "/tasks/update":
            task_id = data.get("task_id") or str(uuid.uuid4())
            with _tasks_lock:
                if task_id in _tasks:
                    _tasks[task_id].update(data)
                    _tasks[task_id]["task_id"] = task_id
                else:
                    _tasks[task_id] = {"task_id": task_id, "status": "pending", **data}
                task = dict(_tasks[task_id])
            print(f"[task] {task_id} -> {task.get('status')}")
            self.send_json_response({"accepted": True, "task": task})
            return

        # Create a new named prompt
        if self.path == "/prompts/create":
            self.send_json_response({"accepted": True, "prompt": data})
            return

        # Reload config from disk without restarting
        if self.path == "/config/reload":
            load_config()
            self.send_json_response({"reloaded": True, "config": get_config()})
            return

        self.send_json_response({"error": "not found"}, status=404)

    def log_message(self, fmt, *args):
        pass  # suppress per-request access log noise


if __name__ == "__main__":
    load_config()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8010
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"python-llm-bridge listening on {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
