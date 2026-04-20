from __future__ import annotations

import sys
from pathlib import Path


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_root() -> Path:
    if _is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def asset_path(*parts: str) -> Path:
    return resource_root() / "assets" / Path(*parts)


def data_path(*parts: str) -> Path:
    return app_root() / "data" / Path(*parts)


def exports_path() -> Path:
    path = app_root() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path
