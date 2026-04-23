"""
laravel-ai-cms-bridge

An OpenAI-compatible HTTP proxy that sits between the sanchit237/laravel-ai-cms
Laravel application and LocalAI.  Every chat-completion request is:

  1. Recorded as a tracked task (visible via GET /tasks and GET /tasks/<id>)
  2. Forwarded to the LocalAI API
  3. The response (slug, summary, etc.) is stored on the task record

This gives full task-process visibility for every AI generation triggered by
the CMS queue worker (GenerateSlugSummary jobs etc.).

Endpoints
---------
  POST /v1/chat/completions        OpenAI-compatible proxy to LocalAI
  GET  /health                     Health check
  GET  /tasks                      List all tracked tasks
  GET  /tasks/<id>                 Single task detail
  POST /tasks/update               Create / advance a task manually
  GET  /config                     View current config
  POST /config/reload              Hot-reload config.json from disk
"""
import http.client
import json
import os
import sys
import threading
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

_config_lock = threading.Lock()
_config: dict = {}

_tasks_lock = threading.Lock()
_tasks: dict = {}


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config():
    global _config
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        with _config_lock:
            _config = data
        print(f"[config] loaded from {CONFIG_PATH}")
    except FileNotFoundError:
        print(f"[config] {CONFIG_PATH} not found, using defaults")
    except json.JSONDecodeError as e:
        print(f"[config] parse error: {e}")


def get_config() -> dict:
    with _config_lock:
        return dict(_config)


# ---------------------------------------------------------------------------
# Task registry helpers
# ---------------------------------------------------------------------------

def upsert_task(task_id: str, updates: dict) -> dict:
    with _tasks_lock:
        if task_id in _tasks:
            _tasks[task_id].update(updates)
            _tasks[task_id]["task_id"] = task_id
        else:
            _tasks[task_id] = {"task_id": task_id, "status": "pending", **updates}
        return dict(_tasks[task_id])


def get_task(task_id: str):
    with _tasks_lock:
        return _tasks.get(task_id)


def list_tasks() -> list:
    with _tasks_lock:
        return list(_tasks.values())


# ---------------------------------------------------------------------------
# LocalAI proxy helper
# ---------------------------------------------------------------------------

def proxy_to_localai(path: str, body_bytes: bytes, request_headers) -> tuple:
    """Forward a request to LocalAI and return (status, headers, body_bytes)."""
    cfg = get_config()
    localai_url = cfg.get("localai_base_url", "http://api:8080/v1")
    parsed = urllib.parse.urlparse(localai_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    base_path = parsed.path.rstrip("/")

    conn = http.client.HTTPConnection(host, port, timeout=120)
    forward_path = base_path + path[len("/v1"):]  # e.g. /v1/chat/completions -> /v1/chat/completions

    headers = {
        "Content-Type": request_headers.get("Content-Type", "application/json"),
        "Content-Length": str(len(body_bytes)),
        "Authorization": request_headers.get("Authorization", "Bearer localai"),
    }

    conn.request("POST", forward_path, body=body_bytes, headers=headers)
    resp = conn.getresponse()
    resp_body = resp.read()
    resp_headers = dict(resp.getheaders())
    conn.close()
    return resp.status, resp_headers, resp_body


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):

    def send_json_response(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b"{}"

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------

    def do_GET(self):
        if self.path == "/health":
            self.send_json_response({"status": "ok", "service": "laravel-ai-cms-bridge"})
            return

        if self.path == "/tasks":
            self.send_json_response({"tasks": list_tasks()})
            return

        if self.path.startswith("/tasks/"):
            task_id = self.path[len("/tasks/"):]
            task = get_task(task_id)
            if task is None:
                self.send_json_response({"error": "task not found"}, status=404)
            else:
                self.send_json_response(task)
            return

        if self.path == "/config":
            self.send_json_response(get_config())
            return

        self.send_json_response({"error": "not found"}, status=404)

    # ------------------------------------------------------------------
    # POST
    # ------------------------------------------------------------------

    def do_POST(self):
        body = self.read_body()

        # ---- OpenAI-compatible chat completions proxy ------------------
        if self.path == "/v1/chat/completions":
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_json_response({"error": "invalid json"}, status=400)
                return

            # Derive a human-readable description from the last user message
            messages = payload.get("messages", [])
            last_user_msg = next(
                (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
                "",
            )
            model = payload.get("model", get_config().get("default_model", "gpt-3.5-turbo"))

            task_id = str(uuid.uuid4())
            task = upsert_task(task_id, {
                "status": "running",
                "type": "chat-completion",
                "model": model,
                "prompt_preview": last_user_msg[:200],
                "source": "laravel-ai-cms",
            })
            print(f"[task] {task_id} running | model={model}")

            # Override model with whatever LocalAI has configured
            cfg = get_config()
            if cfg.get("override_model"):
                payload["model"] = cfg["override_model"]
                body = json.dumps(payload).encode("utf-8")

            try:
                status, resp_headers, resp_body = proxy_to_localai(
                    "/v1/chat/completions", body, self.headers
                )
            except Exception as exc:
                upsert_task(task_id, {"status": "error", "error": str(exc)})
                print(f"[task] {task_id} error: {exc}")
                self.send_json_response({"error": str(exc)}, status=502)
                return

            # Parse result for task record
            result_text = ""
            try:
                parsed_resp = json.loads(resp_body)
                choices = parsed_resp.get("choices", [])
                if choices:
                    result_text = choices[0].get("message", {}).get("content", "")
            except Exception:
                pass

            upsert_task(task_id, {
                "status": "done" if status < 400 else "error",
                "result_preview": result_text[:300],
                "localai_status": status,
            })
            print(f"[task] {task_id} {'done' if status < 400 else 'error'} | http={status}")

            # Return the raw LocalAI response to the caller
            self.send_response(status)
            for hdr_name, hdr_val in resp_headers.items():
                if hdr_name.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(hdr_name, hdr_val)
            self.send_header("Content-Length", str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)
            return

        # ---- Manual task upsert ----------------------------------------
        if self.path == "/tasks/update":
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self.send_json_response({"error": "invalid json"}, status=400)
                return
            task_id = data.get("task_id") or str(uuid.uuid4())
            task = upsert_task(task_id, data)
            print(f"[task] {task_id} -> {task.get('status')}")
            self.send_json_response({"accepted": True, "task": task})
            return

        # ---- Dynamic config reload --------------------------------------
        if self.path == "/config/reload":
            load_config()
            self.send_json_response({"reloaded": True, "config": get_config()})
            return

        self.send_json_response({"error": "not found"}, status=404)

    def log_message(self, fmt, *args):
        pass  # suppress noisy per-request access logs


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    load_config()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8012
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"laravel-ai-cms-bridge listening on {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
