# OntologyViewer — Master Plan

**Date:** 2026-05-25 (updated)  
**Source:** `raw/spec.md`, `wiki/queries/ontology-viewer-spec.md`, `plans/plan_v01.md`  
**Status:** v01 ✅ | v02 ✅ | v03 ✅ | v04 🚧 (진행 중)

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [기술 스택](#2-기술-스택)
3. [데이터 모델](#3-데이터-모델)
4. [기능 카탈로그](#4-기능-카탈로그)
5. [REST API 설계](#5-rest-api-설계)
6. [프론트엔드 UI 설계](#6-프론트엔드-ui-설계)
7. [핵심 SPARQL 레퍼런스](#7-핵심-sparql-레퍼런스)
8. [구현 단계](#8-구현-단계)
9. [미결 항목](#9-미결-항목)

---

## 1. 시스템 개요

OntologyViewer는 Apache Jena Fuseki 위에서 온톨로지를 관리하는 백엔드 시스템이다.

```
사용자
  │
  ▼
FastAPI 백엔드          ← Python (이 프로젝트)
  │   ├─ SPARQL query/update ─────────────────┐
  │   └─ Admin REST API (dataset 관리) ────┐  │
  ▼                                        ▼  ▼
Apache Jena Fuseki      ← TDB2 multi-dataset store
```

**핵심 개념:**
- **Dataset**: 최상위 단위. Fuseki TDB2 dataset.
- **Named Graph**: 온톨로지 구분 축 1. Dataset 안의 named graph.
- **Namespace**: 온톨로지 구분 축 2. Base IRI (prefix 기저).
- **OOI (Ontology of Interest)**: Named Graph + Namespace(들) 조합. 모든 작업의 스코프.
- **TBox**: 스키마 (Class, Object Property, Data Property)
- **ABox**: 인스턴스 (Individual)

---

## 2. 기술 스택

### 백엔드

| 역할 | 라이브러리 | 비고 |
|------|-----------|------|
| API 서버 | `FastAPI` | |
| SPARQL query/update | `SPARQLWrapper` | Fuseki `/sparql`, `/update` 엔드포인트 |
| Fuseki Admin API | `httpx` | Dataset 목록/생성/삭제 |
| RDF 로컬 처리 | **v01: 불필요** | v02+ 필요 시 `pyoxigraph` (Rust 바인딩, rdflib 대비 10~100x) |

### 프론트엔드

| 역할 | 라이브러리 | 비고 |
|------|-----------|------|
| 빌드 도구 | `Vite` 5 | |
| 런타임 | `React` 18 + TypeScript 5 | |
| UI 컴포넌트 | `Ant Design` 5 | Table, Form, Modal, Drawer, Tabs 적극 활용 |
| HTTP | fetch (native) | IRI 경로: `encodeURIComponent()` 필수 처리 |
| 상태관리 | React Context + useState | 전역: OOI 컨텍스트 / 로컬: 각 패널 독립 |

### 프로젝트 구조

#### 백엔드

```
backend/
├── main.py
├── config.py                    # Fuseki URL 등 환경 설정
├── fuseki/
│   ├── client.py                # Fuseki Admin API (dataset 관리)
│   └── sparql.py                # SPARQL query / update 실행기
├── routers/
│   ├── datasets.py              # Dataset CRUD
│   ├── graphs.py                # Named Graph CRUD
│   ├── namespaces.py            # Namespace CRUD
│   ├── classes.py               # Class CRUD
│   ├── object_properties.py     # Object Property CRUD
│   ├── data_properties.py       # Data Property CRUD
│   └── individuals.py           # Individual CRUD
└── services/
    ├── iri.py                   # IRI 생성 (SHA256 content-addressing)
    ├── namespace.py             # Custom/Universal 분류
    ├── class_.py
    ├── object_property.py
    ├── data_property.py
    └── individual.py
```

#### 프론트엔드

```
frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
└── src/
    ├── main.tsx                       # ReactDOM.createRoot
    ├── App.tsx                        # Layout + OOIProvider
    ├── api/
    │   ├── client.ts                  # apiFetch 래퍼, encodeIRI 헬퍼
    │   ├── navigator.ts               # health, datasets, graphs, namespaces
    │   ├── classes.ts
    │   ├── objProps.ts
    │   ├── dataProps.ts
    │   └── individuals.ts
    ├── context/
    │   └── OOIContext.tsx             # {dataset, graph, namespace} 전역 공유
    ├── components/
    │   ├── Navigator/
    │   │   └── OOINavigator.tsx
    │   ├── Classes/
    │   │   ├── ClassTable.tsx
    │   │   ├── ClassDialog.tsx        # create / edit 공용
    │   │   └── ClassDetail.tsx        # Drawer
    │   ├── ObjProps/
    │   │   ├── ObjPropTable.tsx
    │   │   ├── ObjPropDialog.tsx
    │   │   └── ObjPropDetail.tsx      # Drawer (characteristics 표시)
    │   ├── DataProps/
    │   │   ├── DataPropTable.tsx
    │   │   ├── DataPropDialog.tsx
    │   │   └── DataPropDetail.tsx     # Drawer (functional 표시)
    │   └── Individuals/
    │       ├── IndividualTable.tsx
    │       ├── IndividualCreateDialog.tsx
    │       ├── IndividualEditDialog.tsx
    │       └── IndividualDetail.tsx   # Drawer (outgoing + incoming)
    └── types/
        └── ontology.ts               # 공통 TypeScript 타입
```

### IRI 자동 생성

```python
# services/iri.py
IRI = {baseIRI} + {PascalCaseSlug} + "_" + {uuid4_hex_32자리}

# 예시
baseIRI = "http://myorg.com/onto#"
label   = "Person"
→ "http://myorg.com/onto#Person_a3b2c1d4e5f60718293a4b5c6d7e8f90"
```

- Fuseki 조회 없음. UUID4 실제 엔트로피 122-bit (버전·배리언트 6비트 고정). 충돌 확률 p ≈ n² / 2¹²³ → 10억 건 기준 p ≈ 10⁻¹⁹. 0이 아니나 실용적으로 무시 가능한 수준.

---

## 3. 데이터 모델

### 3-1. 계층 구조

```
Dataset  (Fuseki TDB2 dataset)
└── Named Graph  (owl:Ontology IRI)
    ├── Namespace A (Custom)
    │   ├── TBox
    │   │   ├── Class
    │   │   ├── Object Property
    │   │   └── Data Property
    │   └── ABox
    │       └── Individual
    └── Namespace B (Universal, e.g. foaf)
```

### 3-2. TBox

#### Class
| 속성 | 타입 | 필수 |
|------|------|------|
| IRI | xsd:anyURI | ✅ (자동 생성) |
| `rdf:type` | `owl:Class` | ✅ |
| `rdfs:label` | xsd:string | ✅ |
| `rdfs:comment` | xsd:string | ✅ |
| `rdfs:subClassOf` | Class IRI | ❌ |

#### Object Property
| 속성 | 타입 | 필수 |
|------|------|------|
| IRI | xsd:anyURI | ✅ (자동 생성) |
| `rdf:type` | `owl:ObjectProperty` | ✅ |
| 명칭 | camelCase | ✅ |
| `rdfs:domain` | Class IRI | ✅ |
| `rdfs:range` | Class IRI | ✅ |
| characteristics | 아래 참조 | ❌ |

**Property Characteristics:**
`Functional` · `InverseFunctional` · `Transitive` · `Symmetric` · `Asymmetric` · `Reflexive` · `Irreflexive`

> `owl:inverseOf`는 characteristics가 아닌 별도 axiom (v02+)

#### Data Property
| 속성 | 타입 | 필수 |
|------|------|------|
| IRI | xsd:anyURI | ✅ (자동 생성) |
| `rdf:type` | `owl:DatatypeProperty` | ✅ |
| 명칭 | camelCase | ✅ |
| `rdfs:domain` | Class IRI | ✅ |
| `rdfs:range` | xsd datatype | ✅ |
| characteristics | `Functional`만 | ❌ |

**지원 xsd Range:** `string` · `integer` · `float` · `boolean` · `dateTime` · `anyURI`

### 3-3. ABox

#### Individual
| 속성 | 타입 | 필수 |
|------|------|------|
| IRI | xsd:anyURI | ✅ (자동 생성 or 입력) |
| `rdf:type` | Class IRI | ✅ |
| `rdfs:label` | xsd:string | ✅ |
| `rdfs:comment` | xsd:string | ❌ |
| Object Property 관계 | Individual IRI | ❌ |
| Data Property 값 | Literal | ❌ |

---

## 4. 기능 카탈로그

> 구현 단계: **v01** · **v02** · **v03**

### A. 인프라 — Dataset / Named Graph / Namespace

#### A1. Dataset
| 기능 | 상세 | 단계 |
|------|------|------|
| **목록 조회** | Fuseki Admin API `GET /$/datasets` | v02 |
| **Create** | dataset 명 + IRI → Fuseki Admin `POST /$/datasets` | v02 |
| **Update** | 명 / IRI 수정 | v02 |
| **Delete** | 포함 Named Graph 전체 처리(삭제 or 마이그레이션) → dataset 삭제 | v02 |

#### A2. Named Graph
| 기능 | 상세 | 단계 |
|------|------|------|
| **목록 조회** | `SELECT DISTINCT ?g WHERE { GRAPH ?g { } }` | v01 (읽기) |
| **Create** | Named Graph IRI + rdfs:label + rdfs:comment | v02 |
| **Update** | rdfs:label / rdfs:comment 수정 | v02 |
| **Delete** | 포함 트리플 전체 처리 → Named Graph 삭제 | v02 |

#### A3. Namespace
| 기능 | 상세 | 단계 |
|------|------|------|
| **목록 조회** | Named Graph 내 subject IRI에서 base IRI 추출 | v01 (읽기) |
| **Custom/Universal 구분** | 알려진 Universal 목록과 대조 | v01 |
| **Create** | prefix + base IRI + 유형(Custom/Universal) | v02 |
| **Update** | prefix / base IRI 수정 — 변경 시 IRI 일괄 치환 | v02 |
| **Delete** | 해당 namespace IRI 전체 처리 → 선언 삭제 | v02 |

**알려진 Universal Namespace:**

| prefix | base IRI |
|--------|----------|
| `rdf` | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` |
| `rdfs` | `http://www.w3.org/2000/01/rdf-schema#` |
| `owl` | `http://www.w3.org/2002/07/owl#` |
| `xsd` | `http://www.w3.org/2001/XMLSchema#` |
| `skos` | `http://www.w3.org/2004/02/skos/core#` |
| `dc` | `http://purl.org/dc/elements/1.1/` |
| `dcterms` | `http://purl.org/dc/terms/` |
| `foaf` | `http://xmlns.com/foaf/0.1/` |
| `schema` | `http://schema.org/` |

#### A4. OOI Navigator
| 기능 | 상세 | 단계 |
|------|------|------|
| **Fuseki 연결** | endpoint URL 입력 및 연결 확인 | v01 |
| **Dataset 목록** | Fuseki Admin API | v01 |
| **Named Graph 목록** | 선택된 dataset 기준 | v01 |
| **Namespace 목록** | 선택된 Named Graph 기준, Custom/Universal 구분 | v01 |
| **상호 포함 관계** | Named Graph → Namespaces / Namespace → Named Graphs | v01 |
| **OOI 선택** | Named Graph + Namespace(복수) 조합 선택, 컨텍스트 고정 | v01 |

---

### B. TBox — Class

#### B1. Class CRUD
| 기능 | 상세 | 단계 |
|------|------|------|
| **목록 조회** | OOI 범위 내 `owl:Class` 전체 | v01 |
| **Create** | OOI 선택 → rdfs:label → rdfs:comment → IRI 자동생성 → INSERT | v01 |
| **Update** | label / comment 수정 (optional) | v01 |
| **Delete** | ① Individual 처리(삭제 or 마이그레이션) → ② domain/range/관계 제거 → ③ 선언 삭제 | v01 |

#### B2. Class Read 뷰
| 뷰 | 내용 | 단계 |
|----|------|------|
| Class hierarchy | `rdfs:subClassOf` 기반 계층 트리 | v01 (읽기) / v02 (편집) |
| 관계 탐색 | domain, range 기반 Object Property 그래프 | v01 |
| Data Property 목록 | 소속 Individuals 통계값 포함 | v01 |
| SHACL 검증 룰 시각화 | 적용된 SHACL shape | v03 |
| Rule 시각화 | 추론 규칙 | v03 |
| Datasource 매핑 | 각 datasource ↔ class 매핑 | v03 |

---

### C. TBox — Object Property

#### C1. Object Property CRUD
| 기능 | 상세 | 단계 |
|------|------|------|
| **목록 조회** | OOI 범위 내 `owl:ObjectProperty` 전체, domain/range 표시 | v01 |
| **Create** | OOI → 명칭(camelCase) → domain(Class) → range(Class) → characteristics → IRI 자동생성 | v01 |
| **Update** | 명칭 / domain / range / characteristics 수정 (optional) | v01 |
| **Delete** | ① Individual 간 관계 삭제 → ② domain/range 선언 삭제 → ③ 선언 삭제 | v01 |

---

### D. TBox — Data Property

#### D1. Data Property CRUD
| 기능 | 상세 | 단계 |
|------|------|------|
| **목록 조회** | OOI 범위 내 `owl:DatatypeProperty` 전체 | v01 |
| **Create** | OOI → 명칭(camelCase) → domain(Class) → range(xsd datatype) → Functional 여부 | v01 |
| **Update** | 명칭 / domain / range / characteristics 수정 (optional) | v01 |
| **Delete** | ① Individual 값 삭제 → ② 선언 삭제 | v01 |

---

### E. ABox — Individual

#### E1. Individual CRUD
| 기능 | 상세 | 단계 |
|------|------|------|
| **목록 조회** | OOI 범위 내 Individual 전체, Class별 필터 | v01 |
| **Create** | OOI → Class 선택 → IRI(자동생성 or 입력) → label → data property 값 → object property 관계 | v01 |
| **Read** | 소속 Class / data property 값 / object property 관계(outgoing + incoming) / SHACL 결과 | v01 |
| **Update** | label / data property 값 / object property 관계 수정·추가·삭제 (optional) | v01 |
| **Delete** | ① outgoing + incoming 관계 삭제 → ② data property 값 삭제 → ③ 선언 삭제 | v01 |
| **Class 변경** | 소속 Class 마이그레이션 (상세 절차 미정의) | v02 |

---

### F. SPARQL Editor

#### F1. OOI-scoped SPARQL
| 기능 | 상세 | 단계 |
|------|------|------|
| **Query** | SELECT / CONSTRUCT / ASK — OOI Named Graph 범위 자동 적용 | v02 |
| **Update** | INSERT / DELETE / UPDATE — OOI Named Graph 범위 자동 적용 | v02 |

---

### G. Reasoning

#### G1. Reasoning 실행
| 기능 | 상세 | 단계 |
|------|------|------|
| **유형 선택** | Class hierarchy inference / Property inference / Consistency checking / Rule-based inference | v02 |
| **Reasoner 선택** | OWL_DL_MEM_RULE (권장) / OWL_MEM_RULE / OWL_MEM_TRANS_INF / RDFS | v02 |
| **결과 미리보기** | 추론된 트리플 목록 + Consistency 여부 + Inconsistency 설명 (미저장) | v02 |
| **Materialization** | 사용자 검토 후 저장 / 취소 결정 | v02 |

---

## 5. REST API 설계

### OOI 컨텍스트 전달 방식
OOI는 query parameter로 전달한다. Namespace는 복수 선택 가능.

```
?dataset={ds_name}
&graph={namedGraphIRI}       ← URL-encoded
&namespace={baseIRI}         ← 복수 허용 (&namespace=...&namespace=...)
```

### 엔드포인트 목록

#### Fuseki 연결
```
GET  /api/health                              # Fuseki 연결 확인
```

#### Dataset
```
GET    /api/datasets                          # 목록
POST   /api/datasets                          # 생성
DELETE /api/datasets/{ds_name}                # 삭제
```

#### Named Graph
```
GET    /api/datasets/{ds}/graphs              # 목록
POST   /api/datasets/{ds}/graphs              # 생성
PATCH  /api/datasets/{ds}/graphs              # 수정  ?graph={graphIRI}
DELETE /api/datasets/{ds}/graphs              # 삭제  ?graph={graphIRI}
```

#### Namespace
```
GET    /api/datasets/{ds}/namespaces          # 목록 (Custom/Universal 구분 포함)
POST   /api/datasets/{ds}/namespaces          # 생성
PATCH  /api/datasets/{ds}/namespaces/{prefix} # 수정 (IRI 일괄 치환)
DELETE /api/datasets/{ds}/namespaces/{prefix} # 삭제
```

#### OOI Navigator
```
GET /api/datasets/{ds}/graphs/{graphIRI}/namespaces   # graph → namespaces
GET /api/datasets/{ds}/namespaces/{prefix}/graphs     # namespace → graphs
```

#### TBox — Class
```
GET    /api/tbox/classes           # 목록      ?dataset&graph&namespace
POST   /api/tbox/classes           # 생성      body: {label, comment, ooi}
GET    /api/tbox/classes/{iri}     # 상세      ?dataset&graph
PATCH  /api/tbox/classes/{iri}     # 수정
DELETE /api/tbox/classes/{iri}     # 삭제      ?dataset&graph&on_individual=[delete|migrate]
```

#### TBox — Object Property
```
GET    /api/tbox/object-properties           # 목록
POST   /api/tbox/object-properties           # 생성
PATCH  /api/tbox/object-properties/{iri}     # 수정
DELETE /api/tbox/object-properties/{iri}     # 삭제
```

#### TBox — Data Property
```
GET    /api/tbox/data-properties             # 목록
POST   /api/tbox/data-properties             # 생성
PATCH  /api/tbox/data-properties/{iri}       # 수정
DELETE /api/tbox/data-properties/{iri}       # 삭제
```

#### ABox — Individual
```
GET    /api/abox/individuals              # 목록  ?class={classIRI} (optional filter)
POST   /api/abox/individuals              # 생성
GET    /api/abox/individuals/{iri}        # 상세 (outgoing + incoming 관계 포함)
PATCH  /api/abox/individuals/{iri}        # 수정
DELETE /api/abox/individuals/{iri}        # 삭제
```

#### SPARQL Editor
```
POST /api/sparql/query     # SELECT / CONSTRUCT / ASK  body: {sparql, dataset, graph}
POST /api/sparql/update    # INSERT / DELETE / UPDATE  body: {sparql, dataset, graph}
```

#### Reasoning
```
POST /api/reasoning/run          # 추론 실행 → 결과 미리보기 반환  body: {ooi, type, reasoner}
POST /api/reasoning/materialize  # 미리보기 결과 OOI에 저장       body: {triples, ooi}
```

---

## 6. 프론트엔드 UI 설계

### 6-1. 전체 레이아웃

```
┌─ Header ─────────────────────────────────────────────────────────┐
│  🔷 OntologyViewer                                               │
├──────────────────────────────────────────────────────────────────┤
│ ┌─ Sider (260px) ──────┐  ┌─ Content ──────────────────────────┐ │
│ │                      │  │                                    │ │
│ │  OOI Navigator       │  │  Tabs                              │ │
│ │  ─────────────────   │  │  [Class][Obj Prop][Data Prop][Ind] │ │
│ │  Fuseki: ✅ 연결됨    │  │                                    │ │
│ │                      │  │  [+ 새로 만들기]       [검색...]   │ │
│ │  Dataset  [▼ ds]     │  │  ┌────────────────────────────┐    │ │
│ │  Graph    [▼ g]      │  │  │  Table                     │    │ │
│ │  NS       [▼ ns]     │  │  │  (행 클릭 → 우측 Drawer)  │    │ │
│ │  [OOI 설정]           │  │  └────────────────────────────┘    │ │
│ │                      │  │                                    │ │
│ │  ── 현재 OOI ──      │  │  Modal (Create / Edit)             │ │
│ │  ontology            │  │  Drawer (Detail)                   │ │
│ │  /graph/test         │  │                                    │ │
│ │  http://ex.org/onto# │  │                                    │ │
│ └──────────────────────┘  └────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 6-2. OOI Navigator 흐름

```
앱 시작 → GET /api/health → 연결 상태 표시
         ↓
         GET /api/datasets → Dataset Select 활성화
         ↓ (dataset 선택 시)
         GET /api/datasets/{ds}/graphs → Graph Select 활성화
         ↓ (graph 선택 시)
         GET /api/datasets/{ds}/graphs/namespaces?graph= → NS 목록
           └ type=custom  → Select 선택 가능
           └ type=universal → 표시만 (선택 불가)
         ↓ ([OOI 설정] 클릭)
         OOIContext 업데이트 → 모든 탭 데이터 로드
```

> OOI 미설정 시: 탭 전체 `disabled` + `<Alert>OOI를 먼저 설정하세요</Alert>`

### 6-3. TypeScript 타입 (`types/ontology.ts`)

```ts
// Navigator
interface Dataset   { name: string; state: string }
interface Namespace { base_iri: string; prefix: string | null; type: 'custom' | 'universal' }

// OOI Context
interface OOIState {
  dataset: string | null; graph: string | null; namespace: string | null
  setOOI: (ds: string, graph: string, ns: string) => void
  clear: () => void
}

// TBox — Class
interface ClassSummary { iri: string; label: string | null; comment: string | null }
interface ClassDetail extends ClassSummary {
  super_classes:     string[]
  sub_classes:       string[]
  object_properties: { iri: string; label: string | null; role: 'domain' | 'range' }[]
  data_properties:   { iri: string; label: string | null; range: string | null }[]
  individual_count:  number
}

// TBox — Object Property
// 목록: characteristics 없음 / 상세: characteristics 포함
interface ObjPropSummary { iri: string; label: string | null; domain: string | null; range: string | null }
interface ObjPropDetail  extends ObjPropSummary { characteristics: string[] }
// characteristics 가능 값: "Functional" | "InverseFunctional" | "Transitive"
//                          | "Symmetric" | "Asymmetric" | "Reflexive" | "Irreflexive"

// TBox — Data Property
// 목록: functional 없음 / 상세: functional 포함
interface DataPropSummary { iri: string; label: string | null; domain: string | null; range: string | null }
interface DataPropDetail  extends DataPropSummary { functional: boolean }
// range: 목록·상세 응답은 full XSD IRI, 생성·수정 요청은 shortname
//        (string | integer | float | boolean | dateTime | anyURI)

// ABox — Individual
interface IndividualSummary { iri: string; label: string | null; class_iri: string }
interface IndividualDetail {
  iri: string; class_iri: string; label: string | null; comment: string | null
  outgoing: { property: string; value: string; value_type: 'iri' | 'literal' }[]
  incoming: { subject: string; property: string }[]
}
```

### 6-4. API 클라이언트 (`api/client.ts`)

```ts
const BASE = 'http://localhost:8000'

// IRI를 URL 경로에 포함할 때 반드시 사용
export const encodeIRI = (iri: string) => encodeURIComponent(iri)

export async function apiFetch<T>(
  method: string, path: string, body?: unknown
): Promise<T> {
  const res = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}
```

### 6-5. 컴포넌트별 핵심 동작

#### Classes 패널

| 상황 | 동작 |
|------|------|
| DELETE 시 `individual_count > 0` | Modal.confirm("소속 Individual N개도 삭제됩니다") 표시 후 진행 |
| DELETE 시 `individual_count == 0` | Popconfirm 바로 삭제 |
| 행 클릭 | ClassDetail Drawer → `GET /api/tbox/classes/{iri}` → super/sub class, ObjProp, DataProp, 개수 표시 |

#### Object Properties 패널

| 상황 | 동작 |
|------|------|
| Edit 클릭 | `GET /api/tbox/object-properties/{iri}` → characteristics 채운 후 Dialog 오픈 |
| 행 클릭 | ObjPropDetail Drawer → characteristics `<Tag>` 목록 표시 |

#### Data Properties 패널

| 상황 | 동작 |
|------|------|
| Edit 클릭 | `GET /api/tbox/data-properties/{iri}` → functional Switch 채운 후 Dialog 오픈 |
| range 표시 | 목록 응답의 full XSD IRI → shortname 변환하여 표시<br>예: `...XMLSchema#integer` → `integer` |

#### Individuals 패널

| 상황 | 동작 |
|------|------|
| Class 필터 | Select (optional) → `?class_iri=` 파라미터로 목록 재조회 |
| Create | 3단계: ① class·label·comment → ② Data Property 값 (동적 행) → ③ Object Property 관계 (동적 행) |
| Edit | label·comment·Data Property 값만 수정 가능 |
| Edit — OP 관계 | **수정 불가** (PATCH API 미지원) → `<Alert>Object Property 관계 수정은 v02에서 지원</Alert>` |
| 행 클릭 | IndividualDetail Drawer → outgoing Table + incoming Table |

> **Individual Create 필요 데이터**: Classes 목록, Data Properties 목록, Object Properties 목록, Individuals 목록(OP 대상 선택용) — 모두 현재 OOI 기준으로 병렬 fetch

### 6-6. 백엔드 사전 작업

```python
# backend/main.py — CORS 미들웨어 추가
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 7. 핵심 SPARQL 레퍼런스

### Named Graph 목록
```sparql
SELECT DISTINCT ?g WHERE { GRAPH ?g { } }
```

### Named Graph 내 Namespace 추출
```sparql
SELECT DISTINCT ?ns WHERE {
  GRAPH <{graphIRI}> {
    ?s ?p ?o .
    BIND(REPLACE(str(?s), "(#|/)[^#/]*$", "$1") AS ?ns)
  }
}
```

### Namespace → Named Graphs
```sparql
SELECT DISTINCT ?g WHERE {
  GRAPH ?g { ?s ?p ?o . FILTER(STRSTARTS(str(?s), "{baseIRI}")) }
}
```

### Class 목록
```sparql
SELECT ?class ?label ?comment WHERE {
  GRAPH <{graphIRI}> {
    ?class a owl:Class .
    OPTIONAL { ?class rdfs:label ?label }
    OPTIONAL { ?class rdfs:comment ?comment }
    FILTER(STRSTARTS(str(?class), "{baseIRI}"))
  }
}
```

### Class 생성
```sparql
INSERT DATA {
  GRAPH <{graphIRI}> {
    <{classIRI}> a owl:Class ;
      rdfs:label "{label}"@ko ;
      rdfs:comment "{comment}"@ko .
  }
}
```

### Class 삭제 (3단계)
```sparql
-- 1) 소속 Individual rdf:type 제거 (삭제 선택 시 Individual 전체 삭제)
DELETE WHERE { GRAPH <{graphIRI}> { ?ind a <{classIRI}> } }

-- 2) domain/range 참조 제거
DELETE WHERE {
  GRAPH <{graphIRI}> {
    { ?p rdfs:domain <{classIRI}> } UNION { ?p rdfs:range <{classIRI}> }
  }
}

-- 3) Class 선언 삭제
DELETE WHERE { GRAPH <{graphIRI}> { <{classIRI}> ?p ?o } }
```

### Object Property 생성
```sparql
INSERT DATA {
  GRAPH <{graphIRI}> {
    <{propIRI}> a owl:ObjectProperty ;
      rdfs:label "{name}"@ko ;
      rdfs:domain <{domainIRI}> ;
      rdfs:range  <{rangeIRI}> .
    # characteristics 예시
    <{propIRI}> a owl:TransitiveProperty .
  }
}
```

### Data Property 생성
```sparql
INSERT DATA {
  GRAPH <{graphIRI}> {
    <{propIRI}> a owl:DatatypeProperty ;
      rdfs:label "{name}"@ko ;
      rdfs:domain <{domainIRI}> ;
      rdfs:range  xsd:{datatype} .
  }
}
```

### Individual 생성
```sparql
INSERT DATA {
  GRAPH <{graphIRI}> {
    <{indIRI}> a <{classIRI}> ;
      rdfs:label "{label}"@ko ;
      <{dataPropIRI}> "{value}"^^xsd:{datatype} ;
      <{objPropIRI}>  <{targetIndIRI}> .
  }
}
```

### Individual Read (outgoing + incoming)
```sparql
-- outgoing
SELECT ?prop ?value WHERE {
  GRAPH <{graphIRI}> { <{indIRI}> ?prop ?value . FILTER(?prop != rdf:type) }
}

-- incoming
SELECT ?subj ?prop WHERE {
  GRAPH <{graphIRI}> { ?subj ?prop <{indIRI}> }
}
```

### Individual 삭제 (3단계)
```sparql
-- 1) outgoing 관계 삭제
DELETE WHERE { GRAPH <{graphIRI}> { <{indIRI}> ?p ?o } }

-- 2) incoming 관계 삭제
DELETE WHERE { GRAPH <{graphIRI}> { ?s ?p <{indIRI}> } }
-- (선언도 1에서 함께 삭제됨)
```

---

## 8. 구현 단계

> **범례:** ✅ 완료 &nbsp;|&nbsp; 🚧 진행 중 &nbsp;|&nbsp; ⬜ 미착수

---

### 전체 구현 순서

```
v01 Backend  →  v01 Frontend  →  v02 Backend  →  v02 Frontend  →  v03
(✅ 완료)        (✅ 완료)         (✅ 완료)        (✅ 완료)        (✅ 완료)
```

---

### v01 — Core CRUD

**목표:** OOI를 선택하고, TBox를 정의하고, Individual을 투입하는 최소 흐름.

#### v01 Backend ✅

| ID | 기능 | 포함 항목 | 상태 |
|----|------|---------|------|
| v01-A | OOI Navigator | Dataset 목록, Named Graph 목록, Namespace 목록/분류, OOI 선택 | ✅ |
| v01-B | Class CRUD | 목록/생성/수정/삭제, hierarchy 읽기, 관계 탐색 | ✅ |
| v01-C | Object Property CRUD | 목록/생성/수정/삭제, characteristics | ✅ |
| v01-D | Data Property CRUD | 목록/생성/수정/삭제, functional | ✅ |
| v01-E | Individual CRUD | 목록/생성/상세조회(outgoing+incoming)/수정/삭제 | ✅ |

#### v01 Frontend ✅

| ID | 기능 | 포함 항목 | 상태 |
|----|------|---------|------|
| v01-F1 | 프로젝트 설정 | Vite + React + TS + antd 설치, CORS 추가, api/client.ts | ✅ |
| v01-F2 | OOI Navigator | Sider: health check, dataset/graph/ns 선택, OOI Context | ✅ |
| v01-F3 | 앱 레이아웃 | Header + Sider + Tabs 골격, OOI 미설정 가드 | ✅ |
| v01-F4 | Class 패널 | Table + Dialog(create/edit) + Detail Drawer | ✅ |
| v01-F5 | Object Property 패널 | Table + Dialog + Detail Drawer (characteristics) | ✅ |
| v01-F6 | Data Property 패널 | Table + Dialog + Detail Drawer (functional) | ✅ |
| v01-F7 | Individual 패널 | Table(class filter) + CreateDialog(3단계) + EditDialog + Detail Drawer | ✅ |

---

### v02 — 관리 기능 + 고급 TBox + Reasoning

#### v02 Backend ✅

| ID | 기능 | 상태 |
|----|------|------|
| v02-A | Dataset CRUD | ✅ |
| v02-B | Named Graph CRUD | ✅ |
| v02-C | Namespace CRUD (IRI 일괄 치환 포함) | ✅ |
| v02-D | Class hierarchy 편집 (subClassOf 추가/삭제) | ✅ |
| v02-E | Individual Class 마이그레이션 | ✅ |
| v02-F | SPARQL Editor (OOI-scoped query/update) | ✅ |
| v02-G | Reasoning (Jena Reasoner + Materialization 미리보기) | ✅ |
| v02-H | `inverseOf` 설정 (Object Property) | ✅ |
| v02-I | Namespace 복수 선택 | ✅ |
| v02-J | Fuseki Endpoint URL 입력 UI | ✅ |

#### v02 Frontend ✅

| ID | 기능 | 상태 |
|----|------|------|
| v02-F1 | Dataset / Named Graph / Namespace CRUD UI | ✅ |
| v02-F2 | Class hierarchy 편집 UI (subClassOf 트리) | ✅ |
| v02-F3 | Individual Class 마이그레이션 UI | ✅ |
| v02-F4 | Individual Object Property 관계 수정 UI | ✅ |
| v02-F5 | SPARQL Editor UI (OOI-scoped) | ✅ |
| v02-F6 | Reasoning UI (Reasoner 선택 + Materialization 미리보기) | ✅ |
| v02-F7 | `inverseOf` 설정 UI | ✅ |

---

### v03 — 시각화 + 고급 기능

| ID | 기능 | 상태 |
|----|------|------|
| v03-A | SHACL 검증 룰 관리 + 검증 | ✅ |
| v03-B | SPARQL 기반 추론 Rule | ✅ |
| v03-C | Datasource 매핑 + 미리보기 | ✅ |
| v03-D | Universal Namespace import UI | ✅ |

---

---

## v04 — OntologyReasoningEngine (자동 구체화)

> 상세: `plans/plan_v04.md`

### 설계 원칙

추론 로직을 단일 서비스(`reasoning_engine.py`)로 격리한다.
각 서비스는 연산 후 hook을 호출하는 방식으로 연결한다.

```
[services/*]  연산 실행 → reasoning_engine.hook() 호출
[reasoning_engine.py]  RDFS rdfs9 자동 구체화 (materialize)
[Fuseki]  main graph (asserted) + {graph}__inferred (materialized)
```

**지원 규칙:** rdfs9 (subClassOf 계층 타입 전파) + owlrl full_materialize

#### v04 Backend 🚧

| ID | 기능 | 상태 |
|----|------|------|
| v04-A | `reasoning_engine.py` 신규 (get_ancestor_classes, materialize_individual, on_class_hierarchy_change, full_materialize) | 🚧 |
| v04-B | `individual.py` 버그픽스 — incompatible_props Python 집합 연산 교체 | 🚧 |
| v04-C | `individual.py` hook — migrate/create 후 materialize_individual 호출 | 🚧 |
| v04-D | `class_.py` hook — add/removeSuperClass 후 on_class_hierarchy_change 호출 | 🚧 |

#### v04 프로젝트 구조 추가

```
backend/services/
└── reasoning_engine.py   ← 신규: OntologyReasoningEngine
```

---

## 9. 미결 항목

| # | 항목 | 관련 기능 |
|---|------|---------|
| 1 | Data Property domain/range 필수 여부 규칙 명세 | D1 |
| 2 | Individual Class 마이그레이션 상세 절차 | E1 |
| 3 | Universal Namespace import 방식 (owl:imports vs 수동) | A3 |
| 4 | Namespace 수정 시 IRI 일괄 치환 — 트랜잭션 보장 방법 | A3 |
| 5 | Named Graph 삭제 시 다른 Named Graph로 마이그레이션 UI | A2 |
| 6 | SHACL Rule 작성 UI 상세 | v03-A |
| 7 | Datasource 매핑 상세 (어떤 datasource와 어떻게 연결?) | v03-C |
| 8 | Reasoning Rule-based inference — SWRL 작성 UI | v02-G |
| 9 | Class 삭제 시 Individual 마이그레이션 대상 Class 선택 UI | v01-B |
