from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import requests


DEFAULT_API_BASE_URL = (
    os.getenv("CHECKLIST_API_URL")
    or os.getenv("API_BASE_URL")
    or "https://checklist-frota-qngw.onrender.com"
)


class APIClient:
    def __init__(self, base_url: str = DEFAULT_API_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.user = None
        self.login_started_at: datetime | None = None
        self._image_cache: dict[str, bytes | None] = {}

    def set_base_url(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._image_cache.clear()

    def ping(self) -> bool:
        try:
            response = self.session.get(f"{self.base_url}/login", timeout=3)
            return response.status_code < 500
        except requests.RequestException:
            return False

    def _request(self, method: str, path: str, **kwargs):
        timeout = kwargs.pop("timeout", 30)
        response = self.session.request(method, f"{self.base_url}{path}", timeout=timeout, **kwargs)
        if response.ok:
            if response.content:
                payload = response.json()
                if isinstance(payload, dict):
                    if payload.get("success") is False:
                        raise RuntimeError(payload.get("error") or f"Falha na requisicao {method} {path}.")
                    if "data" in payload:
                        return payload["data"]
                return payload
            return None

        try:
            payload = response.json()
        except ValueError:
            payload = {}
        raise RuntimeError(payload.get("error") or f"Falha na requisicao {method} {path}.")

    def login(self, login: str, senha: str):
        payload = self._request("POST", "/login", json={"login": login, "senha": senha}, timeout=20)
        token = payload["token"]
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.user = payload["user"]
        self.login_started_at = datetime.now()
        self._image_cache.clear()
        return payload

    def user_has_admin_access(self) -> bool:
        return bool(self.user and self.user.get("tipo") == "admin")

    def user_has_management_access(self) -> bool:
        return bool(self.user and self.user.get("tipo") in {"admin", "gestor"})

    def clear_session(self) -> None:
        try:
            if "Authorization" in self.session.headers:
                self.logout()
        except Exception:
            pass
        self.session.headers.pop("Authorization", None)
        self.user = None
        self.login_started_at = None
        self._image_cache.clear()

    def get_vehicles(self, tipo: str | None = None):
        params = {"tipo": tipo} if tipo else {}
        return self._request("GET", "/veiculos", params=params or None)

    def get_equipment(self, tipo: str | None = None, ativos: bool | None = None):
        params = {}
        if tipo:
            params["tipo"] = tipo
        if ativos is not None:
            params["ativos"] = "true" if ativos else "false"
        return self._request("GET", "/veiculos", params=params)

    def get_vehicle_history(self, vehicle_id: int):
        return self._request("GET", f"/veiculos/{vehicle_id}/historico")

    def get_equipment_structure(self):
        return self._request("GET", "/equipamentos/estrutura")

    def get_availability_overview(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        family_id: int | None = None,
        location_id: int | None = None,
    ):
        params = {}
        if date_from:
            params["data_inicial"] = date_from
        if date_to:
            params["data_final"] = date_to
        if family_id:
            params["familia_id"] = family_id
        if location_id:
            params["local_id"] = location_id
        return self._request("GET", "/disponibilidade/visao", params=params or None)

    def get_critical_equipment(self):
        return self._request("GET", "/dashboard-manutencao/ativos-criticos")

    def set_equipment_operational_status(self, vehicle_id: int, payload: dict):
        return self._request("PUT", f"/equipamentos/{vehicle_id}/status-operacional", json=payload)

    def get_equipment_status_history(self, vehicle_id: int):
        return self._request("GET", f"/equipamentos/{vehicle_id}/status-historico")

    def get_spreader_daily_history(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        spreader_id: int | None = None,
        lbs_id: int | None = None,
        status: str | None = None,
    ):
        params = {}
        if date_from:
            params["data_inicial"] = date_from
        if date_to:
            params["data_final"] = date_to
        if spreader_id:
            params["spreader_id"] = spreader_id
        if lbs_id:
            params["lbs_id"] = lbs_id
        if status:
            params["status"] = status
        return self._request("GET", "/equipamentos/spreaders/historico", params=params or None)

    def record_equipment_hourmeter(self, vehicle_id: int, payload: dict):
        return self._request("POST", f"/equipamentos/{vehicle_id}/horimetros", json=payload)

    def get_equipment_hourmeters(self, vehicle_id: int):
        return self._request("GET", f"/equipamentos/{vehicle_id}/horimetros")

    def get_emergencies(self, status: str | None = None):
        params = {"status": status} if status else None
        return self._request("GET", "/emergenciais", params=params)

    def triage_emergency(self, emergency_id: int, payload: dict):
        return self._request("PUT", f"/emergenciais/{emergency_id}/triagem", json=payload)

    def convert_emergency_to_work_order(self, emergency_id: int, payload: dict):
        return self._request("POST", f"/emergenciais/{emergency_id}/converter-os", json=payload)

    def get_inspection_templates(self, *, include_all: bool = False, vehicle_id: int | None = None):
        params = {}
        if include_all:
            params["incluir_todos"] = "true"
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        return self._request("GET", "/inspecoes-tecnicas/modelos", params=params or None)

    def create_inspection_template(self, payload: dict):
        return self._request("POST", "/inspecoes-tecnicas/modelos", json=payload)

    def update_inspection_template(self, template_id: int, payload: dict):
        return self._request("PUT", f"/inspecoes-tecnicas/modelos/{template_id}", json=payload)

    def publish_inspection_template(self, template_id: int):
        return self._request("POST", f"/inspecoes-tecnicas/modelos/{template_id}/publicar", json={})

    def create_inspection_template_version(self, template_id: int):
        return self._request("POST", f"/inspecoes-tecnicas/modelos/{template_id}/nova-versao", json={})

    def get_technical_inspection_executions(self, vehicle_id: int | None = None):
        params = {"vehicle_id": vehicle_id} if vehicle_id else None
        return self._request("GET", "/inspecoes-tecnicas/execucoes", params=params)

    def create_equipment_family(self, payload: dict):
        return self._request("POST", "/equipamentos/familias", json=payload)

    def update_equipment_family(self, family_id: int, payload: dict):
        return self._request("PUT", f"/equipamentos/familias/{family_id}", json=payload)

    def create_operational_location(self, payload: dict):
        return self._request("POST", "/equipamentos/locais", json=payload)

    def update_operational_location(self, location_id: int, payload: dict):
        return self._request("PUT", f"/equipamentos/locais/{location_id}", json=payload)

    def get_equipment_links(self, *, active: bool | None = None, parent_id: int | None = None, child_id: int | None = None):
        params = {}
        if active is not None:
            params["active"] = str(active).lower()
        if parent_id:
            params["parent_equipment_id"] = parent_id
        if child_id:
            params["child_equipment_id"] = child_id
        return self._request("GET", "/equipamentos/vinculos", params=params or None)

    def create_equipment_link(self, payload: dict):
        return self._request("POST", "/equipamentos/vinculos", json=payload)

    def close_equipment_link(self, link_id: int):
        return self._request("PUT", f"/equipamentos/vinculos/{link_id}/encerrar", json={})

    def create_vehicle(self, payload: dict):
        return self._request("POST", "/veiculos", json=payload)

    def update_vehicle(self, vehicle_id: int, payload: dict):
        result = self._request("PUT", f"/veiculos/{vehicle_id}", json=payload)
        # Limpar cache de imagem quando veiculo for atualizado
        # Garante que dados recentes sejam carregados
        self._image_cache.clear()
        return result

    def retire_vehicle(self, vehicle_id: int):
        return self._request("DELETE", f"/veiculos/{vehicle_id}")

    def import_inventory(self):
        return self._request("POST", "/veiculos/importar-inventario")

    def get_users(self):
        return self._request("GET", "/usuarios")

    def get_user_profile(self, user_id: int):
        return self._request("GET", f"/usuarios/{user_id}/perfil")

    def reset_user_first_access(self, user_id: int):
        return self._request("POST", f"/usuarios/{user_id}/reset-primeiro-acesso")

    def update_user_pages(self, user_id: int, page_keys: list[str]):
        return self._request("PUT", f"/usuarios/{user_id}/telas", json={"page_keys": page_keys})

    def get_mechanics(self):
        return self._request("GET", "/usuarios/mecanicos")

    def create_user(self, payload: dict):
        return self._request("POST", "/usuarios", json=payload)

    def update_user(self, user_id: int, payload: dict):
        return self._request("PUT", f"/usuarios/{user_id}", json=payload)

    def update_own_password(self, current_password: str, new_password: str):
        return self._request(
            "PUT",
            "/usuarios/me/senha",
            json={"senha_atual": current_password, "nova_senha": new_password},
        )

    def delete_user(self, user_id: int):
        return self._request("DELETE", f"/usuarios/{user_id}")

    def get_employees(self, *, search: str | None = None, status: str | None = None, team: str | None = None, shift: str | None = None):
        params = {"busca": search, "situacao": status, "equipe": team, "turno": shift}
        return self._request("GET", "/rh/colaboradores", params={key: value for key, value in params.items() if value})

    def get_linkable_employee_users(self):
        return self._request("GET", "/rh/colaboradores/usuarios-disponiveis")

    def create_employee(self, payload: dict):
        return self._request("POST", "/rh/colaboradores", json=payload)

    def update_employee(self, employee_id: int, payload: dict):
        return self._request("PUT", f"/rh/colaboradores/{employee_id}", json=payload)

    def get_employee_attendance(self, *, employee_id: int | None = None, occurrence_date: str | None = None, occurrence_type: str | None = None):
        params = {"colaborador_id": employee_id, "data": occurrence_date, "tipo": occurrence_type}
        return self._request("GET", "/rh/frequencia", params={key: value for key, value in params.items() if value})

    def get_mobile_absenteeism(self, *, reference_date: str, **filters):
        params = {"data": reference_date, **filters}
        return self._request(
            "GET",
            "/rh/absenteismo-mobile",
            params={key: value for key, value in params.items() if value not in (None, "")},
        )

    def save_mobile_absenteeism(self, *, reference_date: str, entries: list[dict]):
        return self._request(
            "POST",
            "/rh/absenteismo-mobile",
            json={"date": reference_date, "entries": entries},
        )

    def get_special_schedules(self, schedule_date: str | None = None):
        params = {"data": schedule_date} if schedule_date else None
        return self._request("GET", "/rh/escalas-especiais", params=params)

    def create_special_schedule(self, payload: dict):
        return self._request("POST", "/rh/escalas-especiais", json=payload)

    def get_special_schedule_pdf(self, schedule_date: str | None = None, schedule_type: str | None = None) -> bytes:
        params = {}
        if schedule_date:
            params["data"] = schedule_date
        if schedule_type:
            params["tipo"] = schedule_type
        response = self.session.get(f"{self.base_url}/rh/escalas-especiais/pdf", params=params or None, timeout=30)
        if not response.ok:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            raise RuntimeError(payload.get("error") or "Falha ao exportar a escala em PDF.")
        return response.content

    def create_employee_attendance(self, payload: dict):
        return self._request("POST", "/rh/frequencia", json=payload)

    def update_employee_attendance(self, record_id: int, payload: dict):
        return self._request("PUT", f"/rh/frequencia/{record_id}", json=payload)

    def cancel_employee_attendance(self, record_id: int, reason: str):
        return self._request("POST", f"/rh/frequencia/{record_id}/cancelar", json={"reason": reason})

    def get_employee_documents(self, *, employee_id: int | None = None):
        params = {"colaborador_id": employee_id} if employee_id else None
        return self._request("GET", "/rh/documentos", params=params)

    def create_employee_document(self, payload: dict):
        return self._request("POST", "/rh/documentos", json=payload)

    def get_employee_trainings(self, *, employee_id: int | None = None):
        params = {"colaborador_id": employee_id} if employee_id else None
        return self._request("GET", "/rh/treinamentos", params=params)

    def create_employee_training(self, payload: dict):
        return self._request("POST", "/rh/treinamentos", json=payload)

    def get_employee_history(self, employee_id: int):
        return self._request("GET", "/rh/historico", params={"colaborador_id": employee_id})

    def create_employee_history(self, payload: dict):
        return self._request("POST", "/rh/historico", json=payload)

    def get_hr_management(self, *, date_from: str | None = None, date_to: str | None = None, alert_days: int = 30):
        params = {"data_inicial": date_from, "data_final": date_to, "dias_alerta": alert_days}
        return self._request("GET", "/rh/gestao", params={key: value for key, value in params.items() if value is not None})

    def register_hr_export(self, payload: dict):
        return self._request("POST", "/rh/gestao/exportacoes", json=payload)

    def get_employee_vacations(
        self,
        *,
        employee_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        status: str | None = None,
    ):
        params = {
            "colaborador_id": employee_id,
            "data_inicial": date_from,
            "data_final": date_to,
            "situacao": status,
        }
        return self._request("GET", "/rh/ferias", params={key: value for key, value in params.items() if value})

    def create_employee_vacation(self, payload: dict):
        return self._request("POST", "/rh/ferias", json=payload)

    def cancel_employee_vacation(self, vacation_id: int, reason: str):
        return self._request("POST", f"/rh/ferias/{vacation_id}/cancelar", json={"reason": reason})

    def get_wash_overview(self, year: int | None = None, month: int | None = None):
        params = {}
        if year:
            params["ano"] = year
        if month:
            params["mes"] = month
        return self._request("GET", "/lavagens/visao", params=params or None)

    def sync_wash_queue(self):
        return self._request("POST", "/lavagens/sincronizar")

    def reclassify_wash_queue(self):
        return self._request("POST", "/lavagens/reclassificar")

    def register_wash(self, payload: dict):
        return self._request("POST", "/lavagens/registrar", json=payload)

    def set_wash_unavailable(self, queue_item_id: int, payload: dict):
        return self._request("PUT", f"/lavagens/fila/{queue_item_id}/indisponivel", json=payload)

    def set_wash_available(self, queue_item_id: int):
        return self._request("PUT", f"/lavagens/fila/{queue_item_id}/disponivel", json={})

    def schedule_wash_preventive(self, payload: dict):
        return self._request("PUT", "/lavagens/preventiva", json=payload)

    def update_wash_plan(self, payload: dict):
        return self._request("PUT", "/lavagens/plano", json=payload)

    def set_wash_blocked_day(self, payload: dict):
        return self._request("PUT", "/lavagens/plano/bloqueio", json=payload)

    def get_wash_tomorrow_message(self, reference_date: str | None = None):
        params = {"data": reference_date} if reference_date else None
        return self._request("GET", "/lavagens/mensagem-amanha", params=params)

    def set_wash_schedule_decision(self, payload: dict):
        return self._request("PUT", "/lavagens/cronograma/decisao", json=payload)

    def reedit_wash_schedule_decision(self, payload: dict):
        return self._request("PUT", "/lavagens/cronograma/reeditar", json=payload)

    def get_maintenance_overview(
        self,
        year: int | None = None,
        month: int | None = None,
        mechanic_id: int | None = None,
    ):
        params = {}
        if year:
            params["ano"] = year
        if month:
            params["mes"] = month
        if mechanic_id:
            params["mecanico_id"] = mechanic_id
        return self._request("GET", "/manutencao/visao", params=params or None)

    def get_maintenance_schedules(self):
        return self._request("GET", "/manutencao/programacoes")

    def create_maintenance_schedule(self, payload: dict):
        return self._request("POST", "/manutencao/programacoes", json=payload)

    def get_maintenance_mechanic_suggestion(self, payload: dict):
        return self._request("POST", "/manutencao/sugestao-responsavel", json=payload)

    def get_maintenance_schedule_suggestion(self, payload: dict):
        return self._request("POST", "/manutencao/sugestao-agenda", json=payload)

    def get_maintenance_material_suggestion(self, schedule_id: int):
        return self._request("GET", f"/manutencao/programacoes/{schedule_id}/sugestao-peca")

    def link_maintenance_schedule_material(self, schedule_id: int, payload: dict):
        return self._request("POST", f"/manutencao/programacoes/{schedule_id}/materiais", json=payload)

    def program_maintenance_schedule(self, schedule_id: int, payload: dict):
        return self._request("PUT", f"/manutencao/programacoes/{schedule_id}/cronograma", json=payload)

    def reprogram_maintenance_item(self, item_id: int, payload: dict):
        return self._request("PUT", f"/manutencao/itens/{item_id}/reprogramar", json=payload)

    def update_maintenance_item(self, item_id: int, payload: dict):
        return self._request("PUT", f"/manutencao/itens/{item_id}", json=payload)

    def get_pcm_agenda(self, year: int | None = None, month: int | None = None):
        params = {key: value for key, value in {"ano": year, "mes": month}.items() if value}
        return self._request("GET", "/pcm/agenda", params=params or None)

    def get_pcm_backlog(self):
        return self._request("GET", "/pcm/backlog")

    def get_pcm_programming(self, *, date_from: str | None = None, date_to: str | None = None, daily_capacity_minutes: int = 480):
        params = {"data_inicial": date_from, "data_final": date_to, "capacidade_minutos": daily_capacity_minutes}
        return self._request("GET", "/pcm/programacao", params={key: value for key, value in params.items() if value is not None})

    def get_maintenance_resources(self):
        return self._request("GET", "/recursos")

    def create_maintenance_resource(self, payload: dict):
        return self._request("POST", "/recursos", json=payload)

    def get_maintenance_resource_reservations(self, resource_id: int):
        return self._request("GET", f"/recursos/{resource_id}/reservas")

    def reserve_maintenance_resource(self, resource_id: int, payload: dict):
        return self._request("POST", f"/recursos/{resource_id}/reservas", json=payload)

    def cancel_maintenance_resource_reservation(self, reservation_id: int, reason: str | None = None):
        return self._request("POST", f"/recursos/reservas/{reservation_id}/cancelar", json={"reason": reason or ""})

    def get_suppliers(self):
        return self._request("GET", "/compras/fornecedores")

    def create_supplier(self, payload: dict):
        return self._request("POST", "/compras/fornecedores", json=payload)

    def get_purchase_requests(self):
        return self._request("GET", "/compras/solicitacoes")

    def get_purchase_request(self, purchase_id: int):
        return self._request("GET", f"/compras/solicitacoes/{purchase_id}")

    def create_purchase_request(self, payload: dict):
        return self._request("POST", "/compras/solicitacoes", json=payload)

    def approve_purchase_request(self, purchase_id: int):
        return self._request("POST", f"/compras/solicitacoes/{purchase_id}/aprovar", json={})

    def receive_purchase_request(self, purchase_id: int, payload: dict):
        return self._request("POST", f"/compras/solicitacoes/{purchase_id}/recebimentos", json=payload)

    def get_navigation_preferences(self):
        return self._request("GET", "/navegacao/preferencias")

    def toggle_navigation_favorite(self, page_key: str):
        return self._request("PUT", f"/navegacao/paginas/{page_key}/favorito", json={})

    def register_navigation_access(self, page_key: str):
        return self._request("POST", f"/navegacao/paginas/{page_key}/acessar", json={})

    def search_global_records(self, query: str, limit: int = 20):
        return self._request("GET", "/navegacao/busca-global", params={"q": query, "limite": limit})

    def get_preventive_plans(self):
        return self._request("GET", "/pcm/planos-preventivos")

    def create_preventive_plan(self, payload: dict):
        return self._request("POST", "/pcm/planos-preventivos", json=payload)

    def generate_due_preventives(self, plan_id: int | None = None):
        payload = {"plan_id": plan_id} if plan_id else {}
        return self._request("POST", "/pcm/gerar-preventivas", json=payload)

    def get_warehouses(self):
        return self._request("GET", "/suprimentos/depositos")

    def create_warehouse(self, payload: dict):
        return self._request("POST", "/suprimentos/depositos", json=payload)

    def get_warehouse_stocks(self):
        return self._request("GET", "/suprimentos/estoques")

    def initialize_warehouse_stock(self, payload: dict):
        return self._request("POST", "/suprimentos/estoques", json=payload)

    def get_warehouse_reservations(self):
        return self._request("GET", "/suprimentos/reservas")

    def reserve_warehouse_material(self, payload: dict):
        return self._request("POST", "/suprimentos/reservas", json=payload)

    def set_material_family_applications(self, material_id: int, family_ids: list[int]):
        return self._request("PUT", f"/materiais/{material_id}/familias", json={"family_ids": family_ids})

    def get_technical_documents(self, vehicle_id: int | None = None, *, include_archived: bool = False):
        params = {"vehicle_id": vehicle_id} if vehicle_id else {}
        if include_archived:
            params["incluir_arquivados"] = "true"
        return self._request("GET", "/biblioteca-tecnica", params=params or None)

    def create_technical_document(self, payload: dict):
        return self._request("POST", "/biblioteca-tecnica", json=payload)

    def download_maintenance_pdf(
        self,
        output_path: str,
        *,
        report_type: str = "mensal",
        year: int | None = None,
        month: int | None = None,
        mechanic_id: int | None = None,
        vehicle_id: int | None = None,
    ) -> None:
        params: dict[str, str | int] = {"tipo": report_type or "mensal"}
        if year:
            params["ano"] = int(year)
        if month:
            params["mes"] = int(month)
        if mechanic_id:
            params["mecanico_id"] = int(mechanic_id)
        if vehicle_id:
            params["vehicle_id"] = int(vehicle_id)

        response = self.session.get(
            f"{self.base_url}/manutencao/relatorio/pdf",
            params=params,
            timeout=180,
            stream=True,
        )
        if not response.ok:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            raise RuntimeError(payload.get("error") or "Falha ao baixar relatorio de manutencao.")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as file_handle:
            for chunk in response.iter_content(chunk_size=1024 * 512):
                if chunk:
                    file_handle.write(chunk)

    def download_maintenance_work_order_pdf(self, work_order_id: int, output_path: str) -> None:
        response = self.session.get(
            f"{self.base_url}/manutencao/os/{int(work_order_id)}/pdf",
            timeout=180,
            stream=True,
        )
        if not response.ok:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            raise RuntimeError(payload.get("error") or "Falha ao baixar ordem de serviço.")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as file_handle:
            for chunk in response.iter_content(chunk_size=1024 * 512):
                if chunk:
                    file_handle.write(chunk)

    def update_wash_values(self, values: list[dict]):
        return self._request("PUT", "/lavagens/valores", json={"valores": values})

    def get_materials(
        self,
        tipo: str | None = None,
        search: str | None = None,
        ativos: str | None = "true",
        baixo_estoque: bool | None = None,
    ):
        params = {}
        if tipo:
            params["tipo"] = tipo
        if search:
            params["q"] = search
        if ativos is not None:
            params["ativos"] = ativos
        if baixo_estoque is not None:
            params["baixo_estoque"] = "true" if baixo_estoque else "false"
        return self._request("GET", "/materiais", params=params or None)

    def create_material(self, payload: dict):
        return self._request("POST", "/materiais", json=payload)

    def update_material(self, material_id: int, payload: dict):
        return self._request("PUT", f"/materiais/{material_id}", json=payload)

    def delete_material(self, material_id: int):
        return self._request("DELETE", f"/materiais/{material_id}")

    def get_material_movements(self, material_id: int):
        return self._request("GET", f"/materiais/{material_id}/movimentos")

    def adjust_material_stock(self, material_id: int, payload: dict):
        return self._request("POST", f"/materiais/{material_id}/ajustar_estoque", json=payload)

    def get_material_report(self, date_from: str | None = None, date_to: str | None = None):
        params = {}
        if date_from:
            params["data_inicial"] = date_from
        if date_to:
            params["data_final"] = date_to
        return self._request("GET", "/materiais/relatorio", params=params or None)

    def get_activities(
        self,
        tipo: str | None = None,
        status: str | None = None,
        item_name: str | None = None,
        mechanic_id: int | None = None,
    ):
        params = {}
        if tipo:
            params["tipo"] = tipo
        if status:
            params["status"] = status
        if item_name:
            params["item"] = item_name
        if mechanic_id:
            params["mecanico_id"] = mechanic_id
        return self._request("GET", "/atividades", params=params or None)

    def create_activity(self, payload: dict):
        return self._request("POST", "/atividades", json=payload)

    def create_mass_activity_from_non_conformity_item(self, payload: dict):
        return self._request("POST", "/atividades/nao_conformidades/lote", json=payload)

    def get_activity(self, activity_id: int):
        return self._request("GET", f"/atividades/{activity_id}")

    def update_activity_item(self, activity_id: int, item_id: int, payload: dict):
        return self._request("PUT", f"/atividades/{activity_id}/itens/{item_id}", json=payload)

    def update_activity_materials(self, activity_id: int, payload: dict):
        return self._request("PUT", f"/atividades/{activity_id}/materiais", json=payload)

    def get_catalog(self):
        return self._request("GET", "/config/checklists")

    def get_checklist_items(self, tipo: str | None = None, ativos: str | None = "true"):
        params = {}
        if tipo:
            params["tipo"] = tipo
        if ativos is not None:
            params["ativos"] = ativos
        return self._request("GET", "/checklist-itens", params=params or None)

    def get_checklist_history_matrix(
        self,
        tipo: str | None = None,
        data_inicio: str | None = None,
        data_fim: str | None = None,
    ):
        params = {}
        if tipo:
            params["tipo"] = tipo
        if data_inicio:
            params["data_inicio"] = data_inicio
        if data_fim:
            params["data_fim"] = data_fim
        return self._request("GET", "/checklist/historico-matriz", params=params or None)

    def get_checklist_detail(self, checklist_id: int):
        return self._request("GET", f"/checklists/{checklist_id}")

    def create_checklist_item(self, payload: dict):
        return self._request("POST", "/checklist-itens", json=payload)

    def update_checklist_item(self, item_id: int, payload: dict):
        return self._request("PUT", f"/checklist-itens/{item_id}", json=payload)

    def delete_checklist_item(self, item_id: int):
        return self._request("DELETE", f"/checklist-itens/{item_id}")

    def get_dashboard(self):
        return self._request("GET", "/relatorios/dashboard")

    def get_maintenance_executive_report(self):
        return self._request("GET", "/relatorios/manutencao-executivo")

    def get_automation_alerts(self):
        return self._request("GET", "/inteligencia/automacoes")

    def evaluate_automation_rules(self):
        return self._request("POST", "/inteligencia/automacoes/avaliar")

    def acknowledge_automation_alert(self, alert_id: int):
        return self._request("PUT", f"/inteligencia/automacoes/{alert_id}/reconhecer")

    def get_productivity_report(self):
        return self._request("GET", "/relatorios/produtividade")

    def get_macro_report(self):
        return self._request("GET", "/relatorios/macro")

    def get_micro_report(self, ativos: bool | None = True):
        params = None
        if ativos is not None:
            params = {"ativos": "true" if ativos else "false"}
        return self._request("GET", "/relatorios/micro", params=params)

    def get_item_report(
        self,
        item_name: str | None = None,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        nc_status: str | None = None,
        modulo: str | None = None,
        data_base: str | None = None,
    ):
        params = {}
        if item_name:
            params["item"] = item_name
        if date_from:
            params["data_de"] = date_from
        if date_to:
            params["data_ate"] = date_to
        if nc_status:
            params["status_nc"] = nc_status
        if modulo:
            params["modulo"] = modulo
        if data_base:
            params["data_base"] = data_base
        return self._request("GET", "/relatorios/item", params=params or None)

    def get_cloud_storage_status(self):
        return self._request("GET", "/admin/storage/status")

    def get_intelligent_rules(self):
        return self._request("GET", "/admin/intelligent-rules")

    def update_intelligent_rules(self, payload: dict):
        return self._request("PUT", "/admin/intelligent-rules", json=payload)

    def get_compatibility_status(self):
        return self._request("GET", "/admin/compatibility-status")

    def get_homologation_status(self):
        return self._request("GET", "/admin/homologation-status")

    def logout(self):
        return self._request("POST", "/logout", timeout=8)

    def get_audit_logs(
        self,
        entidade: str | None = None,
        data_inicio: str | None = None,
        data_fim: str | None = None,
    ):
        params = {}
        if entidade:
            params["entidade"] = entidade
        if data_inicio:
            params["data_inicio"] = data_inicio
        if data_fim:
            params["data_fim"] = data_fim
        return self._request("GET", "/admin/audit-logs", params=params or None)

    def create_cloud_backup(self):
        return self._request("POST", "/admin/backups/create", timeout=180)

    def download_cloud_backup(self, download_url: str, output_path: str) -> None:
        response = self.session.get(self.make_absolute_url(download_url), timeout=180, stream=True)
        if not response.ok:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            raise RuntimeError(payload.get("error") or "Falha ao baixar backup.")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as file_handle:
            for chunk in response.iter_content(chunk_size=1024 * 512):
                if chunk:
                    file_handle.write(chunk)

    def get_non_conformities(self, vehicle: str | None = None, item_type: str | None = None, status: str | None = None):
        params = {}
        if vehicle:
            params["veiculo"] = vehicle
        if item_type:
            params["tipo"] = item_type
        if status:
            params["status"] = status
        return self._request("GET", "/nao_conformidades", params=params or None)

    def get_resolution_packages(self, status: str | None = None):
        params = {"status": status} if status else None
        return self._request("GET", "/pacotes_resolucao", params=params)

    def get_resolution_package_suggestions(self, checklist_item_ids: list[int]):
        return self._request("POST", "/pacotes_resolucao/sugestoes", json={"checklist_item_ids": checklist_item_ids})

    def create_resolution_package(self, payload: dict):
        return self._request("POST", "/pacotes_resolucao", json=payload)

    def add_items_to_resolution_package(self, package_id: int, checklist_item_ids: list[int], observation: str | None = None):
        payload = {"checklist_item_ids": checklist_item_ids}
        if observation:
            payload["observation"] = observation
        return self._request("POST", f"/pacotes_resolucao/{package_id}/itens", json=payload)

    def get_mechanic_non_conformities(self, status: str | None = None):
        params = {"status": status} if status else None
        return self._request("GET", "/mecanico/nao_conformidades", params=params)

    def resolve_non_conformity(self, item_id: int, payload: dict):
        return self._request("PUT", f"/nao_conformidade/{item_id}/resolver", json=payload)

    def create_activity_from_non_conformity(self, item_id: int, payload: dict):
        return self._request("POST", f"/nao_conformidade/{item_id}/atividade", json=payload)

    def upload_file(self, file_path: str, vehicle: str, item: str, user: str) -> dict:
        path = Path(file_path)
        with path.open("rb") as file_handle:
            files = {"file": (path.name, file_handle)}
            data = {"vehicle": vehicle, "item": item, "user": user}
            return self._request("POST", "/upload", files=files, data=data)

    def fetch_image(self, relative_path: str | None) -> bytes | None:
        if not relative_path:
            return None
        if relative_path in self._image_cache:
            return self._image_cache[relative_path]
        response = self.session.get(self.make_absolute_url(relative_path), timeout=30)
        if not response.ok:
            self._image_cache[relative_path] = None
            return None
        self._image_cache[relative_path] = response.content
        return response.content

    def make_absolute_url(self, relative_path: str | None) -> str:
        if not relative_path:
            return ""
        if relative_path.startswith("http://") or relative_path.startswith("https://"):
            return relative_path
        return f"{self.base_url}{relative_path}"
