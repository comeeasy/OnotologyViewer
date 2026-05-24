# Class

**Category:** Ontology Language  
**Related:** [[object-property]], [[data-property]], [[individual]], [[data-model]]  
**Sources:** [[ontology-viewer-spec]]

## 정의

TBox의 구성요소. 온톨로지에서 개념(concept)을 표현하는 단위.  
모든 Class는 **IRI**를 가진다.  
Class 간 계층 구조(`rdfs:subClassOf`)를 지원한다.

## CRUD

### Create
```
1. Dataset 선택
2. Namespace 선택  ┐ OOI 선택
3. Named Graph 선택 ┘
4. rdfs:label 작성
5. rdfs:comment 작성
6. Data Properties 생성
7. Object Properties 생성
```

### Update (모두 optional)
- `rdfs:label` 수정
- `rdfs:comment` 수정
- Object Property 수정
- Data Property 수정

### Delete
```
1. 소속 Individuals 처리 — 삭제 또는 다른 Class로 마이그레이션
2. 연결 관계 제거
   - domain / range 제거
   - 모든 property 관계 제거
3. Class 선언문 삭제
```

### Read (뷰)
| 뷰 | 내용 |
|----|------|
| Class hierarchy 탐색 | `rdfs:subClassOf` 기반 계층 시각화 |
| 관계 탐색 | domain, range 기반 Object Property 시각화 |
| Data Property 목록 | 소속 Individuals 통계값 포함 |
| SHACL 검증 룰 시각화 | 적용된 SHACL shape 표시 |
| Rule 시각화 | 추론 규칙 표시 |
| Datasource 매핑 | 각 datasource ↔ class 매핑 관계 |

## 관련 개념
- **vs [[individual]]**: Class는 타입 정의, Individual은 그 타입의 인스턴스
- **vs [[object-property]]**: Object Property의 domain/range가 Class를 참조
- **vs [[data-property]]**: Data Property의 domain이 Class를 참조
