from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse


backend_root = Path(__file__).resolve().parents[1] / "backend"
if backend_root.exists():
    backend_root_str = str(backend_root)
    if backend_root_str not in sys.path:
        sys.path.insert(0, backend_root_str)


_backend_thread: threading.Thread | None = None


def _is_local_address(base_url: str) -> tuple[bool, str, int]:
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    is_local = host in {"127.0.0.1", "localhost"}
    return is_local, host, port


def _run_backend(host: str, port: int) -> None:
    os.environ["CHECKLIST_EMBEDDED_BACKEND"] = "1"
    from app import create_app

    app = create_app()
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


def ensure_local_backend(api_client, wait_seconds: float = 8.0) -> bool:
    global _backend_thread

    is_local, host, port = _is_local_address(api_client.base_url)
    if not is_local:
        return False
    if api_client.ping():
        return True

    if _backend_thread is None or not _backend_thread.is_alive():
        _backend_thread = threading.Thread(
            target=_run_backend,
            args=(host, port),
            name="ChecklistEmbeddedBackend",
            daemon=True,
        )
        _backend_thread.start()

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if api_client.ping():
            return True
        time.sleep(0.25)
    return False
