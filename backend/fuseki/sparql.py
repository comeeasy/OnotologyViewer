"""Fuseki SPARQL query / update 실행기."""

from SPARQLWrapper import JSON, POST, SPARQLWrapper
from config import settings


def _sparql_endpoint(dataset: str) -> str:
    return f"{settings.fuseki_base_url}/{dataset}/sparql"


def _update_endpoint(dataset: str) -> str:
    return f"{settings.fuseki_base_url}/{dataset}/update"


def _set_auth(sw: SPARQLWrapper) -> None:
    """Admin 인증 정보를 SPARQLWrapper 에 적용한다."""
    sw.setHTTPAuth("BASIC")
    sw.setCredentials(settings.fuseki_admin_user, settings.fuseki_admin_password)


def _flatten(bindings: list[dict]) -> list[dict]:
    """
    SPARQLWrapper JSON 결과를 단순 dict 리스트로 변환한다.

    입력:  [{"g": {"type": "uri", "value": "http://..."}}]
    출력:  [{"g": "http://..."}]
    """
    return [{k: v["value"] for k, v in row.items()} for row in bindings]


def query(dataset: str, sparql_str: str) -> list[dict]:
    """
    SPARQL SELECT 쿼리를 실행하고 결과 row 리스트를 반환한다.

    Args:
        dataset:    Fuseki dataset 명 (e.g. "myds")
        sparql_str: SPARQL SELECT 문자열

    Returns:
        [{"varName": "value", ...}, ...]
    """
    sw = SPARQLWrapper(_sparql_endpoint(dataset))
    _set_auth(sw)
    sw.setQuery(sparql_str)
    sw.setReturnFormat(JSON)
    results = sw.query().convert()
    bindings = results.get("results", {}).get("bindings", [])
    return _flatten(bindings)


def update(dataset: str, sparql_str: str) -> None:
    """
    SPARQL UPDATE(INSERT/DELETE)를 실행한다.

    Args:
        dataset:    Fuseki dataset 명
        sparql_str: SPARQL UPDATE 문자열
    """
    sw = SPARQLWrapper(_update_endpoint(dataset))
    _set_auth(sw)
    sw.setMethod(POST)
    sw.setQuery(sparql_str)
    sw.query()
