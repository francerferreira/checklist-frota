from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


DEFAULT_API_URL = "https://checklist-frota-qngw.onrender.com"
DEFAULT_LOGIN = "admin"
DEFAULT_PASSWORD = "123456"
DEFAULT_DB_PATH = Path("backend/checklist_frota.db")


def banner() -> None:
    print("=" * 52)
    print("  Checklist de Frota - Migracao para nuvem")
    print("=" * 52)
    print()


def is_safe_remote_reference(value: str | None) -> bool:
    if not value:
        return False
    text = value.strip()
    if not text:
        return False
    if text.startswith("http://") or text.startswith("https://"):
        return True
    if text.startswith("/uploads/") or text.startswith("uploads/"):
        return True
    if text.startswith("backend_data/uploads/"):
        return True
    return False


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "t", "yes", "y", "on", "sim"}


def build_payload(row: dict[str, Any]) -> dict[str, Any]:
    status = clean(row.get("status")) or "ON"
    ativo = normalize_bool(row.get("ativo"))
    if status.upper() in {"RETIRADO", "OFF"}:
        ativo = False

    payload: dict[str, Any] = {
        "frota": (clean(row.get("frota")) or "").upper(),
        "tipo": (clean(row.get("tipo")) or "").lower(),
        "placa": (clean(row.get("placa")) or "S/PLACA").upper(),
        "ano": clean(row.get("ano")),
        "modelo": clean(row.get("modelo")) or "CAVALO MECANICO",
        "chassi": clean(row.get("chassi")),
        "configuracao": clean(row.get("configuracao")),
        "atividade": clean(row.get("atividade")),
        "status": status.upper(),
        "local": clean(row.get("local")),
        "descricao": clean(row.get("descricao")),
        "ativo": ativo,
    }

    foto_path = clean(row.get("foto_path"))
    if is_safe_remote_reference(foto_path):
        payload["foto_path"] = foto_path

    # Remove campos vazios opcionais, mas mantém os obrigatórios e o estado.
    for key in ("ano", "chassi", "configuracao", "atividade", "local", "descricao"):
        if payload.get(key) is None:
            payload.pop(key, None)

    return payload


def fetch_local_vehicles(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        raise FileNotFoundError(f"Banco local nao encontrado: {db_path}")

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT id, frota, placa, ano, modelo, tipo, chassi, configuracao,
                   atividade, status, local, descricao, foto_path, ativo, retirado_em
            FROM vehicles
            ORDER BY id
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()


@dataclass
class CloudClient:
    base_url: str
    login: str
    password: str

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.session = requests.Session()
        self.token = None

    def authenticate(self) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/login",
            json={"login": self.login, "senha": self.password},
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(f"Falha no login na nuvem: {response.status_code} {response.text}")
        payload = response.json()
        token = payload["token"]
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.token = token
        return payload

    def list_vehicles(self) -> list[dict[str, Any]]:
        response = self.session.get(f"{self.base_url}/veiculos", timeout=30)
        if not response.ok:
            raise RuntimeError(f"Falha ao listar veiculos da nuvem: {response.status_code} {response.text}")
        return response.json()

    def create_vehicle(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(f"{self.base_url}/veiculos", json=payload, timeout=30)
        if not response.ok:
            raise RuntimeError(f"Falha ao criar veiculo {payload.get('frota')}: {response.status_code} {response.text}")
        return response.json()

    def update_vehicle(self, vehicle_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.put(f"{self.base_url}/veiculos/{vehicle_id}", json=payload, timeout=30)
        if not response.ok:
            raise RuntimeError(f"Falha ao atualizar veiculo {payload.get('frota')}: {response.status_code} {response.text}")
        return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Migra a frota do SQLite local para a nuvem.")
    parser.add_argument("--source-db", default=str(DEFAULT_DB_PATH), help="Caminho do SQLite local.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="URL base da API na nuvem.")
    parser.add_argument("--login", default=DEFAULT_LOGIN, help="Login de admin na nuvem.")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Senha do admin na nuvem.")
    args = parser.parse_args()

    banner()
    db_path = Path(args.source_db)
    print("[1/4] Lendo banco local...")
    print(f"Banco: {db_path}")

    local_rows = fetch_local_vehicles(db_path)
    print(f"Veiculos locais encontrados: {len(local_rows)}")
    if not local_rows:
        print("Nada para migrar.")
        return 0

    print()
    print("[2/4] Conectando na nuvem...")
    cloud = CloudClient(args.api_url, args.login, args.password)
    auth_payload = cloud.authenticate()
    user = auth_payload["user"]
    print(f"Logado como: {user['login']} ({user['tipo']})")

    cloud_rows = cloud.list_vehicles()
    cloud_by_frota = {str(row.get("frota") or "").upper(): row for row in cloud_rows if row.get("frota")}
    cloud_by_placa = {str(row.get("placa") or "").upper(): row for row in cloud_rows if row.get("placa")}
    print(f"Veiculos atuais na nuvem: {len(cloud_rows)}")
    print()

    print("[3/4] Migrando veiculos...")
    created = 0
    updated = 0
    skipped = 0
    for index, row in enumerate(local_rows, start=1):
        payload = build_payload(row)
        frota = payload.get("frota")
        if not frota:
            skipped += 1
            continue

        existing = cloud_by_frota.get(frota)
        if not existing:
            placa_key = str(payload.get("placa") or "").upper()
            existing = cloud_by_placa.get(placa_key)
        prefix = f"[{index}/{len(local_rows)}] {frota:<12}"
        try:
            if existing:
                cloud.update_vehicle(int(existing["id"]), payload)
                updated += 1
                print(f"{prefix} atualizado")
            else:
                try:
                    cloud.create_vehicle(payload)
                    created += 1
                    print(f"{prefix} criado")
                except RuntimeError as exc:
                    message = str(exc)
                    if "409" not in message:
                        raise
                    cloud_rows = cloud.list_vehicles()
                    cloud_by_frota = {str(row.get("frota") or "").upper(): row for row in cloud_rows if row.get("frota")}
                    cloud_by_placa = {str(row.get("placa") or "").upper(): row for row in cloud_rows if row.get("placa")}
                    existing = cloud_by_frota.get(frota)
                    if not existing:
                        existing = cloud_by_placa.get(str(payload.get("placa") or "").upper())
                    if existing:
                        cloud.update_vehicle(int(existing["id"]), payload)
                        updated += 1
                        print(f"{prefix} atualizado (conflito resolvido)")
                    else:
                        raise
        except Exception as exc:
            print(f"{prefix} ERRO: {exc}")
            raise

    print()
    print("[4/4] Finalizando...")
    print(f"Criados: {created}")
    print(f"Atualizados: {updated}")
    print(f"Ignorados: {skipped}")
    print("Migracao concluida com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

