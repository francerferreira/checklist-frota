from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ROOT = PROJECT_ROOT / "desktop"
if str(DESKTOP_ROOT) not in sys.path:
    sys.path.insert(0, str(DESKTOP_ROOT))

from services.message_service import (
    build_activity_message_package,
    build_item_message_package,
    build_macro_message_package,
    build_material_message_package,
    build_micro_message_package,
)


class MessageServiceTests(unittest.TestCase):
    def test_macro_message_contains_subject_and_whatsapp_formatting(self):
        package = build_macro_message_package(
            [
                {"item_nome": "Farol alto", "total_nc": 4, "abertas": 3, "resolvidas": 1},
                {"item_nome": "Pneu", "total_nc": 2, "abertas": 1, "resolvidas": 1},
            ],
            "01/04/2026 a 12/04/2026",
            generated_by="Administrador",
        )
        self.assertIn("Não conformidades por item", package.email_subject)
        self.assertIn("**RELATÓRIO EXECUTIVO", package.whatsapp_text)
        self.assertIn("Top 5 itens", package.whatsapp_text)
        self.assertTrue(package.summary_items)

    def test_micro_message_contains_vehicle_summary(self):
        package = build_micro_message_package(
            [
                {"frota": "CV801", "total_nc": 3},
                {"frota": "CV800", "total_nc": 1},
            ],
            "01/04/2026 a 12/04/2026",
        )
        self.assertIn("equipamento", package.email_subject.lower())
        self.assertIn("Top 5 equipamentos", package.whatsapp_text)
        self.assertIn("CV801", package.email_body)

    def test_item_message_contains_item_name(self):
        package = build_item_message_package(
            [
                {"veiculo": {"frota": "CV801"}, "resolvido": False, "created_at": "2026-04-11T12:00:00"},
                {"veiculo": {"frota": "CV802"}, "resolvido": True, "created_at": "2026-04-12T12:00:00"},
            ],
            "Farol baixo",
            "11/04/2026 a 12/04/2026",
        )
        self.assertIn("Farol baixo", package.email_subject)
        self.assertIn("Top 5 veículos impactados", package.whatsapp_text)

    def test_material_message_contains_stock_summary(self):
        package = build_material_message_package(
            {
                "periodo": {"data_inicial": "2026-04-01", "data_final": "2026-04-12"},
                "resumo": {
                    "total_materiais": 12,
                    "abaixo_minimo": 2,
                    "saldo_total": 145,
                    "consumo_total_periodo": 23,
                },
                "baixo_estoque": [{"descricao": "Lanterna", "deficit": 3}],
                "ranking_uso": [{"descricao": "Lanterna", "consumo_total": 9}],
                "consumo_periodo": [{"descricao": "Lanterna", "consumo_total": 9}],
            },
            "01/04/2026 a 12/04/2026",
        )
        self.assertIn("estoque", package.email_subject.lower())
        self.assertIn("Materiais abaixo do mínimo", package.whatsapp_text)
        self.assertIn("Lanterna", package.email_body)

    def test_activity_message_contains_activity_summary(self):
        package = build_activity_message_package(
            {
                "titulo": "Troca em massa - Lanterna",
                "item_nome": "Lanterna",
                "created_at": "2026-04-11T12:00:00",
                "finalized_at": None,
                "resumo": {"total": 2, "instalados": 1, "nao_instalados": 1, "pendentes": 0},
                "itens": [
                    {
                        "status_execucao": "INSTALADO",
                        "veiculo": {"frota": "CV801"},
                    },
                    {
                        "status_execucao": "NAO_INSTALADO",
                        "veiculo": {"frota": "CV802"},
                    },
                ],
            }
        )
        self.assertIn("atividade em massa", package.title.lower())
        self.assertIn("CV802", package.email_body)
        self.assertIn("**RELATÓRIO EXECUTIVO", package.whatsapp_text)


if __name__ == "__main__":
    unittest.main()
