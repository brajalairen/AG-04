"""A small JSON disk cache for the agricultural data layer (under runs/, which is gitignored).

Every entry records when it was fetched, so anything served from it is labelled CACHED with its
real age and is never passed off as live. Callers decide freshness: a stale entry may still answer
when a live fetch fails, and then the answer says it is stale instead of inventing values.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CacheEntry:
    value: Any
    retrieved_at: str  # ISO UTC
    age_s: float


def cache_key(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:24]


class JsonCache:
    def __init__(self, directory: Path, clock=time.time):
        self.directory = Path(directory)
        self._clock = clock

    def _path(self, namespace: str, key: str) -> Path:
        return self.directory / namespace / f"{key}.json"

    def get(self, namespace: str, key: str) -> CacheEntry | None:
        path = self._path(namespace, key)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return CacheEntry(value=record["value"], retrieved_at=record["retrieved_at"],
                          age_s=max(0.0, self._clock() - float(record["fetched_epoch"])))

    def put(self, namespace: str, key: str, value: Any) -> CacheEntry:
        now = self._clock()
        retrieved_at = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")
        path = self._path(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".partial")
        partial.write_text(json.dumps({"fetched_epoch": now, "retrieved_at": retrieved_at, "value": value}),
                           encoding="utf-8")
        partial.replace(path)  # never leave a half-written entry behind
        return CacheEntry(value=value, retrieved_at=retrieved_at, age_s=0.0)
