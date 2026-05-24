"""v03-B Rules Router — SPARQL 기반 추론 규칙 엔드포인트."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from urllib.parse import unquote

from services import rules as rules_svc

router = APIRouter(prefix="/api/rules", tags=["rules"])


# ──────────────────────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────────────────────

class CreateRuleBody(BaseModel):
    dataset: str
    graph: str
    label: str
    condition: str
    consequence: str
    description: str | None = None


class UpdateRuleBody(BaseModel):
    dataset: str
    graph: str
    label: str | None = None
    description: str | None = None
    condition: str | None = None
    consequence: str | None = None


class ApplyBody(BaseModel):
    dataset: str
    graph: str


class RuleSummary(BaseModel):
    rule_iri: str
    label: str | None = None
    description: str | None = None


class RuleDetail(BaseModel):
    rule_iri: str
    label: str | None = None
    condition: str
    consequence: str
    description: str | None = None


class CreateRuleResponse(BaseModel):
    rule_iri: str
    label: str | None = None
    condition: str
    consequence: str
    description: str | None = None


class InferredTriple(BaseModel):
    s: str
    p: str
    o: str


class ApplyResponse(BaseModel):
    inferred_triples: list[InferredTriple]


class MaterializeResponse(BaseModel):
    materialized_graph: str
    materialized_count: int


class DeleteResponse(BaseModel):
    deleted: str


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[RuleSummary])
def get_rules(
    dataset: str = Query(...),
    graph: str = Query(...),
):
    """Rules 목록 조회."""
    return rules_svc.list_rules(dataset, graph)


@router.post("", response_model=CreateRuleResponse, status_code=201)
def post_rule(body: CreateRuleBody):
    """Rule 생성."""
    try:
        return rules_svc.create_rule(
            body.dataset,
            body.graph,
            body.label,
            body.condition,
            body.consequence,
            body.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ── /{iri:path}/apply, /{iri:path}/materialize 를 /{iri:path} catch-all 전에 등록 ──

@router.post("/{iri:path}/apply", response_model=ApplyResponse)
def post_apply_rule(iri: str, body: ApplyBody):
    """Rule 적용 미리보기."""
    rule_iri = unquote(iri)
    if rule_iri.endswith("/apply"):
        rule_iri = rule_iri[: -len("/apply")]
    try:
        return rules_svc.apply_rule(body.dataset, body.graph, rule_iri)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/{iri:path}/materialize", response_model=MaterializeResponse)
def post_materialize_rule(iri: str, body: ApplyBody):
    """Rule 결과 저장."""
    rule_iri = unquote(iri)
    if rule_iri.endswith("/materialize"):
        rule_iri = rule_iri[: -len("/materialize")]
    try:
        return rules_svc.materialize_rule(body.dataset, body.graph, rule_iri)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{iri:path}", response_model=RuleDetail)
def get_rule(
    iri: str,
    dataset: str = Query(...),
    graph: str = Query(...),
):
    """Rule 상세 조회."""
    rule_iri = unquote(iri)
    try:
        return rules_svc.get_rule(dataset, graph, rule_iri)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{iri:path}", response_model=RuleDetail)
def patch_rule(iri: str, body: UpdateRuleBody):
    """Rule 수정."""
    rule_iri = unquote(iri)
    try:
        return rules_svc.update_rule(
            body.dataset,
            body.graph,
            rule_iri,
            body.label,
            body.description,
            body.condition,
            body.consequence,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{iri:path}", response_model=DeleteResponse)
def delete_rule(
    iri: str,
    dataset: str = Query(...),
    graph: str = Query(...),
):
    """Rule 삭제."""
    rule_iri = unquote(iri)
    try:
        return rules_svc.delete_rule(dataset, graph, rule_iri)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
