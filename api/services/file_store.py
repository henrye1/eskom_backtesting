"""Temporary file storage for uploaded workbooks."""

import hashlib
import shutil
import tempfile
import time
from pathlib import Path

_STORE: dict[str, dict] = {}
_UPLOAD_DIR = Path(tempfile.gettempdir()) / "lgd_uploads"
_TTL_SECONDS = 3600  # 1 hour


def _ensure_dir() -> None:
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_file(filename: str, data: bytes) -> str:
    _ensure_dir()
    file_id = hashlib.md5(data).hexdigest()
    dest = _UPLOAD_DIR / f"{file_id}.xlsx"
    dest.write_bytes(data)
    _STORE[file_id] = {
        "filename": filename,
        "path": str(dest),
        "size": len(data),
        "created": time.time(),
    }
    return file_id


def get_file_path(file_id: str) -> str | None:
    info = _STORE.get(file_id)
    if info is None:
        return None
    path = Path(info["path"])
    if not path.exists():
        del _STORE[file_id]
        return None
    return str(path)


def get_file_info(file_id: str) -> dict | None:
    return _STORE.get(file_id)


def delete_file(file_id: str) -> bool:
    info = _STORE.pop(file_id, None)
    if info is None:
        return False
    path = Path(info["path"])
    if path.exists():
        path.unlink()
    return True


def cleanup_expired() -> int:
    now = time.time()
    expired = [
        fid for fid, info in _STORE.items()
        if now - info["created"] > _TTL_SECONDS
    ]
    for fid in expired:
        delete_file(fid)
    return len(expired)
