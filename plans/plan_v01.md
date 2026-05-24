# OntologyViewer — 구현 계획 v01

**Date:** 2026-05-24  
**Scope:** 핵심 기능 3개 (MVP)  
**Backend:** Python (FastAPI) + Apache Jena Fuseki  
**Frontend:** 백엔드 완성 후 별도 진행  
**Spec 참조:** `wiki/queries/ontology-viewer-spec.md`

---

## 구현할 핵심 기능 3개

| # | 기능명 | 역할 |
|---|--------|------|
| F1 | **OOI Navigator** | Dataset → Named Graph → Namespace 탐색, OOI 선택 |
| F2 | **TBox Editor** | Class + Object/Data Property CRUD |
| F3 | **ABox Editor** | Individual CRUD |

**선정 이유:**  
이 3개가 완결된 최소 흐름을 형성한다.  
`OOI 선택 → 스키마(TBox) 정의 → 인스턴스(ABox) 투입`  
Reasoning, SHACL, Datasource 매핑은 v02 이후.

---

## 기술 스택

### Python 백엔드

| 역할 | 라이브러리 |
|------|-----------|
| API 서버 | `FastAPI` |
| Fuseki SPARQL 통신 | `SPARQLWrapper` (query/update) |
| Fuseki 관리 API 통신 | `httpx` (dataset 목록/생성) |
| RDF 로컬 처리 | **v01: 불필요** (모든 RDF 처리를 Fuseki에 위임) |

> ⚠️ `rdflib`은 순수 Python이라 느림. v01에서는 SPARQL 문자열 조립 + JSON 파싱만으로 충분하므로 제거.  
> v02에서 TTL import/export 등 로컬 RDF 처리가 필요해지면 `pyoxigraph` (Rust 바인딩, 10~100x 빠름) 도입.

### 프로젝트 구조 (예시)

```
backend/
├── main.py                  # FastAPI 앱 진입점
├── config.py                # Fuseki endpoint URL 등 설정
├── fuseki/
│   ├── client.py            # Fuseki Admin API 클라이언트 (dataset 관리)
│   └── sparql.py            # SPARQL query / update 실행기
├── routers/
│   ├── navigator.py         # F1: OOI Navigator API
│   ├── tbox.py              # F2: TBox Editor API
│   └── abox.py              # F3: ABox Editor API
└── services/
    ├── iri.py               # IRI 생성 로직
    ├── namespace.py         # Namespace 분류 (Custom/Universal)
    └── ontology.py          # TBox/ABox 공통 로직
```

### Fuseki 멀티 dataset 구성

Fuseki Admin REST API (`http://localhost:3030/$/...`) 로 dataset을 관리한다.

| 작업 | API |
|------|-----|
| Dataset 목록 조회 | `GET /$/datasets` |
| Dataset 생성 | `POST /$/datasets` (form: `dbName`, `dbType=tdb2`) |
| Dataset 삭제 | `DELETE /$/datasets/{name}` |
| SPARQL Query | `GET /POST /{name}/sparql` |
| SPARQL Update | `POST /{name}/update` |
| Named Graph 관리 | `GET/PUT/DELETE /{name}/data?graph={graphIRI}` (GSP) |

### IRI 자동 생성 규칙

```
IRI = {baseIRI} + {PascalCaseSlug} + "_" + {uuid4_hex}

PascalCaseSlug : rdfs:label을 PascalCase로 정규화
                 (e.g. "my person class" → "MyPersonClass")
uuid4_hex      : uuid4 전체 hex 32자리 (128-bit random, 하이픈 없음)
                 (e.g. "a3b2c1d4e5f60718293a4b5c6d7e8f90")

예시:
  baseIRI  = "http://myorg.com/onto#"
  label    = "Person"
  결과 IRI = "http://myorg.com/onto#Person_a3b2c1d4e5f60718293a4b5c6d7e8f90"
```

**Fuseki 조회 없음.** UUID4는 2^122 가지 값 → 충돌 확률 수학적으로 무시 가능.  
구현: `services/iri.py`의 `generate_iri(base_iri, label)` 함수 단일 책임.

---

## F1. OOI Navigator

### 목표
사용자가 Fuseki에 연결된 Dataset 아래의 Named Graph / Namespace 계층을 탐색하고,  
**OOI (Named Graph + Namespace 조합)** 를 선택할 수 있다.

### 기능 범위 (in scope)
- Fuseki 연결 설정 (endpoint URL 입력)
- Dataset 목록 조회
- 선택한 Dataset 아래 Named Graph 목록 조회
- Named Graph 아래 Namespace 목록 조회 (Custom / Universal 구분 표시)
- Named Graph ↔ Namespace 상호 포함 관계 조회
- OOI 선택 (Named Graph + Namespace 체크박스 복수 선택)
- 선택된 OOI를 이후 F2, F3 작업의 컨텍스트로 고정

### 기능 범위 (out of scope)
- Dataset / Named Graph / Namespace CRUD (v02)
- Universal namespace import UI (v02)

### API / SPARQL

```python
# Dataset 목록 — Fuseki Admin API
GET /$/datasets
→ JSON: { "datasets": [{ "ds.name": "/myds", "ds.state": "active", ... }, ...] }
```

```sparql
-- Named Graph 목록 (dataset별 SPARQL endpoint 호출)
SELECT DISTINCT ?g WHERE { GRAPH ?g { } }

-- Named Graph 안의 Namespace(prefix) 목록
SELECT DISTINCT ?ns WHERE {
  GRAPH <{namedGraphIRI}> {
    ?s ?p ?o .
    BIND(REPLACE(str(?s), "(#|/)[^#/]*$", "$1") AS ?ns)
  }
}

-- Namespace에 속하는 Named Graph 목록
SELECT DISTINCT ?g WHERE {
  GRAPH ?g {
    ?s ?p ?o .
    FILTER(STRSTARTS(str(?s), "{baseIRI}"))
  }
}

-- Universal namespace 판별 (잘 알려진 prefix 목록과 대조)
-- rdf, rdfs, owl, xsd, skos, dc, foaf, schema 등은 Universal로 분류
-- 그 외는 Custom
```

### 성공 기준
- [ ] Fuseki endpoint에 연결하면 Dataset 목록이 표시된다
- [ ] Named Graph를 선택하면 해당 그래프의 Namespace 목록이 표시된다
- [ ] Custom / Universal Namespace가 구분되어 표시된다
- [ ] Named Graph + Namespace를 선택하면 OOI가 고정된다
- [ ] 선택된 OOI가 F2, F3 작업 전반에 컨텍스트로 유지된다

---

## F2. TBox Editor

### 목표
선택된 OOI 범위 안에서 **Class, Object Property, Data Property를 생성·수정·삭제·조회**할 수 있다.

### 기능 범위 (in scope)

#### Class
- Create: rdfs:label, rdfs:comment 입력 → IRI 자동 생성 → SPARQL INSERT
- Read: Class 목록 조회, subClassOf 계층 트리 표시
- Update: rdfs:label / rdfs:comment 수정
- Delete: 소속 Individual 처리(삭제 or 마이그레이션 선택) → 연결 관계 제거 → 선언 삭제

#### Object Property
- Create: property 명(camelCase) + domain(Class 선택) + range(Class 선택) + characteristics 선택
- Read: property 목록, domain/range 표시
- Update: domain / range / characteristics 수정
- Delete: Individual 간 관계 삭제 → domain/range 선언 삭제 → 선언 삭제

#### Data Property
- Create: property 명(camelCase) + domain(Class 선택) + range(xsd datatype 선택) + Functional 여부
- Read: property 목록, domain/datatype 표시
- Update: domain / range / characteristics 수정
- Delete: Individual 값 삭제 → 선언 삭제

### 기능 범위 (out of scope)
- subClassOf 계층 편집 (Class 간 상속 관계 설정) — v02
- SHACL / Rule 시각화 — v02
- Datasource 매핑 — v02
- inverseOf 설정 — v02

### 필요한 SPARQL

```sparql
# Class 목록
SELECT ?class ?label ?comment WHERE {
  GRAPH <{namedGraphIRI}> {
    ?class a owl:Class .
    OPTIONAL { ?class rdfs:label ?label }
    OPTIONAL { ?class rdfs:comment ?comment }
    FILTER(STRSTARTS(str(?class), "{baseIRI}"))
  }
}

# Class 생성
INSERT DATA {
  GRAPH <{namedGraphIRI}> {
    <{classIRI}> a owl:Class ;
      rdfs:label "{label}" ;
      rdfs:comment "{comment}" .
  }
}

# Object Property 목록
SELECT ?prop ?label ?domain ?range WHERE {
  GRAPH <{namedGraphIRI}> {
    ?prop a owl:ObjectProperty .
    OPTIONAL { ?prop rdfs:label ?label }
    OPTIONAL { ?prop rdfs:domain ?domain }
    OPTIONAL { ?prop rdfs:range ?range }
    FILTER(STRSTARTS(str(?prop), "{baseIRI}"))
  }
}

# Class 삭제 (3단계 — 트랜잭션으로 처리)
# 1) Individual 분리
# 2) domain/range/관계 제거
DELETE WHERE {
  GRAPH <{namedGraphIRI}> {
    ?prop rdfs:domain <{classIRI}> .
    ?prop rdfs:range  <{classIRI}> .
  }
}
# 3) Class 선언 삭제
DELETE DATA {
  GRAPH <{namedGraphIRI}> {
    <{classIRI}> a owl:Class .
    <{classIRI}> rdfs:label ?label .
    ...
  }
}
```

### 성공 기준
- [ ] OOI 범위 안의 Class 목록이 조회된다
- [ ] Class를 생성하면 Fuseki에 owl:Class 트리플이 저장된다
- [ ] Class를 삭제하면 3단계 절차가 순서대로 실행된다
- [ ] Object Property 생성 시 domain / range / characteristics가 저장된다
- [ ] Data Property 생성 시 xsd datatype range가 저장된다

---

## F3. ABox Editor

### 목표
선택된 OOI 범위 안에서 **Individual을 생성·조회·수정·삭제**할 수 있다.

### 기능 범위 (in scope)

#### Individual
- Create: Class 선택 → IRI 입력(or 자동생성) → rdfs:label → data property 값 입력 → object property 관계 설정
- Read: Individual 목록(Class별 필터), data property 값 목록, object property 관계(outgoing + incoming)
- Update: label / data property 값 / object property 관계 수정·추가·삭제
- Delete: outgoing + incoming 관계 삭제 → data property 값 삭제 → 선언 삭제

### 기능 범위 (out of scope)
- 소속 Class 변경(마이그레이션) — v02
- SHACL 검증 결과 표시 — v02
- Individual 통계값 — v02

### 필요한 SPARQL

```sparql
# Class별 Individual 목록
SELECT ?ind ?label WHERE {
  GRAPH <{namedGraphIRI}> {
    ?ind a <{classIRI}> .
    OPTIONAL { ?ind rdfs:label ?label }
    FILTER(STRSTARTS(str(?ind), "{baseIRI}"))
  }
}

# Individual의 모든 property 값 (outgoing)
SELECT ?prop ?value WHERE {
  GRAPH <{namedGraphIRI}> { <{indIRI}> ?prop ?value }
  FILTER(?prop != rdf:type)
}

# Individual의 incoming 관계
SELECT ?subj ?prop WHERE {
  GRAPH <{namedGraphIRI}> { ?subj ?prop <{indIRI}> }
}

# Individual 생성
INSERT DATA {
  GRAPH <{namedGraphIRI}> {
    <{indIRI}> a <{classIRI}> ;
      rdfs:label "{label}" ;
      <{dataPropIRI}> "{value}"^^xsd:string .
  }
}

# Individual 삭제 (3단계)
# 1) outgoing + incoming 관계 삭제
DELETE WHERE { GRAPH <{namedGraphIRI}> { <{indIRI}> ?p ?o } }
DELETE WHERE { GRAPH <{namedGraphIRI}> { ?s ?p <{indIRI}> } }
# 2) 선언 삭제 (위에서 함께 처리됨)
```

### 성공 기준
- [ ] Class를 선택하면 소속 Individual 목록이 조회된다
- [ ] Individual 생성 시 data property 값이 함께 저장된다
- [ ] Individual 조회 시 outgoing + incoming object property 관계가 모두 표시된다
- [ ] Individual 삭제 시 관계 트리플이 먼저 제거된 후 선언이 삭제된다

---

## 구현 순서

```
F1 (OOI Navigator)
  └─ Fuseki 연결 + Named Graph / Namespace 탐색
  └─ OOI 선택 컨텍스트 관리

F2 (TBox Editor)
  └─ Class CRUD
  └─ Object Property CRUD
  └─ Data Property CRUD

F3 (ABox Editor)
  └─ Individual CRUD
```

F1이 완료되어야 F2, F3의 OOI 컨텍스트가 확정되므로 **F1 → F2 → F3 순서로 구현**.

---

## v02 예정 항목

- Dataset / Named Graph / Namespace CRUD
- Class 계층(subClassOf) 편집
- Reasoning (Jena Reasoner)
- SHACL 검증 및 시각화
- inverseOf 설정
- Individual Class 마이그레이션
- Datasource 매핑
