# Apache Jena Fuseki

**Type:** Tool  
**Role:** OntologyViewer 백엔드 — 온톨로지 저장 및 SPARQL 처리  
**Related concepts:** [[sparql]], [[named-graph]], [[reasoning]], [[dataset]]  
**Sources:** (architecture decision)

## Overview

OntologyViewer의 온톨로지 관리 백엔드로 Apache Jena Fuseki를 사용한다.  
Fuseki는 Apache Jena 기반의 SPARQL 서버로, SPARQL 1.1 endpoint와 Named Graph, 내장 Reasoner를 제공한다.

## 아키텍처 매핑

| Spec 개념 | Fuseki/Jena 구현 |
|-----------|----------------|
| Dataset | Fuseki dataset (TDB2) |
| Named Graph | Fuseki dataset 내 named graph |
| Namespace | Jena `PrefixMapping` (모델 레벨) |
| SPARQL CRUD | `/sparql` (query), `/update` (SPARQL Update) 엔드포인트 |
| Named Graph 관리 | SPARQL Graph Store Protocol (GSP) |
| Reasoning Materialization | SPARQL `CONSTRUCT` → `INSERT` 패턴 |

## Jena 내장 Reasoner 목록

| Reasoner | 설명 | 권장 상황 |
|----------|------|---------|
| `OWL_DL_MEM_RULE` | OWL DL + 추론 규칙 | 일반 온톨로지 (권장) |
| `OWL_MEM_RULE` | OWL Full + 추론 규칙 | 표현력 최대 필요 시 |
| `OWL_MEM_TRANS_INF` | Transitive inference만 | 경량 hierarchy 추론 |
| `RDFS` | RDFS 추론만 | RDFS 수준 스키마 |

> HermiT, Pellet, ELK는 OWL API 기반으로 별도 통합이 필요하며, 현재 스펙 범위 밖.

## Notes
- Fuseki 선택으로 item 40c(Reasoner 목록)가 Jena 내장 Reasoner 기준으로 수정됨
