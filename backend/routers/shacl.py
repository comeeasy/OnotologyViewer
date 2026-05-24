"""v03-A SHACL Router — Shape 관리 + 검증 엔드포인트."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator
from urllib.parse import unquote

from services import shacl as shacl_svc

router = APIRouter(prefix="/api/shacl", tags=["shacl"])


# ──────────────────────────────────────────────────────────────────────────────
# Request / Response Models
# ──────────────────────────────────────────────────────────────────────────────

class CreateNodeShapeBody(BaseModel):
    dataset: str
    graph: str
    target_class: str
    label: str | None = None

    @field_validator("target_class")
    @classmethod
    def must_be_http(cls, v: str) -> str:
        if not v.startswith("http"):
            raise ValueError("target_class must be an IRI starting with 'http'")
        return v


class AddPropertyShapeBody(BaseModel):
    dataset: str
    graph: str
    path: str
    min_count: int | None = None
    max_count: int | None = None
    datatype: str | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    label: str | None = None

    @field_validator("path")
    @classmethod
    def path_must_be_http(cls, v: str) -> str:
        if not v.startswith("http"):
            raise ValueError("path must be an IRI starting with 'http'")
        return v


class ValidateBody(BaseModel):
    dataset: str
    graph: str


class ValidateIndividualBody(BaseModel):
    dataset: str
    graph: str
    individual_iri: str


class NodeShapeSummary(BaseModel):
    shape_iri: str
    target_class: str
    label: str | None = None


class PropertyShapeItem(BaseModel):
    prop_shape_iri: str
    path: str
    min_count: int | None = None
    max_count: int | None = None
    datatype: str | None = None
    label: str | None = None


class NodeShapeDetail(BaseModel):
    shape_iri: str
    target_class: str
    label: str | None = None
    property_shapes: list[PropertyShapeItem] = []


class CreateShapeResponse(BaseModel):
    shape_iri: str
    target_class: str
    label: str | None = None


class AddPropShapeResponse(BaseModel):
    prop_shape_iri: str
    path: str


class DeleteResponse(BaseModel):
    deleted: str


class ViolationItem(BaseModel):
    focus_node: str | None = None
    message: str | None = None
    result_path: str | None = None
    source_shape: str | None = None
    severity: str | None = None


class ValidationResponse(BaseModel):
    conforms: bool
    violations: list[ViolationItem] = []


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/shapes", response_model=list[NodeShapeSummary])
def get_shapes(
    dataset: str = Query(...),
    graph: str = Query(...),
):
    """NodeShape 목록 조회."""
    return shacl_svc.list_shapes(dataset, graph)


@router.post("/shapes", response_model=CreateShapeResponse, status_code=201)
def post_shape(body: CreateNodeShapeBody):
    """NodeShape 생성."""
    return shacl_svc.create_node_shape(
        body.dataset,
        body.graph,
        body.target_class,
        body.label,
    )


# ── 더 구체적인 경로를 먼저 등록 (/{iri:path} catch-all 전에) ─────────────

@router.post("/validate/individual", response_model=ValidationResponse)
def post_validate_individual(body: ValidateIndividualBody):
    """Individual 단위 SHACL 검증."""
    return shacl_svc.validate_individual(body.dataset, body.graph, body.individual_iri)


@router.post("/validate", response_model=ValidationResponse)
def post_validate(body: ValidateBody):
    """그래프 전체 SHACL 검증."""
    return shacl_svc.validate_graph(body.dataset, body.graph)


@router.get("/shapes/{iri:path}", response_model=NodeShapeDetail)
def get_shape_detail(
    iri: str,
    dataset: str = Query(...),
    graph: str = Query(...),
):
    """NodeShape 상세 조회."""
    shape_iri = unquote(iri)
    try:
        return shacl_svc.get_shape_detail(dataset, graph, shape_iri)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/shapes/{iri:path}/properties", response_model=AddPropShapeResponse, status_code=201)
def post_property_shape(iri: str, body: AddPropertyShapeBody):
    """PropertyShape 추가."""
    shape_iri = unquote(iri)
    if shape_iri.endswith("/properties"):
        shape_iri = shape_iri[: -len("/properties")]
    try:
        return shacl_svc.add_property_shape(
            body.dataset,
            body.graph,
            shape_iri,
            body.path,
            body.min_count,
            body.max_count,
            body.datatype,
            body.min_length,
            body.max_length,
            body.pattern,
            body.label,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/shapes/{shape_iri:path}/properties/{prop_iri:path}",
    response_model=DeleteResponse,
)
def delete_property_shape(
    shape_iri: str,
    prop_iri: str,
    dataset: str = Query(...),
    graph: str = Query(...),
):
    """PropertyShape 삭제."""
    shape_iri = unquote(shape_iri)
    prop_iri = unquote(prop_iri)
    try:
        return shacl_svc.delete_property_shape(dataset, graph, shape_iri, prop_iri)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/shapes/{iri:path}", response_model=DeleteResponse)
def delete_shape(
    iri: str,
    dataset: str = Query(...),
    graph: str = Query(...),
):
    """NodeShape 삭제 (PropertyShape 연쇄 삭제)."""
    shape_iri = unquote(iri)
    try:
        return shacl_svc.delete_node_shape(dataset, graph, shape_iri)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
