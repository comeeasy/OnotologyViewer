"""Fuseki 연결 설정 동적 변경 라우터 (v02-J)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

import config_state
from fuseki.client import ping

router = APIRouter(prefix="/api/config", tags=["config"])


# ── Models ─────────────────────────────────────────────────────────────────

class FusekiConfig(BaseModel):
    fuseki_base_url:   str
    fuseki_admin_user: str | None = None
    fuseki_admin_password: str | None = None  # None → 변경 안 함

    @field_validator("fuseki_base_url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("fuseki_base_url은 빈 문자열일 수 없습니다.")
        if not v.startswith("http://") and not v.startswith("https://"):
            raise ValueError("fuseki_base_url은 http:// 또는 https://로 시작해야 합니다.")
        return v.rstrip("/")  # 후행 슬래시 제거


class FusekiConfigResponse(BaseModel):
    fuseki_base_url:      str
    fuseki_admin_user:    str
    fuseki_admin_password: str  # 항상 마스킹


class TestBody(BaseModel):
    fuseki_base_url: str

    @field_validator("fuseki_base_url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("http://") and not v.startswith("https://"):
            raise ValueError("fuseki_base_url은 http:// 또는 https://로 시작해야 합니다.")
        return v.rstrip("/")


class TestResponse(BaseModel):
    reachable: bool
    url:       str


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/fuseki", response_model=FusekiConfigResponse)
def get_fuseki_config():
    """현재 Fuseki 연결 설정을 반환한다. password는 *** 로 마스킹."""
    state = config_state.get()
    return FusekiConfigResponse(
        fuseki_base_url=state["fuseki_base_url"],
        fuseki_admin_user=state["fuseki_admin_user"],
        fuseki_admin_password="***",
    )


@router.patch("/fuseki", response_model=FusekiConfigResponse)
async def patch_fuseki_config(body: FusekiConfig):
    """Fuseki 연결 설정을 변경한다.

    - 변경 전 현재 상태를 백업한다.
    - 새 URL로 헬스체크를 실행한다.
    - 실패 시 이전 상태로 롤백하고 503을 반환한다.
    """
    # 현재 상태 백업
    before = config_state.get()

    # 새 설정 적용
    config_state.set(
        url=body.fuseki_base_url,
        user=body.fuseki_admin_user,
        password=body.fuseki_admin_password,
    )

    # 헬스체크
    ok = await ping()
    if not ok:
        # 롤백
        config_state.set(
            url=before["fuseki_base_url"],
            user=before["fuseki_admin_user"],
            password=before["fuseki_admin_password"],
        )
        raise HTTPException(
            503,
            f"Fuseki 서버({body.fuseki_base_url})에 연결할 수 없습니다. 설정이 롤백되었습니다.",
        )

    state = config_state.get()
    return FusekiConfigResponse(
        fuseki_base_url=state["fuseki_base_url"],
        fuseki_admin_user=state["fuseki_admin_user"],
        fuseki_admin_password="***",
    )


@router.post("/fuseki/test", response_model=TestResponse)
async def test_fuseki_connection(body: TestBody):
    """URL을 저장하지 않고 연결 가능 여부만 확인한다 (dry-run)."""
    reachable = await ping(url=body.fuseki_base_url)
    return TestResponse(reachable=reachable, url=body.fuseki_base_url)
