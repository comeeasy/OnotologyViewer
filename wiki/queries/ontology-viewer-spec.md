# OntologyViewer — 기능 명세

**Date:** 2026-05-24  
**Source:** `raw/spec.md`  
**Status:** In Progress  
**Related:** [[data-model]], [[class]], [[object-property]], [[data-property]], [[individual]], [[reasoning]], [[apache-jena-fuseki]]

---

## 1. 데이터 계층 구조

```
Dataset
└── Named Graph          ← 온톨로지 구분 축 1
    └── Namespace        ← 온톨로지 구분 축 2 (= Base IRI = prefix)
```

- **OOI (Ontology of Interest)**: Namespace + Named Graph 조합으로 선택된 온톨로지 단위 → [[data-model]]
- 백엔드: Apache Jena Fuseki → [[apache-jena-fuseki]]

---

## 2. Namespace

- Namespace = Base IRI (prefix의 기저가 되는 IRI)
- 분류: **Custom** (직접 정의) / **Universal** (import한 표준, e.g. rdf:, owl:, xsd:)

### 기능
- 모든 prefix(namespace) 리스트 조회
- Custom / Universal 구분 표시
- 복수 namespace 동시 선택 가능
- 선택한 Namespace ↔ Named Graph 상호 포함 관계 조회

### CRUD
| 작업 | 내용 |
|------|------|
| **Create** | dataset 선택 → prefix 작성 → base IRI 작성 → 유형(Custom/Universal) 선택 |
| **Update** | prefix 수정 (IRI 일괄 치환) / base IRI 수정 (IRI 일괄 치환) — 모두 optional |
| **Delete** | 해당 namespace 사용 IRI 전체 처리(삭제 or 마이그레이션) → namespace 선언 삭제 |

---

## 3. Named Graph

### CRUD
| 작업 | 내용 |
|------|------|
| **Create** | dataset 선택 → Named Graph IRI 작성 → rdfs:label (optional) → rdfs:comment (optional) |
| **Update** | rdfs:label / rdfs:comment 수정 — 모두 optional |
| **Delete** | 포함 트리플 전체 처리(삭제 or 마이그레이션) → Named Graph 선언 삭제 |

---

## 4. Dataset

### CRUD
| 작업 | 내용 |
|------|------|
| **Create** | dataset 명 작성 → dataset IRI 작성 |
| **Update** | dataset 명 / IRI 수정 — 모두 optional |
| **Delete** | 포함 Named Graph 전체 처리(삭제 or 마이그레이션) → Dataset 선언 삭제 |

---

## 5. 온톨로지 구조: TBox / ABox → [[data-model]]

### TBox (스키마)
- **Class**: IRI 보유. 계층 구조(hierarchy) 지원 → [[class]]
- **Object Property**: Class ↔ Class 관계. domain + range 필수 → [[object-property]]
- **Data Property**: Class ↔ Literal 관계. domain(Class) + range(xsd datatype) → [[data-property]]

### ABox (인스턴스)
- **Individual**: 각 Class의 인스턴스. IRI 보유 → [[individual]]
- Individual은 소속 Class의 Property를 가질 수 있음
  - Object Property: Individual ↔ Individual (자기 자신 포함)
  - Data Property: Individual → Literal

---

## 6. OOI 기반 기능

| 기능 | 내용 |
|------|------|
| **SPARQL CRUD** | 선택된 OOI 범위 내에서 SPARQL을 통해 Create / Read / Update / Delete |
| **Reasoning** | 선택된 OOI 범위 내에서 Jena 내장 Reasoner 실행 → [[reasoning]] |

---

## 7. Class CRUD → [[class]]

### Create
```
a. Dataset 선택
b. Namespace 선택  ┐ OOI 선택
c. Named Graph 선택 ┘
d. rdfs:label 작성
e. rdfs:comment 작성
f. Data Properties 생성
g. Object Properties 생성
```

### Update (모두 optional)
- rdfs:label 수정 / rdfs:comment 수정 / Object Property 수정 / Data Property 수정

### Delete
```
a. 소속 Individuals 처리 — 삭제 또는 다른 Class로 마이그레이션
b. 연결 관계 제거 — domain/range 제거, 모든 property 관계 제거
c. Class 선언문 삭제
```

### Read
| 뷰 | 내용 |
|----|------|
| Class hierarchy 탐색 | subClassOf 기반 계층 시각화 |
| 관계 탐색 | domain, range 기반 Object Property 시각화 |
| Data Property 목록 | 소속 Individuals 통계값 포함 |
| SHACL 검증 룰 시각화 | 적용된 SHACL shape 표시 |
| Rule 시각화 | 추론 규칙 표시 |
| Datasource 매핑 | 각 datasource ↔ class 매핑 관계 |

---

## 8. Object Property CRUD → [[object-property]]

### Create
```
a. Dataset 선택
b. OOI 선택
c. property 명 작성 (camelCase)
d. domain 설정 (Class)
e. range 설정 (Class)
f. property characteristics 설정
   (Functional, InverseFunctional, Transitive, Symmetric, Asymmetric, Reflexive, Irreflexive)
```

### Update (모두 optional)
- property 명 수정 / domain 수정 / range 수정 / characteristics 수정

### Delete
```
a. 해당 property를 사용하는 모든 Individual 간 관계 삭제
b. domain, range 선언 삭제
c. property 선언문 삭제
```

---

## 9. Data Property CRUD → [[data-property]]

### Create
```
a. Dataset 선택
b. OOI 선택
c. property 명 작성 (camelCase)
d. domain 설정 (Class)
e. range 설정 (xsd datatype: string, integer, float, boolean, dateTime, anyURI 등)
f. property characteristics 설정 (Functional만 적용 가능)
```

### Update (모두 optional)
- property 명 수정 / domain 수정 / range(datatype) 수정 / characteristics 수정

### Delete
```
a. 해당 property를 사용하는 모든 Individual의 값 삭제
b. property 선언문 삭제
```

---

## 10. Individual CRUD → [[individual]]

### Create
```
a. Dataset 선택
b. OOI 선택
c. Class 선택 (소속 Class)
d. IRI 작성 (또는 자동 생성)
e. rdfs:label 작성
f. rdfs:comment 작성 (optional)
g. data property 값 입력
h. object property 관계 설정 (대상 Individual 선택)
```

### Read
- 소속 Class 확인
- data property 값 목록
- object property 관계 목록 (outgoing + incoming 모두)
- SHACL 검증 결과

### Update (모두 optional)
- rdfs:label / rdfs:comment 수정
- data property 값 수정 / 추가 / 삭제
- object property 관계 수정 / 추가 / 삭제
- 소속 Class 변경 (마이그레이션)

### Delete
```
a. 참여하는 모든 object property 관계 삭제 (outgoing + incoming)
b. 모든 data property 값 삭제
c. Individual 선언문 삭제
```

---

## 11. Reasoning → [[reasoning]]

```
a. OOI 선택
b. Reasoning 유형 선택
   - Class hierarchy inference (subClassOf 추론)
   - Property inference (domain, range 기반 타입 추론)
   - Consistency checking (온톨로지 무결성 검사)
   - Rule-based inference (SWRL / SPARQL rules)
c. Reasoner 선택 (Jena 내장)
   - OWL_DL_MEM_RULE: OWL DL + 추론 규칙 (일반 권장)
   - OWL_MEM_RULE: OWL Full + 추론 규칙
   - OWL_MEM_TRANS_INF: Transitive inference만
   - RDFS: RDFS 추론만
d. 결과 미리보기 (미저장)
   - 추론된 트리플 목록 (추가될 triples)
   - Consistency 여부 (consistent / inconsistent)
   - Inconsistency 원인 설명 (explanation)
e. 사용자 검토 후 Materialization 결정
   - 저장: 추론 결과를 트리플로 OOI에 반영
   - 취소: 추론 결과 폐기, OOI 변경 없음
```

---

## 미정의 항목 (TODO)

- [ ] Data Property의 domain/range 필수 여부 규칙
- [ ] Individual CRUD — Class 변경(마이그레이션) 상세 절차
- [ ] Universal namespace import 방식
- [ ] SHACL Rule 작성 UI
- [ ] Datasource 매핑 상세
- [ ] SPARQL 편집기 UI 상세
