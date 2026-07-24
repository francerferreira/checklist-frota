"""Configuração comum para testes locais descartáveis.

O produto exige PostgreSQL nos ambientes oficiais. A suite atual ainda usa
SQLite isolado para testes unitários e de contrato, sem tocar dados reais.
"""

from __future__ import annotations

import os


os.environ.pop("CHECKLIST_FORCE_LOCAL_DB", None)
os.environ["CHECKLIST_ENV"] = "test"
os.environ["CHECKLIST_ALLOW_SQLITE"] = "1"
os.environ["CHECKLIST_LEGACY_LOCAL_BOOTSTRAP"] = "1"
