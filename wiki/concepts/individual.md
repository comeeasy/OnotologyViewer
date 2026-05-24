# Individual

**Category:** Ontology Language  
**Related:** [[class]], [[object-property]], [[data-property]], [[data-model]]  
**Sources:** [[ontology-viewer-spec]]

## 정의

ABox의 구성요소. 특정 Class의 인스턴스(instance).  
모든 Individual은 **IRI**를 가진다.

## 특성

- 소속 Class의 Property를 가질 수 있다
  - **Object Property**: Individual ↔ Individual (자기 자신과의 관계도 허용)
  - **Data Property**: Individual → Literal 값
- 여러 Class에 동시에 소속될 수 있다 (OWL Open World Assumption)

## CRUD

### Create
```
1. Dataset 선택
2. OOI 선택
3. Class 선택 (소속 Class)
4. IRI 작성 (또는 자동 생성)
5. rdfs:label 작성
6. rdfs:comment 작성 (optional)
7. data property 값 입력
8. object property 관계 설정 (대상 Individual 선택)
```

### Read
- 소속 Class 확인
- data property 값 목록
- object property 관계 목록 (**outgoing + incoming** 모두)
- SHACL 검증 결과

### Update (모두 optional)
- `rdfs:label` / `rdfs:comment` 수정
- data property 값 수정 / 추가 / 삭제
- object property 관계 수정 / 추가 / 삭제
- 소속 Class 변경 (마이그레이션) ← 상세 절차 미정의

### Delete
```
1. 참여하는 모든 object property 관계 삭제 (outgoing + incoming)
2. 모든 data property 값 삭제
3. Individual 선언문 삭제
```

## 관련 개념
- **[[class]]**: Individual은 Class의 인스턴스
- **[[object-property]]**: Individual 간 관계의 타입을 Object Property가 정의
- **[[data-property]]**: Individual의 속성값을 Data Property가 정의
