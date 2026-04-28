from __future__ import annotations

from flask import jsonify


def api_response(
    success: bool,
    *,
    data=None,
    error: str | None = None,
    status_code: int = 200,
):
    payload: dict = {"success": bool(success)}
    if data is not None:
        payload["data"] = data
    if error:
        payload["error"] = str(error)
    return jsonify(payload), int(status_code)
