# OntologyViewer — Plan v04

**Date:** 2026-05-25  
**Status:** 🚧 진행 중  
**Depends on:** plan_v03.md (완료)

---

## 배경 — 왜 v04가 필요한가

현재 시스템은 Fuseki에 **명시적(asserted) 트리플만** 저장한다.
OWL/RDFS의 핵심 추론 규칙이 자동 적용되지 않아 두 가지 버그가 발생한다.

### 버그 1: 비호환 Property 체크가 틀림

```sparql
-- _Q_INCOMPATIBLE_PROPS 내부
FILTER NOT EXISTS {
  <Novel> rdfs:subClassOf* <Book> .   ← GRAPH 컨텍스트 밖에서 평가됨
}
```

Fuseki에서 `FILTER NOT EXISTS` 내부의 property path는 기본 그래프에서 평가되어
실제로는 호환인 property들이 비호환으로 잘못 표시된다.

**예:** `Novel subClassOf Book`, `title domain=Book`
→ Novel 개인 마이그레이션 시 title이 비호환으로 표시됨 (오보)

### 버그 2: Migration 후 타입 단절

```
Before:  Book_OWLPrimer  rdf:type Book    ✓
After:   Book_OWLPrimer  rdf:type Novel   ← Book 타입 사라짐
         Book_OWLPrimer  title "..."      domain=Book → 의미적 단절
```

`Novel rdfs:subClassOf Book`이 있으므로 Novel 개인은 암묵적으로 Book이어야 하지만
Fuseki는 추론하지 않으므로 `rdf:type Book`이 사라진다.

---

## 핵심 설계 결정 (6개월 후 관점)

### OntologyReasoningEngine — 단일 책임 서비스

추론 로직이 individual.py, class_.py, object_property.py 등에 분산되면
6개월 후 유지보수 비용이 폭발적으로 증가한다.

```
[각 서비스]  연산 실행 → reasoning_engine.hook() 호출
                               ↓
[reasoning_engine.py]  단일 책임으로 모든 추론 처리
                               ↓
[Fuseki]  main graph + {graph}__inferred graph
```

### 이중 그래프 전략

| 그래프 | 내용 | 설명 |
|--------|------|------|
| `{graph}` (main) | 사용자가 명시한 트리플 | asserted |
| `{graph}__inferred` | 추론된 트리플 | materialized |

**장점:**
- `removeSuperClass` 후 inferred 트리플만 선택적 제거 가능
- 추론 결과 재계산이 깨끗함 (inferred 그래프 clear → 재계산)
- main 그래프 쿼리는 기존 코드 그대로 유지
- 향후 "reasoning view" (UNION 쿼리)로 확장 용이

**현재 쿼리 영향:**
- Individual 목록/상세: main 그래프만 사용 (변경 없음)
- Class 개수: main 그래프만 (변경 없음)
- 비호환 체크: Python 집합 연산으로 교체 (SPARQL 제거)
- SHACL 검증: 필요 시 inferred 포함 (향후 확장)

### 지원 추론 규칙

| RDFS 규칙 | 내용 | 구현 |
|-----------|------|------|
| rdfs9 | `X rdf:type C, C rdfs:subClassOf D → X rdf:type D` | SPARQL |
| rdfs11 | `A subClassOf B, B subClassOf C → A subClassOf C` | SPARQL property path |
| rdfs2/3 | `P domain D, X P Y → X rdf:type D` | owlrl full_materialize |

---

## OntologyReasoningEngine API

```python
# backend/services/reasoning_engine.py

def get_ancestor_classes(dataset, graph, class_iri) -> list[str]:
    """rdfs:subClassOf+ 경로로 모든 상위 클래스 반환 (main 그래프)."""

def materialize_individual(dataset, graph, ind_iri) -> list[str]:
    """
    개인의 asserted rdf:type 기반으로 ancestor types를 __inferred에 추가.
    Returns: 새로 추가된 type IRI 목록.
    """

def clear_inferred_types(dataset, graph, ind_iri) -> None:
    """개인의 inferred rdf:type 트리플을 __inferred 그래프에서 제거."""

def on_class_hierarchy_change(dataset, graph, changed_class_iri) -> None:
    """
    addSuperClass / removeSuperClass 후 호출.
    changed_class의 모든 직접 개인 재구체화.
    """

def full_materialize(dataset, graph) -> dict:
    """
    owlrl RDFS_Semantics 기반 전체 그래프 재구체화.
    __inferred 그래프를 초기화 후 재계산.
    Returns: {"added": N}
    """
```

### 각 서비스 Hook 연결

```python
# individual.py
create_individual(...)
    → sparql_update(INSERT)
    → reasoning_engine.materialize_individual(ind_iri)      ← NEW

migrate_individual_class(...)
    → sparql_update(CHANGE TYPE)
    → reasoning_engine.clear_inferred_types(ind_iri)
    → reasoning_engine.materialize_individual(ind_iri)      ← NEW

# class_.py
add_super_class(child, parent)
    → sparql_update(INSERT subClassOf)
    → reasoning_engine.on_class_hierarchy_change(child)     ← NEW

remove_super_class(child, parent)
    → sparql_update(DELETE subClassOf)
    → reasoning_engine.on_class_hierarchy_change(child)     ← NEW

# incompatible props 체크: SPARQL → Python 집합 연산
get_incompatible_properties(ind_iri, new_class)
    → ancestors = get_ancestor_classes(new_class) | {new_class}
    → Python: prop.domain NOT IN ancestors → incompatible   ← FIXED
```

---

## 테스트 시나리오 (10개)

> **전제 데이터** (Stage 3~4에서 구축한 Book Ontology)
> - Graph: `http://example.org/bookOntology`
> - Classes: `Book`, `Novel` (subClassOf Book), `TextBook` (subClassOf Book), `Author`, `Genre`
> - Properties: `title` (domain=Book, range=string), `isbn` (domain=Book), `pageCount` (domain=Book), `hasGenre` (domain=Book, range=Genre), `writtenBy` (domain=Book, range=Author)
> - Individuals: `Book_OWLPrimer` (class=Book, title/isbn/pageCount/hasGenre/writtenBy 있음)

### TC-01: Individual 생성 시 ancestor type 자동 구체화

```
Action: createIndividual(class=Novel, label="Fellowship of the Ring")
Expected:
  - main graph: rdf:type Novel ✓
  - __inferred:  rdf:type Book ✓
  - title/isbn/pageCount 값 추가 가능 (domain=Book 호환)
```

### TC-02: incompatibleProps 수정 — Novel은 Book 속성과 호환

```
Action: previewClassMigrate(Book_OWLPrimer, old=Book, new=Novel)
Expected:
  - ancestors(Novel) = {Book}
  - title domain=Book ∈ ancestors → 호환
  - isbn domain=Book ∈ ancestors → 호환
  - incompatible_properties = []    ← 버그 수정 확인
```

### TC-03: Book → Novel 마이그레이션 후 Book 타입 유지

```
Action: migrateIndividualClass(Book_OWLPrimer, Book → Novel, keep)
Expected:
  - main graph: rdf:type Novel ✓ (Book 제거됨)
  - __inferred:  rdf:type Book ✓ (재구체화)
  - title/isbn/pageCount/hasGenre/writtenBy 값 모두 유지
  - deleted_properties = []
```

### TC-04: Novel → TextBook 마이그레이션 (호환)

```
Action: migrateIndividualClass(Book_OWLPrimer, Novel → TextBook, keep)
Expected:
  - ancestors(TextBook) = {Book}
  - incompatible_properties = []
  - main graph: rdf:type TextBook ✓
  - __inferred:  rdf:type Book ✓
```

### TC-05: 3-depth 계층 — SciFiNovel 생성 후 전체 ancestor 구체화

```
Setup: addSuperClass(SciFiNovel, Novel)  [SciFiNovel subClassOf Novel subClassOf Book]
Action: createIndividual(class=SciFiNovel, label="Dune")
Expected:
  - main graph: rdf:type SciFiNovel ✓
  - __inferred:  rdf:type Novel ✓
  - __inferred:  rdf:type Book ✓
  - ancestors(SciFiNovel) = {Novel, Book}
```

### TC-06: addSuperClass 후 기존 개인 타입 갱신

```
Setup: createIndividual(class=Author, label="Isaac Asimov")
Action: addSuperClass(Author, Book)   [Author가 갑자기 Book의 하위]
Expected:
  - Author 개인들 __inferred에 rdf:type Book 추가
  - on_class_hierarchy_change(Author) 실행됨
```

### TC-07: removeSuperClass 후 inferred type 제거

```
Setup: Novel subClassOf Book (기존)
       Novel 개인 Fellowship (main: Novel, inferred: Book)
Action: removeSuperClass(Novel, Book)
Expected:
  - Novel rdfs:subClassOf Book 트리플 삭제
  - Fellowship __inferred에서 rdf:type Book 제거
  - on_class_hierarchy_change(Novel) 실행됨
  - ancestors(Novel) = {} (빈 집합)
```

### TC-08: removeSuperClass 후 비호환 체크 변화 확인

```
Setup: (TC-07 이후) Novel subClassOf Book 없음
Action: previewClassMigrate(어떤_Novel_개인, old=Novel, new=Novel)
Expected:
  - ancestors(Novel) = {} → title domain=Book ∉ {} → 비호환
  - incompatible_properties = [title, isbn, pageCount, hasGenre, writtenBy]
```

### TC-09: full_materialize — 전체 그래프 일관성 재구체화

```
Setup: 다양한 부분 구체화 상태
Action: full_materialize(dataset, graph)
Expected:
  - __inferred 그래프 초기화
  - owlrl RDFS_Semantics 기반 재계산
  - 모든 Novel/TextBook/SciFiNovel 개인의 ancestor types 재삽입
  - {"added": N} 반환
```

### TC-10: 비호환 delete 옵션으로 마이그레이션

```
Action: migrateIndividualClass(Book_OWLPrimer, Novel → Author, delete)
Expected:
  - ancestors(Author) = {}
  - incompatible_properties = [title, isbn, pageCount, hasGenre, writtenBy]
  - migration 실행 → 비호환 props 트리플 모두 삭제
  - deleted_properties = [title, isbn, pageCount, hasGenre, writtenBy]
  - main graph: rdf:type Author ✓
  - __inferred: (Author의 ancestor 없으므로 빈 상태)
```

---

## 구현 순서

| 스텝 | 대상 | 내용 |
|------|------|------|
| S1 | `services/reasoning_engine.py` (신규) | get_ancestor_classes, materialize_individual, clear_inferred_types, on_class_hierarchy_change, full_materialize |
| S2 | `services/individual.py` | get_incompatible_properties → Python 집합 연산 교체, migrate_individual_class + create_individual hook 추가 |
| S3 | `services/class_.py` | add_super_class + remove_super_class hook 추가 |
| S4 | 통합 테스트 TC-01 ~ TC-10 검증 | 실제 Fuseki 서버 대상 |
| S5 | master_plan.md 갱신 | v04 완료 표시 |

---

## 파일 변경 목록

| 파일 | 변경 유형 | 내용 |
|------|-----------|------|
| `backend/services/reasoning_engine.py` | 신규 | OntologyReasoningEngine 로직 전체 |
| `backend/services/individual.py` | 수정 | 버그픽스 + hook 2개 |
| `backend/services/class_.py` | 수정 | hook 2개 |
| `plans/master_plan.md` | 수정 | v04 항목 추가 |

---

## 미결 항목 (v05 이후)

| # | 항목 |
|---|------|
| 1 | rdfs2/3 (domain/range 기반 타입 추론) — full_materialize에서 owlrl로 커버 |
| 2 | owl:equivalentClass 지원 |
| 3 | __inferred 그래프를 UI에서 "추론 뷰"로 조회하는 기능 |
| 4 | Individual 목록 쿼리에서 UNION (main + inferred) 지원 |
| 5 | Class 삭제 시 inferred 타입 정리 |
