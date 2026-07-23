"""Configuração comum para testes locais descartáveis.

O produto exige PostgreSQL nos ambientes oficiais. A suite atual ainda usa
SQLite isolado para testes unitários e de contrato, sem tocar dados reais.
"""

from __future__ import annotations

import os


os.environ.setdefault("CHECKLIST_ENV", "test")
os.environ.setdefault("CHECKLIST_ALLOW_SQLITE", "1")
os.environ.setdefault("CHECKLIST_LEGACY_LOCAL_BOOTSTRAP", "1")
