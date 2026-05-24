# OntologyViewer — 구현 계획 v02

**Date:** 2026-05-25 (updated)  
**Scope:** 관리 기능 + 고급 TBox + Reasoning  
**Prerequisite:** v01 완료 (Backend ✅ · Frontend ✅)  
**Status:** ✅ Backend + Frontend 모두 완료 (190/190 통합 테스트 통과)

---

## 목차

1. [v02 범위 요약](#1-v02-범위-요약)
2. [v01에서 이월된 항목](#2-v01에서-이월된-항목)
3. [v02-A Dataset CRUD](#3-v02-a-dataset-crud)
4. [v02-B Named Graph CRUD 고도화](#4-v02-b-named-graph-crud-고도화)
5. [v02-C Namespace CRUD](#5-v02-c-namespace-crud)
6. [v02-D Class 계층 편집](#6-v02-d-class-계층-편집)
7. [v02-E Individual Class 마이그레이션](#7-v02-e-individual-class-마이그레이션)
8. [v02-F SPARQL Editor](#8-v02-f-sparql-editor)
9. [v02-G Reasoning](#9-v02-g-reasoning)
10. [v02-H inverseOf 설정](#10-v02-h-inverseof-설정)
11. [구현 순서](#11-구현-순서)

---

## 1. v02 범위 요약

| ID | 기능 | 난이도 |
|----|------|--------|
| v02-A | Dataset CRUD (생성·수정·삭제) | 중 |
| v02-B | Named Graph CRUD 고도화 (label/comment 수정) | 하 |
| v02-C | Namespace CRUD (IRI 일괄 치환 포함) | 상 |
| v02-D | Class 계층 편집 (subClassOf 추가/삭제) | 중 |
| v02-E | Individual Class 마이그레이션 | 중 |
| v02-F | SPARQL Editor (OOI-scoped) | 중 |
| v02-G | Reasoning (Jena Reasoner + Materialization) | 상 |
| v02-H | inverseOf 설정 (Object Property) | 하 |
| v02-I | Namespace 복수 선택 (v01 이월) | 중 |
| v02-J | Fuseki endpoint URL 입력 UI (v01 이월) | 하 |

---

## 2. v01에서 이월된 항목

### v02-I. Namespace 복수 선택

**배경:** v01 plan_v01.md에서 "Named Graph + Namespace 체크박스 복수 선택"으로 정의했으나
현재 모든 API가 `namespace: str` (단일)로 구현되어 있어 단일 선택으로 축소됨.

**필요 변경:**
- 백엔드 API: `namespace` 쿼리 파라미터 복수 허용 (`namespace=A&namespace=B`)
  - SPARQL FILTER: `FILTER(STRSTARTS(..., "A") || STRSTARTS(..., "B"))`
- OOIContext: `namespace: string | null` → `namespaces: string[]`
- OOINavigator: Select → Checkbox.Group (custom namespace 복수 선택)
- 모든 패널 API 호출: namespace 배열 전달

**영향 범위:** 전체 API, Context, 모든 패널 — 변경 범위 크므로 v02에서 일괄 처리.

---

### v02-J. Fuseki Endpoint URL 입력 UI

**배경:** 현재 endpoint는 `config.py` 환경변수(`FUSEKI_BASE_URL`)로만 설정 가능.
UI에서 변경할 수 없어 Docker Compose 외 환경에서는 설정 불편.

**필요 변경:**
- 백엔드: `PATCH /api/config/fuseki` — endpoint URL, user, password 변경
- 프론트엔드 Navigator: 연결 실패 시 "연결 설정" 버튼 → Modal (URL/user/password 입력)
- 보안 고려: password는 마스킹, 변경 시 즉시 health check 재시도

---

## 3. v02-A Dataset CRUD

### 기능
| 기능 | API | 비고 |
|------|-----|------|
| 목록 조회 | `GET /api/datasets` | v01 구현 완료 |
| 생성 | `POST /api/datasets` | Fuseki Admin `POST /$/datasets` |
| 삭제 | `DELETE /api/datasets/{name}` | Fuseki Admin `DELETE /$/datasets/{name}` |

### 삭제 처리 절차
```
1. 포함된 Named Graph 목록 확인
2. 확인 Modal: "N개 Named Graph, M개 트리플이 삭제됩니다"
3. Fuseki Admin DELETE /$/datasets/{name}
```

### 성공 기준
- [x] Dataset을 생성하면 Fuseki에 TDB2 dataset이 등록된다
- [x] Dataset 삭제 시 포함 데이터 현황이 표시된다
- [x] 삭제 후 Navigator Dataset 목록에서 제거된다

---

## 4. v02-B Named Graph CRUD 고도화

### 현황 (v01에서 구현)
- `POST /api/datasets/{ds}/graphs` — 생성 (owl:Ontology + label 삽입)
- `DELETE /api/datasets/{ds}/graphs?graph=` — 삭제

### 추가 필요
| 기능 | API | 내용 |
|------|-----|------|
| label 수정 | `PATCH /api/datasets/{ds}/graphs` | rdfs:label DELETE/INSERT |
| comment 수정 | `PATCH /api/datasets/{ds}/graphs` | rdfs:comment DELETE/INSERT |
| 트리플 수 조회 | `GET /api/datasets/{ds}/graphs?graph=` | `SELECT (COUNT(*) AS ?n) WHERE { GRAPH <g> { ?s ?p ?o } }` |

### 성공 기준
- [x] Named Graph의 label/comment를 수정할 수 있다
- [x] Navigator에서 Named Graph의 트리플 수가 표시된다

---

## 5. v02-C Namespace CRUD

### 목표
Namespace(base IRI)를 명시적으로 관리하고, base IRI 변경 시 해당 namespace의 모든 IRI를 일괄 치환한다.

### 기능
| 기능 | 내용 |
|------|------|
| 선언 | `<ns_iri> a owl:Ontology ; vann:preferredNamespacePrefix "prefix"` 트리플 삽입 |
| prefix 수정 | prefix 선언 트리플 교체 |
| base IRI 변경 | IRI 일괄 치환 (아래 참조) |
| 삭제 | 해당 namespace IRI로 시작하는 모든 subject 트리플 삭제 |

### IRI 일괄 치환 알고리즘
```sparql
-- 1. 해당 namespace의 모든 subject IRI 수집
SELECT ?s WHERE {
  GRAPH <{graph}> { ?s ?p ?o . FILTER(STRSTARTS(str(?s), "{old_ns}")) }
}

-- 2. 각 subject에 대해: 새 IRI 생성 → 트리플 복사 → 구 트리플 삭제
--    subject가 object로 등장하는 경우도 동일 처리

-- 3. Fuseki는 단일 트랜잭션 UPDATE 미지원 → 서버 측 Python으로 처리
--    실패 시 중간 상태 발생 가능 → "백업 후 진행" 경고 표시
```

> ⚠️ IRI 치환은 되돌릴 수 없음. 실행 전 그래프 export(TTL) 다운로드 권장.

### 성공 기준
- [x] Namespace prefix를 수정할 수 있다
- [x] base IRI 변경 시 영향받는 트리플 수가 미리 표시된다
- [x] IRI 치환 후 모든 triple이 새 namespace로 갱신된다

---

## 6. v02-D Class 계층 편집

### 현황 (v01)
ClassDetail Drawer에서 super_classes / sub_classes를 Tag로 표시 (읽기 전용).

### 추가 기능
| 기능 | API | SPARQL |
|------|-----|--------|
| subClassOf 추가 | `POST /api/tbox/classes/{iri}/super-classes` | `INSERT DATA { <child> rdfs:subClassOf <parent> }` |
| subClassOf 삭제 | `DELETE /api/tbox/classes/{iri}/super-classes/{parent}` | `DELETE DATA { <child> rdfs:subClassOf <parent> }` |

### UI
- ClassDetail Drawer에 "계층 편집" 탭 추가
- 상위 Class 추가: Select(현재 OOI Classes) + 추가 버튼
- 상위 Class 삭제: 각 항목 옆 ✕ 버튼

### 성공 기준
- [x] subClassOf 관계를 추가/삭제할 수 있다
- [x] 순환 참조(A subClassOf B, B subClassOf A) 방지 검사
- [x] ClassDetail에서 변경 결과가 즉시 반영된다

---

## 7. v02-E Individual Class 마이그레이션

### 목표
Individual의 rdf:type을 다른 Class로 변경한다.
Data Property 값과 Object Property 관계는 유지하되, 새 Class에 존재하지 않는 Property는 처리 옵션 제공.

### 처리 절차
```
1. 새 Class 선택
2. 현재 Individual의 DP/OP 목록과 새 Class의 DP/OP 비교
3. 호환되지 않는 Property 처리 선택:
   - 유지 (값 보존, 단 OWL 비준수)
   - 삭제 (해당 트리플 제거)
4. rdf:type 트리플 교체:
   DELETE { <ind> a <old_class> }
   INSERT { <ind> a <new_class> }
```

### API
```
PATCH /api/abox/individuals/{iri}/class
body: { dataset, graph, new_class_iri, incompatible_props: "keep" | "delete" }
```

### 성공 기준
- [x] Individual의 Class를 다른 Class로 변경할 수 있다
- [x] 비호환 Property 처리 옵션이 표시된다
- [x] 마이그레이션 후 Individual 상세에 새 Class가 반영된다

---

## 8. v02-F SPARQL Editor

### 목표
현재 OOI(Named Graph) 범위 내에서 사용자가 직접 SPARQL을 실행할 수 있다.

### 기능
| 기능 | API | 비고 |
|------|-----|------|
| SELECT / ASK | `POST /api/sparql/query` | OOI Named Graph 자동 적용 |
| INSERT / DELETE | `POST /api/sparql/update` | OOI Named Graph 자동 적용 |

### Named Graph 자동 적용
```sparql
-- 사용자 입력:
SELECT ?s ?p ?o WHERE { ?s ?p ?o }

-- 서버에서 자동 변환:
SELECT ?s ?p ?o WHERE { GRAPH <{ooi_graph}> { ?s ?p ?o } }
```

### UI
- 메인 Tabs에 "SPARQL Editor" 탭 추가
- 코드 에디터 (textarea, monospace)
- 실행 버튼 → 결과 Table (SELECT) / 성공/실패 메시지 (UPDATE/ASK)
- 쿼리 히스토리 (localStorage 최근 10개)

### 성공 기준
- [x] SELECT 결과가 Table로 표시된다
- [x] ASK 결과가 true/false로 표시된다
- [x] UPDATE 실행 후 성공 여부가 표시된다
- [x] OOI Named Graph가 자동으로 적용된다

---

## 9. v02-G Reasoning

### 목표
Jena Reasoner를 이용해 추론을 실행하고, 결과(추론된 트리플)를 미리보기 후 저장(Materialization) 여부를 결정한다.

### Reasoner 종류
| Reasoner | 설명 | 추천 |
|----------|------|------|
| `OWL_DL_MEM_RULE` | OWL DL + Rule 기반 완전 추론 | ✅ 권장 |
| `OWL_MEM_RULE` | OWL Full + Rule | 느림, 비추천 |
| `OWL_MEM_TRANS_INF` | Transitive + Class hierarchy | 가벼운 추론 |
| `RDFS` | RDFS 추론만 | 최소 추론 |

### 처리 흐름
```
1. Reasoner 선택
2. POST /api/reasoning/run { dataset, graph, reasoner }
   → 백엔드: SPARQL CONSTRUCT로 그래프 추출 → pyoxigraph or rdflib로 추론 실행
   → 추론된 트리플 목록 반환 (최대 1000개 미리보기)
3. 결과 미리보기 Table 표시
4. [저장] → POST /api/reasoning/materialize { triples, dataset, graph }
   → 추론 결과를 별도 Named Graph(예: {graph}/inferred)에 INSERT
5. [취소] → 저장 안 함
```

### 백엔드 기술
- `pyoxigraph` (Rust 바인딩, rdflib 대비 10~100x 빠름) 사용
- Fuseki에서 TTL export → pyoxigraph 추론 → 결과 트리플 반환

### 성공 기준
- [x] Reasoner를 선택하고 추론을 실행할 수 있다
- [x] 추론된 트리플이 미리보기로 표시된다
- [x] Materialization 후 추론 결과가 Fuseki에 저장된다
- [x] 일관성 검사(Consistency Check) 결과가 표시된다

---

## 10. v02-H inverseOf 설정

### 목표
Object Property 간 `owl:inverseOf` 관계를 선언한다.

### 기능
```sparql
-- inverseOf 추가
INSERT DATA {
  GRAPH <{graph}> { <{prop_a}> owl:inverseOf <{prop_b}> }
}

-- inverseOf 삭제
DELETE DATA {
  GRAPH <{graph}> { <{prop_a}> owl:inverseOf <{prop_b}> }
}
```

### API
```
POST   /api/tbox/object-properties/{iri}/inverse    body: { dataset, graph, inverse_iri }
DELETE /api/tbox/object-properties/{iri}/inverse    ?dataset&graph&inverse_iri=
```

### UI
- ObjPropDetail Drawer에 "inverseOf" 섹션 추가
- 현재 inverseOf 관계 표시 + 추가/삭제

### 성공 기준
- [x] Object Property에 inverseOf 관계를 추가/삭제할 수 있다
- [x] ObjPropDetail에서 inverseOf 관계가 표시된다

---

## 11. 구현 순서

```
v02-J (Fuseki URL UI)       ← 독립적, 빠름
v02-B (Named Graph 고도화)  ← v01 연장선
v02-H (inverseOf)           ← 독립적, 빠름
v02-D (Class 계층 편집)     ← ClassDetail 확장
v02-A (Dataset CRUD)        ← Admin API 활용
v02-I (Namespace 복수 선택) ← 전체 영향, 신중하게
v02-C (Namespace CRUD)      ← v02-I 이후
v02-E (Individual 마이그레이션) ← v02-D 이후
v02-F (SPARQL Editor)       ← 독립적
v02-G (Reasoning)           ← pyoxigraph 도입 필요, 마지막
```
