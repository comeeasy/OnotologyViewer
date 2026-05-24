"""v02-G Reasoning — OWL/RDFS 추론 실행 및 Materialization."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from services.reasoning import (
    run_reasoning, materialize, check_consistency,
    SUPPORTED_REASONERS,
)

router = APIRouter(prefix="/api/reasoning", tags=["reasoning"])


# ── Models ────────────────────────────────────────────────────────────────

class RunReasoningBody(BaseModel):
    dataset:  str
    graph:    str
    reasoner: str = "RDFS"

    @field_validator("reasoner")
    @classmethod
    def must_be_supported(cls, v: str) -> str:
        if v not in SUPPORTED_REASONERS:
            raise ValueError(
                f"지원하지 않는 reasoner: {v!r}. 지원: {list(SUPPORTED_REASONERS)}"
            )
        return v


class InferredTriple(BaseModel):
    s: str
    p: str
    o: str


class RunReasoningResponse(BaseModel):
    inferred_triples: list[InferredTriple]
    total_inferred:   int
    truncated:        bool


class MaterializeBody(BaseModel):
    dataset:          str
    graph:            str
    inferred_triples: list[InferredTriple]


class MaterializeResponse(BaseModel):
    inferred_graph:    str
    materialized_count: int


class ConsistencyBody(BaseModel):
    dataset: str
    graph:   str


class ConsistencyResponse(BaseModel):
    consistent: bool
    details:    str | list[str]


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/run", response_model=RunReasoningResponse)
def post_run_reasoning(body: RunReasoningBody):
    """
    Named Graph에서 추론을 실행하고 새로 추론된 트리플 목록을 반환한다.
    (저장하지 않음 — 미리보기 용도)
    """
    try:
        result = run_reasoning(body.dataset, body.graph, body.reasoner)
        return RunReasoningResponse(
            inferred_triples=[InferredTriple(**t) for t in result["inferred_triples"]],
            total_inferred=result["total_inferred"],
            truncated=result["truncated"],
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/materialize", response_model=MaterializeResponse)
def post_materialize(body: MaterializeBody):
    """추론된 트리플을 {graph}/inferred Named Graph에 저장한다."""
    try:
        result = materialize(
            body.dataset, body.graph,
            [t.model_dump() for t in body.inferred_triples],
        )
        return MaterializeResponse(**result)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/consistency", response_model=ConsistencyResponse)
def post_consistency_check(body: ConsistencyBody):
    """Named Graph의 OWL 일관성을 검사한다."""
    try:
        result = check_consistency(body.dataset, body.graph)
        return ConsistencyResponse(**result)
    except Exception as e:
        raise HTTPException(500, str(e))
