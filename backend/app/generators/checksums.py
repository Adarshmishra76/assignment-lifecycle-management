import hashlib
import json
from pathlib import Path
from typing import Any

LOGICAL_EXCLUDE = {
    "created_at",
    "updated_at",
    "uploaded_at",
    "password_hash",
    "enrolled_at",
    "requested_at",
    "decided_at",
}


def canonical_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _stringify(v) for k, v in sorted(row.items()) if k not in LOGICAL_EXCLUDE}


def _stringify(value: Any) -> Any:
    if value is None:
        return None
    return str(value)


def logical_checksum(rows: list[dict[str, Any]]) -> str:
    payload = [canonical_row(row) for row in rows]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
