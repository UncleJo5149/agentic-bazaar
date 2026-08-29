from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

EMPTY = {
    "agents": {},
    "mandates": {},
    "skills": {},
    "quotes": {},
    "intents": {},
    "receipts": {},
    "jobs": {},
    "balances": {},
    "approvals": {},
    "demands": {},
    "invoices": {},
    "payouts": {},
}


class JsonStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists() or self.path.stat().st_size == 0:
            self._write(EMPTY)

    def _read(self) -> dict[str, Any]:
        raw = self.path.read_text().strip()
        return json.loads(raw) if raw else dict(EMPTY)

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.path)

    def get(self, table: str, key: str) -> Any | None:
        with self.lock:
            return self._read().get(table, {}).get(key)

    def all(self, table: str) -> dict[str, Any]:
        with self.lock:
            return self._read().get(table, {})

    def put(self, table: str, key: str, value: Any) -> None:
        with self.lock:
            data = self._read()
            data.setdefault(table, {})[key] = value
            self._write(data)

    def update(self, table: str, key: str, mutator) -> Any:
        with self.lock:
            data = self._read()
            current = data.setdefault(table, {}).get(key)
            updated = mutator(current)
            data[table][key] = updated
            self._write(data)
            return updated
