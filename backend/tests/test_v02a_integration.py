"""
v02-A 통합 테스트 — Dataset CRUD (생성·삭제)

TC01: POST /api/datasets → 새 dataset 생성 (201)
TC02: 생성 후 GET /api/datasets → 목록에 신규 dataset 포함
TC03: 생성 후 GET /api/health → 200 (dataset과 무관하게 정상)
TC04: 중복 이름 dataset 생성 → 409 Conflict
TC05: dataset 이름 빈 문자열 → 422
TC06: dataset 이름에 특수문자 포함 → 422
TC07: DELETE /api/datasets/{name} → 204
TC08: 삭제 후 GET /api/datasets → 목록에서 제거됨
TC09: 존재하지 않는 dataset 삭제 → 404
TC10: 기본 'ontology' dataset은 삭제 불가 (보호) → 400 또는 403

실행:
  cd backend && pytest tests/test_v02a_integration.py -v
"""

import sys
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from main import app

TEST_DS = "v02a-test-dataset"


@pytest_asyncio.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True, scope="module")
async def cleanup(client):
    """테스트 전후 테스트 dataset 정리."""
    # before
    await client.delete(f"/api/datasets/{TEST_DS}")
    yield
    # after
    await client.delete(f"/api/datasets/{TEST_DS}")


# ── TC01 — 새 dataset 생성 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_create_dataset(client):
    """POST /api/datasets → 201, dataset 이름 반환."""
    resp = await client.post("/api/datasets", json={"name": TEST_DS})
    assert resp.status_code == 201, resp.text
    assert resp.json()["name"] == TEST_DS


# ── TC02 — 생성 후 목록 포함 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_created_dataset_in_list(client):
    """생성된 dataset이 GET /api/datasets 목록에 포함된다."""
    resp = await client.get("/api/datasets")
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()["datasets"]]
    assert TEST_DS in names, f"{TEST_DS} not in {names}"


# ── TC03 — health는 dataset과 무관 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_health_unaffected(client):
    """/api/health 는 dataset 상태와 무관하게 200을 반환한다."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200


# ── TC04 — 중복 이름 409 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_duplicate_name_conflict(client):
    """이미 존재하는 dataset 이름으로 생성 시 409를 반환한다."""
    resp = await client.post("/api/datasets", json={"name": TEST_DS})
    assert resp.status_code == 409, resp.text


# ── TC05 — 빈 이름 422 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc05_empty_name_422(client):
    """빈 dataset 이름은 422를 반환한다."""
    resp = await client.post("/api/datasets", json={"name": ""})
    assert resp.status_code == 422, resp.text


# ── TC06 — 특수문자 이름 422 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_special_chars_422(client):
    """dataset 이름에 특수문자(/, ?, #)가 포함되면 422를 반환한다."""
    resp = await client.post("/api/datasets", json={"name": "my/dataset"})
    assert resp.status_code == 422, resp.text


# ── TC07 — dataset 삭제 204 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc07_delete_dataset(client):
    """DELETE /api/datasets/{name} → 204."""
    resp = await client.delete(f"/api/datasets/{TEST_DS}")
    assert resp.status_code == 204, resp.text


# ── TC08 — 삭제 후 목록에서 제거 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_deleted_dataset_not_in_list(client):
    """삭제 후 dataset이 GET /api/datasets 목록에 없다."""
    resp = await client.get("/api/datasets")
    names = [d["name"] for d in resp.json()["datasets"]]
    assert TEST_DS not in names, f"{TEST_DS} still in {names}"


# ── TC09 — 존재하지 않는 dataset 삭제 → 404 ──────────────────────────────

@pytest.mark.asyncio
async def test_tc09_delete_nonexistent_404(client):
    """존재하지 않는 dataset 삭제 시 404를 반환한다."""
    resp = await client.delete("/api/datasets/does-not-exist-xyz")
    assert resp.status_code == 404, resp.text


# ── TC10 — 'ontology' dataset 삭제 보호 ──────────────────────────────────

@pytest.mark.asyncio
async def test_tc10_protected_dataset_not_deletable(client):
    """기본 'ontology' dataset은 삭제할 수 없다 (400 또는 403)."""
    resp = await client.delete("/api/datasets/ontology")
    assert resp.status_code in (400, 403), f"Expected 400/403, got {resp.status_code}"
