"""v03-D Universal Namespace import 엔드포인트."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from fuseki.sparql import update as sparql_update
from services.namespace_crud import is_declared

router = APIRouter(prefix="/api/namespaces", tags=["universal-namespaces"])

# ──────────────────────────────────────────────────────────────────────────────
# 잘 알려진 Universal Namespace 목록
# ──────────────────────────────────────────────────────────────────────────────

UNIVERSAL_NAMESPACES: list[dict] = [
    {"prefix": "rdf",     "ns_iri": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"},
    {"prefix": "rdfs",    "ns_iri": "http://www.w3.org/2000/01/rdf-schema#"},
    {"prefix": "owl",     "ns_iri": "http://www.w3.org/2002/07/owl#"},
    {"prefix": "xsd",     "ns_iri": "http://www.w3.org/2001/XMLSchema#"},
    {"prefix": "skos",    "ns_iri": "http://www.w3.org/2004/02/skos/core#"},
    {"prefix": "dc",      "ns_iri": "http://purl.org/dc/elements/1.1/"},
    {"prefix": "dcterms", "ns_iri": "http://purl.org/dc/terms/"},
    {"prefix": "foaf",    "ns_iri": "http://xmlns.com/foaf/0.1/"},
    {"prefix": "schema",  "ns_iri": "http://schema.org/"},
    {"prefix": "vann",    "ns_iri": "http://purl.org/vocab/vann/"},
    {"prefix": "prov",    "ns_iri": "http://www.w3.org/ns/prov#"},
    {"prefix": "dcat",    "ns_iri": "http://www.w3.org/ns/dcat#"},
    {"prefix": "void",    "ns_iri": "http://rdfs.org/ns/void#"},
    {"prefix": "sh",      "ns_iri": "http://www.w3.org/ns/shacl#"},
    {"prefix": "geo",     "ns_iri": "http://www.opengis.net/ont/geosparql#"},
]

# prefix → ns_iri 맵
_PREFIX_MAP: dict[str, str] = {ns["prefix"]: ns["ns_iri"] for ns in UNIVERSAL_NAMESPACES}


# ──────────────────────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────────────────────

class UniversalNsItem(BaseModel):
    prefix: str
    ns_iri: str


class ImportNsBody(BaseModel):
    dataset: str
    graph: str
    prefix: str

    @field_validator("prefix")
    @classmethod
    def must_be_known(cls, v: str) -> str:
        if v not in _PREFIX_MAP:
            raise ValueError(
                f"알 수 없는 Universal prefix: {v!r}. "
                f"지원: {sorted(_PREFIX_MAP.keys())}"
            )
        return v


class ImportNsResponse(BaseModel):
    ns_iri: str
    prefix: str
    graph: str


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/universal", response_model=list[UniversalNsItem])
def get_universal_namespaces():
    """잘 알려진 Universal Namespace 목록을 반환한다."""
    return UNIVERSAL_NAMESPACES


@router.post("/universal/import", response_model=ImportNsResponse, status_code=201)
def post_import_universal_ns(body: ImportNsBody):
    """
    Universal Namespace를 OOI 그래프에 vann:preferredNamespacePrefix로 선언한다.

    이미 선언된 경우 → 409 Conflict
    알 수 없는 prefix → 422 (validator)
    """
    ns_iri = _PREFIX_MAP[body.prefix]

    # 중복 확인
    if is_declared(body.dataset, body.graph, ns_iri):
        raise HTTPException(
            status_code=409,
            detail=f"이미 선언된 Namespace입니다: {ns_iri}",
        )

    esc_prefix = body.prefix.replace('"', '\\"')

    sparql_update(body.dataset, f"""
    PREFIX owl:  <http://www.w3.org/2002/07/owl#>
    PREFIX vann: <http://purl.org/vocab/vann/>
    INSERT DATA {{
      GRAPH <{body.graph}> {{
        <{ns_iri}> a owl:Ontology ;
            vann:preferredNamespacePrefix "{esc_prefix}" .
      }}
    }}
    """)

    return ImportNsResponse(
        ns_iri=ns_iri,
        prefix=body.prefix,
        graph=body.graph,
    )
