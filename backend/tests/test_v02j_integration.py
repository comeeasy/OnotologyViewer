"""
v02-J 통합 테스트 — Fuseki Endpoint 동적 설정

테스트 시나리오:
  TC01: GET /api/config/fuseki → 현재 설정 반환 (password 마스킹)
  TC02: PATCH /api/config/fuseki → URL 변경 후 GET 반영 확인
  TC03: PATCH 후 /api/health → 변경된 endpoint로 헬스체크 성공
  TC04: PATCH → 잘못된 URL → health 실패 → 422/503 반환
  TC05: PATCH → 잘못된 URL → 롤백 → 원래 URL로 복원
  TC06: PATCH → user/password 변경 → 인증 반영
  TC07: PATCH → 빈 URL → 422 검증 에러
  TC08: PATCH → http 미시작 URL → 422 검증 에러
  TC09: PATCH 후 SPARQL 쿼리가 새 endpoint로 실행되는지 확인 (dataset 목록 정상)
  TC10: POST /api/config/fuseki/test → URL 유효성 미리 검사 (dry-run)

실행:
  cd backend && pytest tests/test_v02j_integration.py -v
"""

import sys
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from main import app
import config_state  # 구현할 mutable config module

VALID_URL = "http://localhost:3030"
INVALID_URL = "http://localhost:9999"   # 존재하지 않는 포트


# ────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(autouse=True)
async def restore_config():
    """각 테스트 후 설정을 원래 값으로 복원."""
    original = config_state.get()
    yield
    config_state.set(
        url=original["fuseki_base_url"],
        user=original["fuseki_admin_user"],
        password=original["fuseki_admin_password"],
    )


# ────────────────────────────────────────────────
# TC01 — 현재 설정 조회 (password 마스킹)
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_get_config(client):
    """GET /api/config/fuseki 는 현재 URL·user·masked password를 반환한다."""
    resp = await client.get("/api/config/fuseki")
    assert resp.status_code == 200
    body = resp.json()
    assert "fuseki_base_url" in body
    assert "fuseki_admin_user" in body
    assert body["fuseki_base_url"].startswith("http")
    # password는 마스킹되어야 한다
    assert "fuseki_admin_password" not in body or body.get("fuseki_admin_password") == "***"


# ────────────────────────────────────────────────
# TC02 — PATCH 후 GET에 변경 반영
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_patch_url_reflected_in_get(client):
    """PATCH로 URL을 바꾸면 GET에서 새 URL이 보여야 한다."""
    new_url = VALID_URL  # 유효한 URL로만 변경 (같은 값이어도 OK)
    resp = await client.patch("/api/config/fuseki", json={"fuseki_base_url": new_url})
    assert resp.status_code == 200

    resp2 = await client.get("/api/config/fuseki")
    assert resp2.json()["fuseki_base_url"] == new_url


# ────────────────────────────────────────────────
# TC03 — 유효한 URL로 PATCH 후 health 정상
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_health_ok_after_valid_patch(client):
    """유효한 Fuseki URL로 PATCH 후 /api/health 가 200을 반환한다."""
    resp = await client.patch("/api/config/fuseki", json={"fuseki_base_url": VALID_URL})
    assert resp.status_code == 200

    health = await client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"


# ────────────────────────────────────────────────
# TC04 — 잘못된 URL로 PATCH → 연결 실패 응답
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_patch_invalid_url_returns_error(client):
    """존재하지 않는 포트로 PATCH하면 422 또는 503을 반환한다."""
    resp = await client.patch("/api/config/fuseki", json={"fuseki_base_url": INVALID_URL})
    assert resp.status_code in (422, 503), f"Expected 422 or 503, got {resp.status_code}"


# ────────────────────────────────────────────────
# TC05 — 잘못된 URL PATCH 후 이전 URL로 롤백
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc05_rollback_on_invalid_url(client):
    """잘못된 URL PATCH 실패 시 이전 URL이 유지된다."""
    before = (await client.get("/api/config/fuseki")).json()["fuseki_base_url"]

    await client.patch("/api/config/fuseki", json={"fuseki_base_url": INVALID_URL})

    after = (await client.get("/api/config/fuseki")).json()["fuseki_base_url"]
    assert after == before, f"URL이 롤백되지 않음: {before!r} → {after!r}"


# ────────────────────────────────────────────────
# TC06 — user/password 변경
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_patch_user_password(client):
    """user와 password를 변경하면 GET에 user가 반영된다."""
    resp = await client.patch("/api/config/fuseki", json={
        "fuseki_base_url": VALID_URL,
        "fuseki_admin_user": "admin",
        "fuseki_admin_password": "admin",
    })
    assert resp.status_code == 200

    body = (await client.get("/api/config/fuseki")).json()
    assert body["fuseki_admin_user"] == "admin"


# ────────────────────────────────────────────────
# TC07 — 빈 URL → 422
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc07_empty_url_rejected(client):
    """빈 문자열 URL은 422 Unprocessable Entity를 반환한다."""
    resp = await client.patch("/api/config/fuseki", json={"fuseki_base_url": ""})
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"


# ────────────────────────────────────────────────
# TC08 — http 미시작 URL → 422
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_non_http_url_rejected(client):
    """http/https로 시작하지 않는 URL은 422를 반환한다."""
    resp = await client.patch("/api/config/fuseki", json={"fuseki_base_url": "ftp://localhost:3030"})
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"


# ────────────────────────────────────────────────
# TC09 — PATCH 후 SPARQL 동작 확인 (dataset 목록)
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc09_sparql_works_after_patch(client):
    """유효한 URL로 PATCH 후 dataset 목록 API가 정상 동작한다."""
    await client.patch("/api/config/fuseki", json={"fuseki_base_url": VALID_URL})

    resp = await client.get("/api/datasets")
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()["datasets"]]
    assert "ontology" in names, f"'ontology' not in {names}"


# ────────────────────────────────────────────────
# TC10 — POST /api/config/fuseki/test (dry-run 연결 검사)
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc10_dry_run_connection_test(client):
    """POST /api/config/fuseki/test 는 URL을 저장하지 않고 연결만 확인한다."""
    # 유효한 URL → 200
    resp_ok = await client.post("/api/config/fuseki/test", json={"fuseki_base_url": VALID_URL})
    assert resp_ok.status_code == 200
    assert resp_ok.json()["reachable"] is True

    # 잘못된 URL → 200 + reachable=False (예외 아님, 결과 반환)
    resp_fail = await client.post("/api/config/fuseki/test", json={"fuseki_base_url": INVALID_URL})
    assert resp_fail.status_code == 200
    assert resp_fail.json()["reachable"] is False

    # 저장되지 않았는지 확인 (현재 URL은 INVALID_URL이 아니어야 함)
    current = (await client.get("/api/config/fuseki")).json()["fuseki_base_url"]
    assert current != INVALID_URL, "dry-run이 URL을 변경함"
