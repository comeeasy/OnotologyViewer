"""TBox — Class CRUD 라우터."""

from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.class_ import (
    add_super_class,
    create_class,
    delete_class,
    get_class_detail,
    list_class_hierarchy,
    list_classes,
    remove_super_class,
    update_class,
)

router = APIRouter(prefix="/api/tbox/classes", tags=["classes"])


# ────────────────────────────────────────────────
# Request / Response models
# ────────────────────────────────────────────────

class ClassSummary(BaseModel):
    source_graph: str | None = None  # 복수 그래프 지원: 출처 그래프 IRI
    iri:          str
    label:        str | None
    comment:      str | None


class ClassesResponse(BaseModel):
    dataset:   str
    graph:     str
    namespace: str
    classes:   list[ClassSummary]


class ObjectPropertyRef(BaseModel):
    iri:   str
    label: str | None
    role:  str          # "domain" | "range"


class DataPropertyRef(BaseModel):
    iri:   str
    label: str | None
    range: str | None


class ClassDetail(BaseModel):
    iri:               str
    label:             str | None
    comment:           str | None
    super_classes:     list[str]
    sub_classes:       list[str]
    object_properties: list[ObjectPropertyRef]
    data_properties:   list[DataPropertyRef]
    individual_count:  int


class CreateClassBody(BaseModel):
    dataset:   str
    graph:     str
    namespace: str
    label:     str
    comment:   str


class CreateClassResponse(BaseModel):
    iri: str


class UpdateClassBody(BaseModel):
    dataset:  str
    graph:    str
    label:    str | None = None
    comment:  str | None = None


class AddSuperClassBody(BaseModel):
    dataset:    str
    graph:      str
    parent_iri: str


class HierarchyItem(BaseModel):
    source_graph:  str | None = None
    iri:           str
    super_classes: list[str]


# ────────────────────────────────────────────────
# Endpoints
# ────────────────────────────────────────────────

@router.get("", response_model=ClassesResponse)
def get_classes(
    dataset:   str       = Query(..., description="Fuseki dataset 명"),
    graph:     list[str] = Query(..., description="Named Graph IRI (복수 허용)"),
    namespace: list[str] = Query(..., description="Namespace base IRI (복수 허용)"),
):
    """OOI 범위 내 모든 Class 목록을 반환한다 (복수 그래프 지원)."""
    graphs  = [g for g in graph if g.strip()]
    ns_list = [ns for ns in namespace if ns.strip()]
    if not graphs:
        raise HTTPException(422, "graph는 하나 이상 유효한 값을 제공해야 합니다.")
    if not ns_list:
        raise HTTPException(422, "namespace는 하나 이상 유효한 값을 제공해야 합니다.")
    try:
        classes = list_classes(dataset, graphs, ns_list)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return ClassesResponse(
        dataset=dataset,
        graph=graphs[0],        # 하위호환: 첫 번째 그래프
        namespace=ns_list[0],   # 하위호환: 첫 번째 namespace
        classes=[ClassSummary(**c) for c in classes],
    )


@router.post("", response_model=CreateClassResponse, status_code=201)
def post_class(body: CreateClassBody):
    """Class를 생성하고 신규 IRI를 반환한다."""
    try:
        iri = create_class(
            dataset=body.dataset,
            graph=body.graph,
            namespace=body.namespace,
            label=body.label,
            comment=body.comment,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return CreateClassResponse(iri=iri)


@router.get("/hierarchy", response_model=list[HierarchyItem])
def get_class_hierarchy(
    dataset:   str       = Query(..., description="Fuseki dataset 명"),
    graph:     list[str] = Query(..., description="Named Graph IRI (복수 허용)"),
    namespace: list[str] = Query(..., description="Namespace base IRI (복수 허용)"),
):
    """모든 Class의 직접 상위 Class 목록을 반환한다 (트리 뷰 구성용)."""
    graphs  = [g for g in graph if g.strip()]
    ns_list = [ns for ns in namespace if ns.strip()]
    if not graphs:
        raise HTTPException(422, "graph는 하나 이상 유효한 값을 제공해야 합니다.")
    if not ns_list:
        raise HTTPException(422, "namespace는 하나 이상 유효한 값을 제공해야 합니다.")
    try:
        items = list_class_hierarchy(dataset, graphs, ns_list)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return [HierarchyItem(**item) for item in items]


@router.get("/{iri:path}", response_model=ClassDetail)
def get_class(
    iri:     str,
    dataset: str = Query(..., description="Fuseki dataset 명"),
    graph:   str = Query(..., description="Named Graph IRI"),
):
    """
    Class 상세 정보를 반환한다.

    - superclass / subclass 계층
    - 관련 Object Property (domain / range)
    - 관련 Data Property
    - Individual 수
    """
    class_iri = unquote(iri)
    try:
        detail = get_class_detail(dataset, graph, class_iri)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if detail is None:
        raise HTTPException(status_code=404, detail=f"Class not found: {class_iri}")

    return ClassDetail(**detail)


@router.patch("/{iri:path}", status_code=204)
def patch_class(iri: str, body: UpdateClassBody):
    """label / comment 중 제공된 필드만 수정한다."""
    class_iri = unquote(iri)
    try:
        update_class(
            dataset=body.dataset,
            graph=body.graph,
            class_iri=class_iri,
            label=body.label,
            comment=body.comment,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))


@router.post("/{iri:path}/super-classes", status_code=201)
def post_super_class(iri: str, body: AddSuperClassBody):
    """child rdfs:subClassOf parent 관계를 추가한다."""
    child_iri = unquote(iri)
    if child_iri.endswith("/super-classes"):
        child_iri = child_iri[: -len("/super-classes")]
    try:
        add_super_class(body.dataset, body.graph, child_iri, body.parent_iri)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(404, msg)
        if "circular" in msg:
            raise HTTPException(400, msg)
        raise HTTPException(422, msg)


@router.delete("/{iri:path}/super-classes/{parent:path}", status_code=204)
def delete_super_class(
    iri:     str,
    parent:  str,
    dataset: str = Query(...),
    graph:   str = Query(...),
):
    """child rdfs:subClassOf parent 관계를 삭제한다 (멱등)."""
    child_iri = unquote(iri)
    if child_iri.endswith("/super-classes"):
        child_iri = child_iri[: -len("/super-classes")]
    parent_iri = unquote(parent)
    try:
        remove_super_class(dataset, graph, child_iri, parent_iri)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.delete("/{iri:path}", status_code=204)
def delete_class_endpoint(
    iri:                str,
    dataset:            str = Query(...),
    graph:              str = Query(...),
    on_individual:      str = Query("delete", description="delete | migrate"),
    target_class_iri:   str | None = Query(None, description="migrate 시 대상 Class IRI"),
):
    """
    Class를 삭제한다 (3단계).

    1. 소속 Individual 처리 (on_individual=delete → 삭제 / migrate → target_class_iri로 이동)
    2. domain/range 참조 제거
    3. Class 선언 삭제
    """
    class_iri = unquote(iri)
    try:
        delete_class(dataset, graph, class_iri, on_individual, target_class_iri)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
