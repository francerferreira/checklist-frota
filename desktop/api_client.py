from __future__ import annotations

from pathlib import Path

import requests


class APIClient:
    def __init__(self, base_url: str = "http://127.0.0.1:5000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.user = None
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
        response = self.session.request(method, f"{self.base_url}{path}", timeout=30, **kwargs)
        if response.ok:
            if response.content:
                return response.json()
            return None

        try:
            payload = response.json()
        except ValueError:
            payload = {}
        raise RuntimeError(payload.get("error") or f"Falha na requisicao {method} {path}.")

    def login(self, login: str, senha: str):
        payload = self._request("POST", "/login", json={"login": login, "senha": senha})
        token = payload["token"]
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.user = payload["user"]
        self._image_cache.clear()
        return payload

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

    def create_vehicle(self, payload: dict):
        return self._request("POST", "/veiculos", json=payload)

    def update_vehicle(self, vehicle_id: int, payload: dict):
        return self._request("PUT", f"/veiculos/{vehicle_id}", json=payload)

    def retire_vehicle(self, vehicle_id: int):
        return self._request("DELETE", f"/veiculos/{vehicle_id}")

    def import_inventory(self):
        return self._request("POST", "/veiculos/importar-inventario")

    def get_users(self):
        return self._request("GET", "/usuarios")

    def get_mechanics(self):
        return self._request("GET", "/usuarios/mecanicos")

    def create_user(self, payload: dict):
        return self._request("POST", "/usuarios", json=payload)

    def update_user(self, user_id: int, payload: dict):
        return self._request("PUT", f"/usuarios/{user_id}", json=payload)

    def delete_user(self, user_id: int):
        return self._request("DELETE", f"/usuarios/{user_id}")

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

    def get_activity(self, activity_id: int):
        return self._request("GET", f"/atividades/{activity_id}")

    def update_activity_item(self, activity_id: int, item_id: int, payload: dict):
        return self._request("PUT", f"/atividades/{activity_id}/itens/{item_id}", json=payload)

    def get_catalog(self):
        return self._request("GET", "/config/checklists")

    def get_checklist_items(self, tipo: str | None = None, ativos: str | None = "true"):
        params = {}
        if tipo:
            params["tipo"] = tipo
        if ativos is not None:
            params["ativos"] = ativos
        return self._request("GET", "/checklist-itens", params=params or None)

    def create_checklist_item(self, payload: dict):
        return self._request("POST", "/checklist-itens", json=payload)

    def update_checklist_item(self, item_id: int, payload: dict):
        return self._request("PUT", f"/checklist-itens/{item_id}", json=payload)

    def delete_checklist_item(self, item_id: int):
        return self._request("DELETE", f"/checklist-itens/{item_id}")

    def get_dashboard(self):
        return self._request("GET", "/relatorios/dashboard")

    def get_productivity_report(self):
        return self._request("GET", "/relatorios/produtividade")

    def get_macro_report(self):
        return self._request("GET", "/relatorios/macro")

    def get_micro_report(self):
        return self._request("GET", "/relatorios/micro")

    def get_item_report(self, item_name: str | None = None):
        params = {"item": item_name} if item_name else None
        return self._request("GET", "/relatorios/item", params=params)

    def get_non_conformities(self, vehicle: str | None = None, item_type: str | None = None, status: str | None = None):
        params = {}
        if vehicle:
            params["veiculo"] = vehicle
        if item_type:
            params["tipo"] = item_type
        if status:
            params["status"] = status
        return self._request("GET", "/nao_conformidades", params=params or None)

    def get_mechanic_non_conformities(self, status: str | None = None):
        params = {"status": status} if status else None
        return self._request("GET", "/mecanico/nao_conformidades", params=params)

    def resolve_non_conformity(self, item_id: int, payload: dict):
        return self._request("PUT", f"/nao_conformidade/{item_id}/resolver", json=payload)

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
