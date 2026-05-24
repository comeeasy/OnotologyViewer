"""Namespace Custom / Universal 분류 및 prefix 매핑."""

from typing import Literal

# 알려진 Universal namespace: base IRI → canonical prefix
UNIVERSAL_NAMESPACES: dict[str, str] = {
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf",
    "http://www.w3.org/2000/01/rdf-schema#":        "rdfs",
    "http://www.w3.org/2002/07/owl#":               "owl",
    "http://www.w3.org/2001/XMLSchema#":            "xsd",
    "http://www.w3.org/2004/02/skos/core#":         "skos",
    "http://purl.org/dc/elements/1.1/":             "dc",
    "http://purl.org/dc/terms/":                    "dcterms",
    "http://xmlns.com/foaf/0.1/":                   "foaf",
    "http://schema.org/":                           "schema",
}

NamespaceType = Literal["custom", "universal"]


def classify(base_iri: str) -> NamespaceType:
    """base IRI가 Universal namespace이면 'universal', 아니면 'custom'."""
    return "universal" if base_iri in UNIVERSAL_NAMESPACES else "custom"


def get_prefix(base_iri: str) -> str | None:
    """Universal namespace의 canonical prefix를 반환한다. Custom이면 None."""
    return UNIVERSAL_NAMESPACES.get(base_iri)
