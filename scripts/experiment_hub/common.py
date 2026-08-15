"""Shared filesystem, hashing, serialization, and naming helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


UNKNOWN = "Unknown"
NOT_PROVIDED = "Not Provided"
NA = "NA"


def now_iso() -> str:
    """Return a timezone-aware local timestamp in ISO 8601 form."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    return date.today().isoformat()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Calculate a file SHA-256 without loading the whole file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(value: Any, fallback: str = "未分类实验", max_length: int = 80) -> str:
    """Create a Windows-safe readable filename component."""
    text = str(value or "").strip()
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text).strip(" ._")
    if not text:
        text = fallback
    return text[:max_length].rstrip(" ._") or fallback


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_iso_date(value: Any) -> Optional[str]:
    """Parse common date values; return YYYY-MM-DD or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    patterns = [
        r"(?<!\d)(20\d{2})[-_/\.](\d{1,2})[-_/\.](\d{1,2})(?!\d)",
        r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)",
        r"(?<!\d)(20\d{2})年(\d{1,2})月(\d{1,2})日",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
        except ValueError:
            continue
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    """Write UTF-8 JSON atomically, without a BOM."""
    ensure_directory(path.parent)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", delete=False,
        dir=str(path.parent), suffix=".tmp",
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=json_default)
            handle.write("\n")
        os.replace(str(temp_path), str(path))
    finally:
        if temp_path.exists():
            temp_path.unlink()


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    """Append one UTF-8 JSON record to an audit ledger."""
    ensure_directory(path.parent)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=json_default))
        handle.write("\n")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid JSONL at line {}: {}".format(line_number, exc))
            if isinstance(value, dict):
                records.append(value)
    return records


def normalize_scalar(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"", "na", "n/a", "nan", "none", "null", "未提供"}
    return False


def unique_text(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        if is_missing(value):
            continue
        text = str(value).strip()
        key = text.casefold()
        if key not in seen:
            seen.add(key)
            result.append(text)
    return result
