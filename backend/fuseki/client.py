"""Fuseki Admin REST API 클라이언트 (dataset 관리)."""

import httpx
import config_state


def _admin() -> str:
    return f"{config_state.base_url()}/$"


async def ping(url: str | None = None) -> bool:
    """Fuseki 서버 생존 확인.

    url이 주어지면 해당 URL로, 없으면 현재 설정 URL로 확인한다.
    """
    base = url if url is not None else config_state.base_url()
    user, pw = config_state.auth()
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{base}/$/ping", auth=(user, pw))
            return resp.status_code == 200
        except Exception:
            return False


async def list_datasets() -> list[dict]:
    """
    Fuseki Admin API에서 dataset 목록을 가져온다.

    반환 예시:
        [{"name": "myds", "state": "active"}, ...]
    """
    user, pw = config_state.auth()
    async with httpx.AsyncClient(timeout=10.0, auth=(user, pw)) as client:
        resp = await client.get(f"{_admin()}/datasets")
        resp.raise_for_status()
        raw: list[dict] = resp.json().get("datasets", [])

    return [
        {
            "name": entry["ds.name"].lstrip("/"),
            "state": "active" if entry.get("ds.state") else "inactive",
        }
        for entry in raw
    ]


async def create_dataset(name: str, ds_type: str = "tdb2") -> None:
    """Fuseki Admin API로 새 dataset을 생성한다."""
    user, pw = config_state.auth()
    async with httpx.AsyncClient(timeout=15.0, auth=(user, pw)) as client:
        resp = await client.post(
            f"{_admin()}/datasets",
            data={"dbName": name, "dbType": ds_type},
        )
        resp.raise_for_status()


async def delete_dataset(name: str) -> None:
    """Fuseki Admin API로 dataset을 삭제한다."""
    user, pw = config_state.auth()
    async with httpx.AsyncClient(timeout=15.0, auth=(user, pw)) as client:
        resp = await client.delete(f"{_admin()}/datasets/{name}")
        resp.raise_for_status()
