"""Installation-local provider settings, separate from journal data and backups."""
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock
from chatgpt_provider import CoachError, _protect, _unprotect

_lock = threading.RLock()


def storage_dir():
    if os.name == "nt":
        return Path(os.environ["LOCALAPPDATA"]) / "TradingJournalAI" / "ai-providers"
    return Path.home() / ".config" / "TradingJournalAI" / "ai-providers"


def storage_description():
    return ("Windows DPAPI encryption for this Windows user, outside the journal and backups."
            if os.name == "nt" else
            "Local file restricted to this user (0600), not encrypted; outside the journal and backups.")


def _read():
    path = storage_dir() / "providers.bin"
    if not path.exists():
        return {"active_provider": "chatgpt", "providers": {}}
    try:
        if os.name != "nt":
            os.chmod(path, 0o600)
        value = json.loads(_unprotect(path.read_bytes()))
        if (not isinstance(value, dict) or not isinstance(value.get("providers"), dict) or
            not isinstance(value.get("active_provider", "chatgpt"), str) or
            any(not isinstance(config, dict) or
                not isinstance(config.get("api_key", ""), str) or
                not isinstance(config.get("model", ""), str) or
                not isinstance(config.get("capabilities", {}), dict)
                for config in value["providers"].values())):
            raise ValueError("invalid store")
        return value
    except Exception:
        raise CoachError("AI provider settings could not be opened on this computer.",
                         "credential_storage_error", 503) from None


def write(store):
    """Called while holding locked_store; replace atomically, never write plaintext on Windows."""
    temp_path = None
    try:
        blob = _protect(json.dumps(store).encode("utf-8"))
        fd, temp_path = tempfile.mkstemp(dir=storage_dir(), prefix="providers-", suffix=".tmp")
        with os.fdopen(fd, "wb") as handle:
            handle.write(blob)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, storage_dir() / "providers.bin")
    except Exception:
        raise CoachError("AI provider settings could not be saved securely.",
                         "credential_storage_error", 503) from None
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@contextmanager
def locked_store():
    try:
        folder = storage_dir()
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            os.chmod(folder, 0o700)
        with _lock, FileLock(str(folder / "providers.lock"), timeout=10):
            yield _read()
    except CoachError:
        raise
    except (OSError, TimeoutError):
        raise CoachError("AI provider settings are unavailable. Try again.",
                         "credential_storage_error", 503) from None
