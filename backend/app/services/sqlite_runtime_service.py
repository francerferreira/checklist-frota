from __future__ import annotations

from sqlalchemy import event, text

from app.extensions import db


_CONFIGURED_ENGINES: set[int] = set()


def configure_sqlite_runtime(app) -> None:
    """Aplica protecoes de concorrencia a cada conexao SQLite local."""
    engine = db.engine
    if engine.dialect.name != "sqlite" or id(engine) in _CONFIGURED_ENGINES:
        return

    busy_timeout_ms = int(app.config["SQLITE_BUSY_TIMEOUT_MS"])
    journal_mode = str(app.config["SQLITE_JOURNAL_MODE"])

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
            cursor.execute(f"PRAGMA journal_mode = {journal_mode}")
            cursor.execute("PRAGMA synchronous = FULL")
        finally:
            cursor.close()

    _CONFIGURED_ENGINES.add(id(engine))


def sqlite_runtime_status() -> dict:
    """Retorna apenas indicadores operacionais; nunca expõe o caminho do banco."""
    if db.engine.dialect.name != "sqlite":
        return {"enabled": False}

    with db.engine.connect() as connection:
        journal_mode = str(connection.execute(text("PRAGMA journal_mode")).scalar_one()).upper()
        busy_timeout_ms = int(connection.execute(text("PRAGMA busy_timeout")).scalar_one())
        foreign_keys = bool(connection.execute(text("PRAGMA foreign_keys")).scalar_one())

    return {
        "enabled": True,
        "journal_mode": journal_mode,
        "busy_timeout_ms": busy_timeout_ms,
        "foreign_keys": foreign_keys,
    }
