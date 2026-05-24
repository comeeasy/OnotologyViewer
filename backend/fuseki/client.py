"""Fuseki Admin REST API 클라이언트 (dataset 관리)."""

import httpx
from config import settings

_ADMIN = f"{settings.fuseki_base_url}/$"
_AUTH = (settings.fuseki_admin_user, settings.fuseki_admin_password)


async def ping() -> bool:
    """Fuseki 서버 생존 확인."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{_ADMIN}/ping")
            return resp.status_code == 200
        except Exception:
            return False


async def list_datasets() -> list[dict]:
    """
    Fuseki Admin API에서 dataset 목록을 가져온다.

    반환 예시:
        [{"name": "myds", "state": "active"}, ...]
    """
    async with httpx.AsyncClient(timeout=10.0, auth=_AUTH) as client:
        resp = await client.get(f"{_ADMIN}/datasets")
        resp.raise_for_status()
        raw: list[dict] = resp.json().get("datasets", [])

    return [
        {
            "name": entry["ds.name"].lstrip("/"),
            "state": "active" if entry.get("ds.state") else "inactive",
        }
        for entry in raw
    ]
