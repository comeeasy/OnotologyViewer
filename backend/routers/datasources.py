"""v03-C Datasource Router — Datasource 매핑 엔드포인트."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator
from urllib.parse import unquote

from services import datasources as ds_svc

router = APIRouter(prefix="/api/datasources", tags=["datasources"])

SUPPORTED_TYPES = {"csv", "json", "rest", "sparql"}


# ──────────────────────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────────────────────

class CreateDatasourceBody(BaseModel):
    dataset: str
    graph: str
    label: str
    ds_type: str
    connection_info: str
    description: str | None = None

    @field_validator("ds_type")
    @classmethod
    def must_be_valid_type(cls, v: str) -> str:
        if v not in SUPPORTED_TYPES:
            raise ValueError(f"ds_type must be one of {sorted(SUPPORTED_TYPES)}")
        return v


class UpdateDatasourceBody(BaseModel):
    dataset: str
    graph: str
    label: str | None = None
    ds_type: str | None = None
    connection_info: str | None = None
    description: str | None = None

    @field_validator("ds_type")
    @classmethod
    def must_be_valid_type(cls, v: str | None) -> str | None:
        if v is not None and v not in SUPPORTED_TYPES:
            raise ValueError(f"ds_type must be one of {sorted(SUPPORTED_TYPES)}")
        return v


class AddClassMappingBody(BaseModel):
    dataset: str
    graph: str
    target_class: str
    identifier_field: str
    label: str | None = None

    @field_validator("target_class")
    @classmethod
    def must_be_http(cls, v: str) -> str:
        if not v.startswith("http"):
            raise ValueError("target_class must be an IRI starting with 'http'")
        return v


class AddPropMappingBody(BaseModel):
    dataset: str
    graph: str
    source_field: str
    target_property: str

    @field_validator("target_property")
    @classmethod
    def must_be_http(cls, v: str) -> str:
        if not v.startswith("http"):
            raise ValueError("target_property must be an IRI")
        return v


class PropertyMappingItem(BaseModel):
    prop_mapping_iri: str
    source_field: str
    target_property: str


class ClassMappingItem(BaseModel):
    mapping_iri: str
    target_class: str
    identifier_field: str
    label: str | None = None
    property_mappings: list[PropertyMappingItem] = []


class DatasourceSummary(BaseModel):
    datasource_iri: str
    label: str | None = None
    ds_type: str
    connection_info: str
    description: str | None = None


class DatasourceDetail(DatasourceSummary):
    mappings: list[ClassMappingItem] = []


class CreateDatasourceResponse(DatasourceSummary):
    pass


class DeleteResponse(BaseModel):
    deleted: str


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[DatasourceSummary])
def get_datasources(
    dataset: str = Query(...),
    graph: str = Query(...),
):
    """Datasource 목록."""
    return ds_svc.list_datasources(dataset, graph)


@router.post("", response_model=CreateDatasourceResponse, status_code=201)
def post_datasource(body: CreateDatasourceBody):
    """Datasource 생성."""
    try:
        return ds_svc.create_datasource(
            body.dataset, body.graph, body.label,
            body.ds_type, body.connection_info, body.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ── 구체적 경로를 먼저 등록 ──────────────────────────────────────────────

@router.post(
    "/{ds_iri:path}/mappings/{mapping_iri:path}/properties",
    response_model=dict,
    status_code=201,
)
def post_property_mapping(ds_iri: str, mapping_iri: str, body: AddPropMappingBody):
    """PropertyMapping 추가."""
    ds_iri = unquote(ds_iri)
    mapping_iri = unquote(mapping_iri)
    # strip suffix '/properties'
    for suffix in ["/properties"]:
        if mapping_iri.endswith(suffix):
            mapping_iri = mapping_iri[: -len(suffix)]
    try:
        return ds_svc.add_property_mapping(
            body.dataset, body.graph, ds_iri, mapping_iri,
            body.source_field, body.target_property,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/{ds_iri:path}/mappings/{mapping_iri:path}",
    response_model=DeleteResponse,
)
def delete_class_mapping(
    ds_iri: str,
    mapping_iri: str,
    dataset: str = Query(...),
    graph: str = Query(...),
):
    """ClassMapping 삭제."""
    ds_iri = unquote(ds_iri)
    mapping_iri = unquote(mapping_iri)
    try:
        return ds_svc.delete_class_mapping(dataset, graph, ds_iri, mapping_iri)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/{ds_iri:path}/mappings",
    response_model=dict,
    status_code=201,
)
def post_class_mapping(ds_iri: str, body: AddClassMappingBody):
    """ClassMapping 추가."""
    ds_iri_decoded = unquote(ds_iri)
    if ds_iri_decoded.endswith("/mappings"):
        ds_iri_decoded = ds_iri_decoded[: -len("/mappings")]
    try:
        return ds_svc.add_class_mapping(
            body.dataset, body.graph, ds_iri_decoded,
            body.target_class, body.identifier_field, body.label,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{iri:path}", response_model=DatasourceDetail)
def get_datasource(
    iri: str,
    dataset: str = Query(...),
    graph: str = Query(...),
):
    """Datasource 상세."""
    ds_iri = unquote(iri)
    try:
        return ds_svc.get_datasource(dataset, graph, ds_iri)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{iri:path}", response_model=DatasourceDetail)
def patch_datasource(iri: str, body: UpdateDatasourceBody):
    """Datasource 수정."""
    ds_iri = unquote(iri)
    try:
        return ds_svc.update_datasource(
            body.dataset, body.graph, ds_iri,
            body.label, body.ds_type, body.connection_info, body.description,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{iri:path}", response_model=DeleteResponse)
def delete_datasource(
    iri: str,
    dataset: str = Query(...),
    graph: str = Query(...),
):
    """Datasource 삭제."""
    ds_iri = unquote(iri)
    try:
        return ds_svc.delete_datasource(dataset, graph, ds_iri)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
