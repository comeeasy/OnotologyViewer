# OntologyViewer — Plan v03

**Date:** 2026-05-25 (updated)  
**Status:** ✅ 완료 (190/190 통합 테스트 통과)  
**Depends on:** plan_v02.md (완료)

### 구현 완료 요약
- v03-A: SHACL 검증 룰 관리 + Individual 검증 + ClassDetail SHACL 탭 ✅
- v03-B: SPARQL 기반 추론 Rule (CRUD + apply + materialize) ✅
- v03-C: Datasource 매핑 (CRUD + ClassMapping + PropertyMapping + 미리보기) ✅
- v03-D: Universal Namespace import UI ✅
- 추가: Individual Edit 시 datatype 실제 값 반영 (query_with_types 활용)
- 추가: ClassDetail에 SHACL/Rules/Datasource 탭 추가
- 추가: Class 삭제 시 Individual migrate 모달 (UI + 백엔드)
- 추가: nginx proxy_pass URI 정규화 버그 수정 (IRI double-slash 문제)

---

## 목표

v03은 시각화 및 고급 기능을 추가한다. 각 스텝은:
1. 실데이터 기반 통합 테스트 10개 작성
2. 기능 구현
3. 테스트 전체 통과 확인
4. 스텝별 git commit

---

## 구현 순서

| 스텝 | 기능 | 우선순위 |
|------|------|---------|
| v03-A | SHACL 검증 룰 관리 + 검증 | 1 |
| v03-B | SPARQL 기반 추론 Rule | 2 |
| v03-C | Datasource 매핑 | 3 |
| v03-D | Universal Namespace import UI | 4 |

---

## v03-A: SHACL 검증 룰 시각화

### 개요

- SHACL(Shapes Constraint Language) shapes를 OOI Named Graph의 서브그래프(`{graph}/shacl`)에 저장
- pyshacl 라이브러리로 검증 실행
- Class별 NodeShape / PropertyShape 관리
- Individual 단위 검증 결과 조회

### 데이터 모델

```turtle
# NodeShape — 클래스를 타겟으로 함
<{shape_iri}> a sh:NodeShape ;
    sh:targetClass <{class_iri}> ;
    rdfs:label "{label}" ;
    sh:property <{prop_shape_iri}> .

# PropertyShape — 프로퍼티 제약 정의
<{prop_shape_iri}> a sh:PropertyShape ;
    sh:path <{property_iri}> ;
    sh:datatype xsd:{datatype} ;     # 선택
    sh:minCount {n} ;                # 선택
    sh:maxCount {n} ;                # 선택
    sh:minLength {n} ;               # 선택
    sh:maxLength {n} ;               # 선택
    sh:pattern "{regex}" ;           # 선택
    rdfs:label "{label}" .
```

### REST API

```
GET    /api/shacl/shapes                         # 목록 ?dataset&graph
POST   /api/shacl/shapes                         # NodeShape 생성
GET    /api/shacl/shapes/{iri:path}              # 상세 (PropertyShape 포함)
DELETE /api/shacl/shapes/{iri:path}              # 삭제 (PropertyShape 연쇄 삭제)
POST   /api/shacl/shapes/{iri:path}/properties   # PropertyShape 추가
DELETE /api/shacl/shapes/{iri:path}/properties/{prop_iri:path}  # PropertyShape 삭제

POST   /api/shacl/validate                        # 그래프 전체 검증
POST   /api/shacl/validate/individual             # Individual 단위 검증
```

### 테스트 시나리오 (10개)

| TC | 내용 |
|----|------|
| TC01 | NodeShape 생성 (targetClass 지정) → 201, shape IRI 반환 |
| TC02 | NodeShape 목록 조회 → shapes 리스트 |
| TC03 | NodeShape 상세 조회 (shape IRI) → NodeShape + PropertyShapes |
| TC04 | PropertyShape 추가 (minCount=1, sh:path=hasName) |
| TC05 | PropertyShape 삭제 |
| TC06 | NodeShape 삭제 (연결 PropertyShape 연쇄 삭제) |
| TC07 | 적합한 그래프 검증 → conforms=True |
| TC08 | 위반 그래프 검증 → conforms=False, violations 목록 |
| TC09 | Individual 단위 검증 → 해당 individual 위반만 필터 |
| TC10 | 존재하지 않는 Shape 조회 → 404 |

---

## v03-B: SPARQL 기반 추론 Rule

### 개요

- 사용자 정의 SPARQL CONSTRUCT 규칙을 `{graph}/rules` 서브그래프에 저장
- 규칙: `if(head) then(body)` 형태 (SPARQL CONSTRUCT pattern)
- 규칙 미리보기 실행 (추론 결과 반환)
- 규칙 결과 Materialization (OOI 그래프에 저장)

### 데이터 모델

```turtle
<{rule_iri}> a onto:Rule ;
    rdfs:label "{name}" ;
    rdfs:comment "{description}" ;
    onto:condition "{sparql_where_clause}" ;
    onto:consequence "{sparql_construct_template}" ;
    dcterms:created "{datetime}"^^xsd:dateTime .
```

### REST API

```
GET    /api/rules                    # 규칙 목록 ?dataset&graph
POST   /api/rules                    # 규칙 생성
GET    /api/rules/{iri:path}         # 규칙 상세
PATCH  /api/rules/{iri:path}         # 규칙 수정
DELETE /api/rules/{iri:path}         # 규칙 삭제
POST   /api/rules/{iri:path}/apply   # 규칙 적용 (미리보기)
POST   /api/rules/{iri:path}/materialize  # 결과 저장
```

### 테스트 시나리오 (10개)

| TC | 내용 |
|----|------|
| TC01 | 규칙 생성 (label + condition + consequence) → 201 |
| TC02 | 규칙 목록 조회 |
| TC03 | 규칙 상세 조회 |
| TC04 | 규칙 수정 (label, description) |
| TC05 | 규칙 삭제 |
| TC06 | 규칙 적용 미리보기 → inferred triples 반환 |
| TC07 | 빈 결과 규칙 적용 → empty list |
| TC08 | 규칙 결과 Materialization → 저장 확인 |
| TC09 | 잘못된 SPARQL 규칙 → 422 |
| TC10 | 존재하지 않는 규칙 → 404 |

---

## v03-C: Datasource 매핑

### 개요

- 외부 데이터소스(CSV, JSON, REST, SPARQL)를 온톨로지 Class/Property에 매핑
- 매핑 정의를 `{graph}/datasources` 서브그래프에 저장
- 매핑 규칙으로 Individual 일괄 생성 기능

### 데이터 모델

```turtle
# Datasource 정의
<{ds_iri}> a onto:Datasource ;
    rdfs:label "{name}" ;
    onto:dsType "csv" ;               # csv | json | rest | sparql
    onto:connectionInfo "{info}" .    # URL or path

# Class 매핑
<{mapping_iri}> a onto:ClassMapping ;
    onto:datasource <{ds_iri}> ;
    onto:targetClass <{class_iri}> ;
    onto:identifierField "{field_name}" .

# Property 매핑
<{prop_map_iri}> a onto:PropertyMapping ;
    onto:classMapping <{mapping_iri}> ;
    onto:sourceField "{field_name}" ;
    onto:targetProperty <{property_iri}> .
```

### REST API

```
GET    /api/datasources                          # 목록 ?dataset&graph
POST   /api/datasources                          # 생성
GET    /api/datasources/{iri:path}               # 상세
PATCH  /api/datasources/{iri:path}               # 수정
DELETE /api/datasources/{iri:path}               # 삭제
POST   /api/datasources/{iri:path}/mappings      # 매핑 추가
DELETE /api/datasources/{iri:path}/mappings/{mapping_iri:path}  # 매핑 삭제
GET    /api/datasources/{iri:path}/preview       # 데이터 미리보기
```

### 테스트 시나리오 (10개)

| TC | 내용 |
|----|------|
| TC01 | Datasource 생성 (csv type) → 201 |
| TC02 | Datasource 목록 조회 |
| TC03 | Datasource 상세 조회 |
| TC04 | Datasource 수정 |
| TC05 | Datasource 삭제 |
| TC06 | Class 매핑 추가 → 201, 매핑 IRI 반환 |
| TC07 | Property 매핑 추가 |
| TC08 | 매핑 삭제 |
| TC09 | 잘못된 타입 → 422 |
| TC10 | 존재하지 않는 Datasource 매핑 → 404 |

---

## v03-D: Universal Namespace import UI

### 개요

- 미리 등록된 표준 Namespace(foaf, schema, skos 등) 목록 제공
- 한 번의 클릭으로 OOI 그래프에 Universal Namespace 선언 추가
- 백엔드: 이미 선언된 것은 409 (중복), 새 것은 201

### 잘 알려진 Universal Namespace 목록

| prefix | base IRI |
|--------|----------|
| rdf | http://www.w3.org/1999/02/22-rdf-syntax-ns# |
| rdfs | http://www.w3.org/2000/01/rdf-schema# |
| owl | http://www.w3.org/2002/07/owl# |
| xsd | http://www.w3.org/2001/XMLSchema# |
| skos | http://www.w3.org/2004/02/skos/core# |
| dc | http://purl.org/dc/elements/1.1/ |
| dcterms | http://purl.org/dc/terms/ |
| foaf | http://xmlns.com/foaf/0.1/ |
| schema | http://schema.org/ |
| vann | http://purl.org/vocab/vann/ |
| prov | http://www.w3.org/ns/prov# |
| dcat | http://www.w3.org/ns/dcat# |

### REST API

```
GET  /api/namespaces/universal                  # 표준 NS 목록 (전체)
POST /api/namespaces/universal/import           # OOI 그래프에 선언 추가
     body: {dataset, graph, prefix, ns_iri}
```

### 테스트 시나리오 (10개)

| TC | 내용 |
|----|------|
| TC01 | Universal NS 목록 조회 → 12개 이상 반환 |
| TC02 | foaf NS import → 201, 그래프에 vann:prefix 선언 추가 |
| TC03 | schema NS import → 201 |
| TC04 | 이미 선언된 NS import → 409 |
| TC05 | skos NS import → 201, graph에서 SPARQL로 확인 |
| TC06 | 알 수 없는 prefix import → 422 (universal 목록에 없는 것) |
| TC07 | dcterms NS import → 201 |
| TC08 | prov NS import → 201 |
| TC09 | import 후 navigator namespace 목록에 반영 확인 |
| TC10 | 커스텀 prefix (Universal 아님) import 시도 → 422 |
