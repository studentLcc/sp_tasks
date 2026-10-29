from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("sp-ha-bridge")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    sp_api_url: str = os.getenv("SP_API_URL", "http://127.0.0.1:3876")
    sp_api_token: str = os.getenv("SP_API_TOKEN", "")
    ha_url: str = os.getenv("HA_URL", "http://homeassistant.local:8123")
    ha_token: str = os.getenv("HA_TOKEN", "")
    ha_endpoint: str = os.getenv("HA_ENDPOINT", "/api/sp_tasks/tasks")
    listen_host: str = os.getenv("BRIDGE_HOST", "127.0.0.1")
    listen_port: int = int(os.getenv("BRIDGE_PORT", "8787"))
    sync_interval: int = int(os.getenv("SYNC_INTERVAL_SECONDS", "900"))
    include_done: bool = _env_bool("SP_INCLUDE_DONE", False)
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))


def _json_request(
    url: str,
    *,
    method: str = "GET",
    token: str = "",
    payload: dict[str, Any] | None = None,
    timeout: int = 15,
) -> Any:
    body = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else None


def normalize_task(task: dict[str, Any], task_date: str) -> dict[str, Any]:
    """Keep HA storage stable across SP API additions."""
    return {
        "id": str(task.get("id", "")),
        "title": str(task.get("title", "")).strip(),
        "notes": task.get("notes") or "",
        "is_done": bool(task.get("isDone", False)),
        "project_id": task.get("projectId"),
        "tag_ids": list(task.get("tagIds") or []),
        "due_day": task.get("dueDay"),
        "due_with_time": task.get("dueWithTime"),
        "deadline_day": task.get("deadlineDay"),
        "deadline_with_time": task.get("deadlineWithTime"),
        "time_estimate_ms": task.get("timeEstimate"),
        "time_spent_ms": task.get("timeSpent"),
        "parent_id": task.get("parentId"),
        "date": task_date,
    }


class Bridge:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self._lock = threading.Lock()
        self._last_sync: dict[str, Any] | None = None

    @property
    def last_sync(self) -> dict[str, Any] | None:
        with self._lock:
            return self._last_sync

    def _sp_url(self) -> str:
        query = urlencode({"tagId": "TODAY", "includeDone": str(self.settings.include_done).lower()})
        return f"{self.settings.sp_api_url.rstrip('/')}/tasks?{query}"

    def sync(self) -> dict[str, Any]:
        task_date = date.today().isoformat()
        response = _json_request(
            self._sp_url(), token=self.settings.sp_api_token, timeout=self.settings.request_timeout
        )
        if not isinstance(response, dict) or response.get("ok") is not True:
            raise RuntimeError(f"unexpected Super Productivity response: {response!r}")
        raw_tasks = response.get("data", [])
        if not isinstance(raw_tasks, list):
            raise RuntimeError("Super Productivity response data is not a list")
        tasks = [normalize_task(task, task_date) for task in raw_tasks if isinstance(task, dict)]
        payload = {
            "source": "super_productivity",
            "date": task_date,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "tasks": tasks,
        }
        endpoint = urljoin(self.settings.ha_url.rstrip("/") + "/", self.settings.ha_endpoint.lstrip("/"))
        result = _json_request(
            endpoint,
            method="POST",
            token=self.settings.ha_token,
            payload=payload,
            timeout=self.settings.request_timeout,
        )
        with self._lock:
            self._last_sync = {
                "date": task_date,
                "synced_at": payload["synced_at"],
                "task_count": len(tasks),
                "ha_response": result,
            }
        return self._last_sync


class _Handler(BaseHTTPRequestHandler):
    bridge: Bridge

    def _write(self, status: int, data: dict[str, Any]) -> None:
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._write(200, {"ok": True, "service": "sp-ha-bridge", "last_sync": self.bridge.last_sync})
            return
        self._write(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/sync":
            self._write(404, {"ok": False, "error": "not_found"})
            return
        try:
            result = self.bridge.sync()
            self._write(200, {"ok": True, "sync": result})
        except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as error:
            LOGGER.exception("sync failed")
            self._write(502, {"ok": False, "error": str(error)})

    def log_message(self, fmt: str, *args: Any) -> None:
        LOGGER.info("%s - %s", self.address_string(), fmt % args)


def run(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    bridge = Bridge(settings)
    handler = type("BridgeHandler", (_Handler,), {"bridge": bridge})
    server = ThreadingHTTPServer((settings.listen_host, settings.listen_port), handler)

    def periodic_sync() -> None:
        while True:
            try:
                bridge.sync()
                LOGGER.info("automatic sync completed: %s", bridge.last_sync)
            except Exception:  # noqa: BLE001
                LOGGER.exception("automatic sync failed")
            time.sleep(max(settings.sync_interval, 30))

    threading.Thread(target=periodic_sync, name="periodic-sync", daemon=True).start()
    LOGGER.info("listening on http://%s:%s", settings.listen_host, settings.listen_port)
    server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    run()

