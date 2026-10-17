"""Per-session log of instrumented calls, the evidence contracts read after a run.

Fault events say what was injected; the call log says what the application did
around them: which steps it called, in what order, how long each call took and
whether it raised. Retry, traversal and timing contracts need that, and the
events alone cannot show it.
"""

import time
from datetime import datetime, timezone
from threading import RLock
from typing import Any

DEFAULT_MAX_CALL_RECORDS = 10_000


class CallLog:
    """Bounded, locked list of call records shared by a session and its workers.

    Records past ``max_records`` are counted in ``dropped`` instead of stored,
    so a long run cannot grow the log without limit. Contracts that need the
    complete log report themselves inconclusive when anything was dropped.
    """

    def __init__(self, max_records: int = DEFAULT_MAX_CALL_RECORDS) -> None:
        if isinstance(max_records, bool) or not isinstance(max_records, int) or max_records < 0:
            raise ValueError("max_records must be a non-negative integer")
        self.max_records = max_records
        self.records: list[dict[str, Any]] = []
        self.dropped = 0
        self._lock = RLock()
        self._sequence = 0

    def begin(self, *, kind: str, step_id: str | None, step_name: str | None) -> dict[str, Any]:
        """Start a record; the caller passes it back to `finish()`."""
        with self._lock:
            self._sequence += 1
            record: dict[str, Any] = {
                "sequence": self._sequence,
                "kind": kind,
                "step_id": step_id,
                "step_name": step_name,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "duration_s": None,
                "status": "running",
                "error_type": None,
                "fault_type": None,
                "event_id": None,
                "_started": time.monotonic(),
            }
            return record

    def finish(self, record: dict[str, Any], error: BaseException | None = None) -> None:
        """Close a record with its outcome and append it (or count it as dropped)."""
        started = record.pop("_started", None)
        if started is not None:
            record["duration_s"] = time.monotonic() - started
        if error is None:
            record["status"] = "ok"
        else:
            record["status"] = "error"
            record["error_type"] = type(error).__name__
        with self._lock:
            if len(self.records) < self.max_records:
                self.records.append(record)
            else:
                self.dropped += 1

    def as_json(self) -> list[dict[str, Any]]:
        """Completed records in start order, ready to embed in a `ChaosReport`."""
        with self._lock:
            return sorted((dict(record) for record in self.records), key=_sequence)


def _sequence(record: dict[str, Any]) -> int:
    value = record.get("sequence", 0)
    return value if isinstance(value, int) else 0
