"""Structured trace events for one customer session.

Every event is appended in order to an in-memory list and to traces/<trace_id>.jsonl.
The Agent Inspector (web/inspector.html) renders these real events; nothing is hardcoded.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRACE_DIR = Path(__file__).parent / "traces"

_SECRET_KEYS = re.compile(r"(api[_-]?key|token|secret|password|card|cvv|auth|signature)", re.I)


def redact(value: Any) -> Any:
    """Drop values whose key looks like a secret. Applied to every event's attrs."""
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if _SECRET_KEYS.search(str(k)) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


class Tracer:
    def __init__(self, trace_id: str | None = None, persist: bool = True):
        self.trace_id = trace_id or f"tr_{uuid.uuid4().hex[:12]}"
        self.events: list[dict] = []
        self.persist = persist
        self._path = TRACE_DIR / f"{self.trace_id}.jsonl"
        if persist:
            TRACE_DIR.mkdir(exist_ok=True)

    def event(self, kind: str, name: str, status: str = "ok", duration_ms: float | None = None, **attrs) -> dict:
        ev = {
            "trace_id": self.trace_id,
            "seq": len(self.events) + 1,
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "kind": kind,
            "name": name,
            "status": status,
            "duration_ms": None if duration_ms is None else round(duration_ms, 2),
            "attrs": redact(attrs),
        }
        self.events.append(ev)
        if self.persist:
            try:
                with self._path.open("a") as f:
                    f.write(json.dumps(ev, default=str) + "\n")
            except OSError:
                # Logging failure must not change commerce behaviour; event stays in memory.
                pass
        return ev

    @contextmanager
    def tool(self, name: str, **args):
        """Time a tool call and record name, args, status, duration and a result summary."""
        start = time.perf_counter()
        holder: dict[str, Any] = {}
        try:
            yield holder
        except Exception as exc:
            self.event("tool", name, status="error", duration_ms=(time.perf_counter() - start) * 1000,
                       args=args, error=f"{type(exc).__name__}: {exc}")
            raise
        self.event("tool", name, duration_ms=(time.perf_counter() - start) * 1000,
                   args=args, result=holder.get("summary"))

    def find(self, kind: str | None = None, name: str | None = None) -> list[dict]:
        return [e for e in self.events if (kind is None or e["kind"] == kind) and (name is None or e["name"] == name)]
