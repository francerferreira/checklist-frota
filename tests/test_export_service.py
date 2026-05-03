from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ROOT = PROJECT_ROOT / "desktop"
if str(DESKTOP_ROOT) not in sys.path:
    sys.path.insert(0, str(DESKTOP_ROOT))

from services.export_service import (
    export_activity_pdf,
    export_item_audit_pdf,
    export_material_report_pdf,
    export_material_report_xlsx,
    export_checklist_detail_pdf,
    export_non_conformity_pdf,
    export_rows_to_csv,
    export_rows_to_pdf,
    export_rows_to_xlsx,
    export_vehicle_detail_pdf,
)
from services.wash_reporting_service import export_wash_month_pdf
from PIL import Image



def make_sample_png() -> bytes:
    image = Image.new("RGB", (20, 20), color=(37, 99, 235))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class ExportServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)
        self.sample_png = make_sample_png()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_rows_to_csv_creates_file(self):
        path = self.output_dir / "macro.csv"
        export_rows_to_csv(
            [("Item", "item"), ("Total", "total")],
            [{"item": "Farol", "total": 2}],
            path,
        )
        self.assertTrue(path.exists())
        self.assertIn("Farol", path.read_text(encoding="utf-8-sig"))

    def test_export_rows_to_xlsx_creates_file(self):
        path = self.output_dir / "micro.xlsx"
        export_rows_to_xlsx(
            "Relatorio Micro",
            [("Frota", "frota"), ("Nao Conformidades", "nc")],
            [{"frota": "CV801", "nc": 3}],
            path,
        )
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1000)

    def test_export_rows_to_pdf_creates_file(self):
        path = self.output_dir / "macro.pdf"
        export_rows_to_pdf(
            "Relatorio Macro",
            "Consolidado executivo",
            [("Item", "item"), ("Total", "total")],
            [{"item": "Freio", "total": 4}],
            path,
            generated_by="Administrador",
        )
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1000)

    def test_export_non_conformity_pdf_creates_file_with_images(self):
        path = self.output_dir / "ocorrencia.pdf"
        item = {
            "veiculo": {"frota": "CV801", "tipo": "cavalo", "placa": "ABC-1234", "modelo": "Scania"},
            "usuario": {"nome": "Motorista"},
            "item_nome": "Farol baixo",
            "resolvido": True,
            "codigo_peca": "P-100",
            "descricao_peca": "Lampada",
            "observacao": "Troca executada",
            "created_at": "2026-04-11T12:00:00",
            "data_resolucao": "2026-04-11T15:00:00",
        }
        export_non_conformity_pdf(
            item,
            output_path=path,
            generated_by="Administrador",
            before_image=self.sample_png,
            after_image=self.sample_png,
        )
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1000)

    def test_export_open_non_conformity_pdf_creates_file_with_only_origin_evidence(self):
        path = self.output_dir / "ocorrencia_aberta.pdf"
        item = {
            "veiculo": {"frota": "CV801", "tipo": "cavalo", "placa": "ABC-1234", "modelo": "Scania"},
            "usuario": {"nome": "Motorista"},
            "item_nome": "Farol baixo",
            "resolvido": False,
            "codigo_peca": None,
            "descricao_peca": None,
            "observacao": "Aguardando tratativa",
            "created_at": "2026-04-11T12:00:00",
            "data_resolucao": None,
        }
        export_non_conformity_pdf(
            item,
            output_path=path,
            generated_by="Administrador",
            before_image=self.sample_png,
            after_image=self.sample_png,
        )
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1000)

    def test_export_checklist_detail_pdf_creates_professional_file(self):
        path = self.output_dir / "checklist_profissional.pdf"
        export_checklist_detail_pdf(
            {
                "vehicle": {"frota": "CV001", "placa": "ABC-1234", "modelo": "CAVALO"},
                "user": {"nome": "MARCIO"},
                "created_at": "2026-05-03T07:06:00",
                "total_itens": 2,
                "total_nc": 1,
                "itens": [
                    {"id": 1, "item_label": "FREIOS", "status": "OK", "resolvido": True},
                    {"id": 2, "item_label": "FAROL", "status": "NC", "observacao": "Quebrado", "resolvido": False},
                ],
            },
            output_path=path,
            generated_by="Administrador",
            item_images={2: {"before": self.sample_png, "after": self.sample_png}},
        )
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1000)

    def test_export_vehicle_detail_pdf_creates_file(self):
        path = self.output_dir / "equipamento.pdf"
        vehicle = {
            "frota": "CV801",
            "tipo": "cavalo",
            "placa": "ABC-1234",
            "modelo": "Scania P360XT",
            "ano": "2024",
            "chassi": "123",
            "configuracao": "Operacional",
            "atividade": "Container",
            "status": "ON",
            "local": "Patio",
            "descricao": "Operacional",
        }
        occurrences = [
            {
                "created_at": "2026-04-11T12:00:00",
                "item_nome": "Farol",
                "resolvido": False,
                "codigo_peca": None,
                "usuario": {"nome": "Motorista"},
                "id": 1,
                "veiculo": {"frota": "CV801", "tipo": "cavalo", "placa": "ABC-1234", "modelo": "Scania"},
            }
        ]
        export_vehicle_detail_pdf(
            vehicle,
            occurrences,
            output_path=path,
            generated_by="Administrador",
            vehicle_image=self.sample_png,
            occurrence_images={1: {"before": self.sample_png, "after": self.sample_png}},
        )
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1000)

    def test_export_item_audit_pdf_creates_file_with_images(self):
        path = self.output_dir / "auditoria_item.pdf"
        occurrences = [
            {
                "id": 10,
                "created_at": "2026-04-11T12:00:00",
                "data_resolucao": "2026-04-12T10:00:00",
                "item_nome": "Paralamas esquerdo",
                "resolvido": True,
                "codigo_peca": "P-300",
                "descricao_peca": "Paralamas",
                "observacao": "Resolvido para auditoria",
                "veiculo": {"frota": "CV801", "tipo": "cavalo", "placa": "ABC-1234", "modelo": "Scania"},
                "usuario": {"nome": "Motorista"},
                "resolved_by": {"nome": "Mecanico"},
            },
            {
                "id": 11,
                "created_at": "2026-04-13T12:00:00",
                "item_nome": "Paralamas esquerdo",
                "resolvido": False,
                "veiculo": {"frota": "CV802", "tipo": "cavalo", "placa": "DEF-5678", "modelo": "Volvo"},
                "usuario": {"nome": "Motorista"},
            },
        ]
        export_item_audit_pdf(
            "Paralamas esquerdo",
            occurrences,
            output_path=path,
            generated_by="Administrador",
            occurrence_images={10: {"before": self.sample_png, "after": self.sample_png}},
        )
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1000)

    def test_export_activity_pdf_creates_file_with_evidence(self):
        path = self.output_dir / "atividade.pdf"
        activity = {
            "titulo": "Troca em massa - Lanterna",
            "item_nome": "Lanterna",
            "tipo_equipamento": "cavalo",
            "codigo_peca": "P-200",
            "descricao_peca": "Lanterna traseira",
            "observacao": "Execucao do lote semanal",
            "status": "ABERTA",
            "created_at": "2026-04-11T12:00:00",
            "finalized_at": None,
            "resumo": {"total": 2, "instalados": 1, "nao_instalados": 0, "pendentes": 1},
            "itens": [
                {
                    "id": 10,
                    "status_execucao": "INSTALADO",
                    "observacao": "Troca concluida",
                    "foto_antes": "/uploads/antes.png",
                    "foto_depois": "/uploads/depois.png",
                    "instalado_em": "2026-04-11T15:00:00",
                    "veiculo": {"frota": "CV801", "placa": "ABC-1234", "modelo": "Scania"},
                },
                {
                    "id": 11,
                    "status_execucao": "PENDENTE",
                    "observacao": "Aguardando chegada de peca",
                    "foto_antes": None,
                    "foto_depois": None,
                    "instalado_em": None,
                    "veiculo": {"frota": "CV802", "placa": "DEF-5678", "modelo": "Scania"},
                },
            ],
        }
        export_activity_pdf(
            activity,
            output_path=path,
            generated_by="Administrador",
            item_images={10: {"before": self.sample_png, "after": self.sample_png}},
        )
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1000)

    def test_export_wash_month_pdf_creates_file_with_total_highlight(self):
        path = self.output_dir / "lavagens_mensal.pdf"
        export_wash_month_pdf(
            {
                "periodo": {"mes": 5, "ano": 2026, "rotulo": "Maio/2026"},
                "resumo": {"lavados_mes": 3, "valor_total": 1875.5},
                "indicadores": {
                    "por_categoria": [
                        {"categoria": "Lavagem completa", "quantidade": 2, "valor": 1250.0},
                        {"categoria": "Lavagem simples", "quantidade": 1, "valor": 625.5},
                    ],
                    "por_veiculo": [
                        {"referencia": "CV801", "quantidade": 2, "valor": 1250.0},
                        {"referencia": "CV905", "quantidade": 1, "valor": 625.5},
                    ],
                },
                "historico": [
                    {
                        "status": "LAVADO",
                        "wash_date": "2026-05-01T08:00:00",
                        "referencia": "CV801",
                        "carreta": "SR001",
                        "tipo_equipamento": "Lavagem completa",
                        "turno": "manha",
                        "local": "Pátio 1",
                        "valor": 625.0,
                        "vehicle": {"placa": "ABC-1234", "modelo": "Scania"},
                    },
                    {
                        "status": "LAVADO",
                        "wash_date": "2026-05-02T13:00:00",
                        "referencia": "CV801",
                        "carreta": "SR001",
                        "tipo_equipamento": "Lavagem completa",
                        "turno": "tarde",
                        "local": "Pátio 1",
                        "valor": 625.0,
                        "vehicle": {"placa": "ABC-1234", "modelo": "Scania"},
                    },
                    {
                        "status": "LAVADO",
                        "wash_date": "2026-05-03T13:00:00",
                        "referencia": "CV905",
                        "carreta": "SR002",
                        "tipo_equipamento": "Lavagem simples",
                        "turno": "tarde",
                        "local": "Pátio 2",
                        "valor": 625.5,
                        "vehicle": {"placa": "DEF-5678", "modelo": "Volvo"},
                    },
                ],
            },
            output_path=path,
            generated_by="Administrador",
        )
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1000)

    def test_export_material_report_files_create_successfully(self):
        xlsx_path = self.output_dir / "estoque.xlsx"
        pdf_path = self.output_dir / "estoque.pdf"
        report = {
            "periodo": {"data_inicial": "2026-04-01", "data_final": "2026-04-11"},
            "resumo": {
                "total_materiais": 12,
                "abaixo_minimo": 2,
                "saldo_total": 145,
                "consumo_total_periodo": 23,
            },
            "baixo_estoque": [
                {
                    "referencia": "MAT-001",
                    "descricao": "Lanterna traseira",
                    "aplicacao_tipo": "cavalo",
                    "quantidade_estoque": 2,
                    "estoque_minimo": 5,
                    "deficit": 3,
                }
            ],
            "consumo_periodo": [
                {
                    "referencia": "MAT-001",
                    "descricao": "Lanterna traseira",
                    "consumo_total": 9,
                    "ultimo_consumo": "2026-04-11T15:00:00",
                }
            ],
            "ranking_uso": [
                {
                    "referencia": "MAT-001",
                    "descricao": "Lanterna traseira",
                    "consumo_total": 9,
                    "ultimo_consumo": "2026-04-11T15:00:00",
                }
            ],
        }
        export_material_report_xlsx(report, output_path=xlsx_path)
        export_material_report_pdf(report, output_path=pdf_path, generated_by="Administrador")
        self.assertTrue(xlsx_path.exists())
        self.assertTrue(pdf_path.exists())
        self.assertGreater(xlsx_path.stat().st_size, 1000)
        self.assertGreater(pdf_path.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()

