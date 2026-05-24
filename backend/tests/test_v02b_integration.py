"""
v02-B 통합 테스트 — Named Graph CRUD 고도화

테스트 시나리오:
  TC01: POST /api/datasets/{ds}/graphs → 생성 후 label triple 존재 확인
  TC02: PATCH /api/datasets/{ds}/graphs → label 수정 후 GET에 반영
  TC03: PATCH /api/datasets/{ds}/graphs → comment 수정 후 GET에 반영
  TC04: PATCH → label + comment 동시 수정
  TC05: GET /api/datasets/{ds}/graphs/{graph_enc} → label·comment·triple_count 반환
  TC06: triple_count — 트리플 추가 후 count 증가 확인
  TC07: triple_count — 초기 생성 직후 count = 1 (owl:Ontology 선언 트리플)
  TC08: PATCH → 존재하지 않는 graph → 404 반환
  TC09: GET triple_count — 존재하지 않는 graph → 404
  TC10: label 빈 문자열로 PATCH → 422 검증 에러

실행:
  cd backend && pytest tests/test_v02b_integration.py -v
"""

import sys
from urllib.parse import quote

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from fuseki.sparql import update as sparql_update
from main import app

DS = "ontology"
TEST_GRAPH = "http://test.example.org/graph/v02b-test"
TEST_GRAPH2 = "http://test.example.org/graph/v02b-test2"

_DROP = lambda g: f"DROP SILENT GRAPH <{g}>"

def genc(iri: str) -> str:
    return quote(iri, safe="")


@pytest_asyncio.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True, scope="module")
def clean():
    sparql_update(DS, _DROP(TEST_GRAPH))
    sparql_update(DS, _DROP(TEST_GRAPH2))
    yield
    sparql_update(DS, _DROP(TEST_GRAPH))
    sparql_update(DS, _DROP(TEST_GRAPH2))


# ── TC01 — 생성 후 label triple 존재 ───────────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_create_graph_with_label(client):
    """Named Graph을 label과 함께 생성하면 graph 목록에 등장한다."""
    resp = await client.post(f"/api/datasets/{DS}/graphs", json={
        "graph": TEST_GRAPH, "label": "v02-B 테스트 그래프",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["graph"] == TEST_GRAPH

    graphs = (await client.get(f"/api/datasets/{DS}/graphs")).json()["graphs"]
    assert TEST_GRAPH in graphs


# ── TC02 — label 수정 ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_patch_label(client):
    """PATCH로 label을 변경하면 graph 상세에 새 label이 반영된다."""
    new_label = "수정된 그래프 이름"
    resp = await client.patch(f"/api/datasets/{DS}/graphs", json={
        "graph": TEST_GRAPH, "label": new_label,
    })
    assert resp.status_code == 200, resp.text

    detail = (await client.get(
        f"/api/datasets/{DS}/graphs/detail",
        params={"graph": TEST_GRAPH},
    )).json()
    assert detail["label"] == new_label


# ── TC03 — comment 수정 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_patch_comment(client):
    """PATCH로 comment를 추가/변경하면 graph 상세에 반영된다."""
    resp = await client.patch(f"/api/datasets/{DS}/graphs", json={
        "graph": TEST_GRAPH, "comment": "이것은 테스트 그래프입니다.",
    })
    assert resp.status_code == 200

    detail = (await client.get(
        f"/api/datasets/{DS}/graphs/detail",
        params={"graph": TEST_GRAPH},
    )).json()
    assert detail["comment"] == "이것은 테스트 그래프입니다."


# ── TC04 — label + comment 동시 수정 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_patch_label_and_comment(client):
    """label과 comment를 동시에 수정할 수 있다."""
    resp = await client.patch(f"/api/datasets/{DS}/graphs", json={
        "graph": TEST_GRAPH,
        "label": "최종 그래프",
        "comment": "최종 설명",
    })
    assert resp.status_code == 200

    detail = (await client.get(
        f"/api/datasets/{DS}/graphs/detail",
        params={"graph": TEST_GRAPH},
    )).json()
    assert detail["label"] == "최종 그래프"
    assert detail["comment"] == "최종 설명"


# ── TC05 — GET detail → label·comment·triple_count ────────────────────────

@pytest.mark.asyncio
async def test_tc05_get_graph_detail_fields(client):
    """GET /api/datasets/{ds}/graphs/detail 은 label·comment·triple_count를 포함한다."""
    detail = (await client.get(
        f"/api/datasets/{DS}/graphs/detail",
        params={"graph": TEST_GRAPH},
    )).json()
    assert "label" in detail
    assert "comment" in detail
    assert "triple_count" in detail
    assert isinstance(detail["triple_count"], int)
    assert detail["triple_count"] >= 1


# ── TC06 — triple_count 증가 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_triple_count_increases(client):
    """트리플을 추가하면 triple_count가 늘어난다."""
    before = (await client.get(
        f"/api/datasets/{DS}/graphs/detail",
        params={"graph": TEST_GRAPH},
    )).json()["triple_count"]

    # 트리플 2개 추가
    sparql_update(DS, f"""
    INSERT DATA {{
      GRAPH <{TEST_GRAPH}> {{
        <http://test.example.org/A> <http://test.example.org/p> "v1" .
        <http://test.example.org/B> <http://test.example.org/p> "v2" .
      }}
    }}
    """)

    after = (await client.get(
        f"/api/datasets/{DS}/graphs/detail",
        params={"graph": TEST_GRAPH},
    )).json()["triple_count"]

    assert after == before + 2, f"Expected {before + 2}, got {after}"


# ── TC07 — 초기 triple_count = 1 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc07_initial_triple_count(client):
    """label 없이 생성한 Named Graph의 triple_count는 1이다 (owl:Ontology 선언 트리플만)."""
    resp = await client.post(f"/api/datasets/{DS}/graphs", json={
        "graph": TEST_GRAPH2,  # label 미포함 → owl:Ontology 트리플 1개만
    })
    assert resp.status_code == 201

    detail = (await client.get(
        f"/api/datasets/{DS}/graphs/detail",
        params={"graph": TEST_GRAPH2},
    )).json()
    assert detail["triple_count"] == 1, f"Expected 1, got {detail['triple_count']}"


# ── TC08 — 존재하지 않는 graph PATCH → 404 ────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_patch_nonexistent_graph_404(client):
    """존재하지 않는 graph에 PATCH하면 404를 반환한다."""
    resp = await client.patch(f"/api/datasets/{DS}/graphs", json={
        "graph": "http://nonexistent.example.org/graph/xyz",
        "label": "없는 그래프",
    })
    assert resp.status_code == 404, resp.text


# ── TC09 — 존재하지 않는 graph detail → 404 ───────────────────────────────

@pytest.mark.asyncio
async def test_tc09_get_detail_nonexistent_404(client):
    """존재하지 않는 graph의 detail을 요청하면 404를 반환한다."""
    resp = await client.get(
        f"/api/datasets/{DS}/graphs/detail",
        params={"graph": "http://nonexistent.example.org/graph/none"},
    )
    assert resp.status_code == 404, resp.text


# ── TC10 — 빈 label PATCH → 422 ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc10_empty_label_rejected(client):
    """label에 빈 문자열을 보내면 422를 반환한다."""
    resp = await client.patch(f"/api/datasets/{DS}/graphs", json={
        "graph": TEST_GRAPH, "label": "",
    })
    assert resp.status_code == 422, resp.text
