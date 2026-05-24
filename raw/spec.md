1. namespace (모든 prefix) 리스트 하는 기능
2. namespace는 직접 구현한 custom, import한 universal로 구분
3. namespace는 base IRI 를 의미한다
4. 여러 namespace를 선택할 수 있다
5. 선택한 namespace 아래에서 SPARQL 을 통해 CRUD를 수행할 수 있다
6. 선택한 namespace 아래에서 Reasoning을 수행할 수 있다
7. namespace로 구분되는 온톨로지들은 named-graph로 구분된다. 즉, 온톨로지를 구분하는 축이 2개가 있는 것.
8. namespace, named-graph를 선택하면 선택된 온톨로지에 서로 포함되는 리스트를 출력할 수 있다. (e.g. 선택된 named-graph에 속하는 모든 namespaces 를 출력할 수 있어야한다.
9. namespace, named-graph 상위에는 dataset이 존재함
10. 모든 온톨로지는 TBox, ABox로 구분된다
11. TBox는 스키마로써 Class, Relation으로 구성된다. 모든 Class는 IRI를 갖는다. Relation은 object property와 data property로 구분된다
12. object property는 class와 class간의 관계. data property는 class와 리터럴의
관계를 정의한다.
13. object property는 반드시 domain, range를 가져야한다
14. ABox는 각 Class의 individuals로 구성된다
15. 모든 Individual은 IRI를 갖는다
16. 각 Individual은 소속된 Class의 Relation을 갖는다. 단, object property는 Individual 끼리 맺을 수 있다. (자기 자신 포함) namespace, named-graph로 선택된 온톨로지를 ontology of interest (OOI) 라고 정의한다
17. Class의 create는 아래와 같이 정의된다
    a. dataset 선택
    b. namespace 선택 (OOI) 선택
    c. named-graph 선택
    d. rdfs:label 작성
    e. rdfs:comment 작성
    f. data properties 생성
    g. object property 생성
18. Class의 update는 아래와 같이 정의된다
  (?) 는 optional
  a. label 수정 (?)
  b. comment 수정 (?)
  c. object property 수정 (?)
  d. data property 수정 (?)
19. Class의 삭제는 아래와 같이 정의된다.
  a. 모든 소속 Individuals를 분리한다
    - 분리는 삭제 혹은 마이그레이션을 의미한다
  b. 해당 Class와의 연결을 모두 삭제한다
    - domain, range 제거
    - 관계 제거
  c. Class 선언문 삭제
20. Class의 Read는 아래와 같이 정의된다.
  - class간의 hierarchy 탐색
  - domain, range 기반의 관계 탐색
  - data property 리스트 및 소속된 모든 Individuals의 통계값
  - shacl 검증룰 시각화
  - Rule 시각화
  - 각 datasource와 class간의 맵핑 관계
21. object proerty의 생성 순서는 아래와 같다
    a. dataset 선택
    b. OOI 선택
    c. property 명 작성 (camelCase)
    d. domain 설정
    e. range 설정
    f. property characteristics 설정 (Functional, InverseFunctional, Transitive, Symmetric, Asymmetric, Reflexive, Irreflexive)

22. object property의 수정 순서는 아래와 같다
    (?) 는 optional
    a. property 명 수정 (?)
    b. domain 수정 (?)
    c. range 수정 (?)
    d. property characteristics 수정 (?)

23. object property의 삭제 순서는 아래와 같다
    a. 해당 property를 사용하는 모든 Individual 간의 관계 삭제
    b. domain, range 선언 삭제
    c. property 선언문 삭제

24. data property의 생성 순서는 아래와 같다
    a. dataset 선택
    b. OOI 선택
    c. property 명 작성 (camelCase)
    d. domain 설정 (Class)
    e. range 설정 (xsd datatype: string, integer, float, boolean, dateTime, anyURI 등)
    f. property characteristics 설정 (Functional만 적용 가능)

25. data property의 수정 순서는 아래와 같다
    (?) 는 optional
    a. property 명 수정 (?)
    b. domain 수정 (?)
    c. range(datatype) 수정 (?)
    d. property characteristics 수정 (?)

26. data property의 삭제 순서는 아래와 같다
    a. 해당 property를 사용하는 모든 Individual의 값 삭제
    b. property 선언문 삭제

27. Individual의 생성 순서는 아래와 같다
    a. dataset 선택
    b. OOI 선택
    c. Class 선택 (소속 Class)
    d. IRI 작성 (또는 자동 생성)
    e. rdfs:label 작성
    f. rdfs:comment 작성 (optional)
    g. data property 값 입력
    h. object property 관계 설정 (대상 Individual 선택)

28. Individual의 Read는 아래와 같이 정의된다
    - 소속 Class 확인
    - data property 값 목록
    - object property 관계 목록 (outgoing + incoming 모두)
    - SHACL 검증 결과

29. Individual의 수정 순서는 아래와 같다
    (?) 는 optional
    a. rdfs:label 수정 (?)
    b. rdfs:comment 수정 (?)
    c. data property 값 수정 / 추가 / 삭제 (?)
    d. object property 관계 수정 / 추가 / 삭제 (?)
    e. 소속 Class 변경 — 마이그레이션 (?)

30. Individual의 삭제 순서는 아래와 같다
    a. 해당 Individual이 참여하는 모든 object property 관계 삭제 (outgoing + incoming)
    b. 해당 Individual의 모든 data property 값 삭제
    c. Individual 선언문 삭제

31. Namespace의 생성 순서는 아래와 같다
    a. dataset 선택
    b. prefix 작성 (e.g. ex, foaf, schema)
    c. base IRI 작성 (e.g. http://example.org/ontology#)
    d. 유형 선택 (Custom / Universal)

32. Namespace의 수정 순서는 아래와 같다
    (?) 는 optional
    a. prefix 수정 (?) — 사용 중인 prefix 수정 시 IRI 일괄 치환 필요
    b. base IRI 수정 (?) — 사용 중인 IRI 일괄 치환 필요

33. Namespace의 삭제 순서는 아래와 같다
    a. 해당 namespace를 base IRI로 사용하는 모든 IRI 처리
       - 삭제 또는 다른 namespace로 마이그레이션
    b. namespace 선언 삭제

34. Named Graph의 생성 순서는 아래와 같다
    a. dataset 선택
    b. Named Graph IRI 작성
    c. rdfs:label 작성 (optional)
    d. rdfs:comment 작성 (optional)

35. Named Graph의 수정 순서는 아래와 같다
    (?) 는 optional
    a. rdfs:label 수정 (?)
    b. rdfs:comment 수정 (?)

36. Named Graph의 삭제 순서는 아래와 같다
    a. 포함된 모든 트리플 처리
       - 삭제 또는 다른 Named Graph로 마이그레이션
    b. Named Graph 선언 삭제

37. Dataset의 생성 순서는 아래와 같다
    a. dataset 명 작성
    b. dataset IRI 작성

38. Dataset의 수정 순서는 아래와 같다
    (?) 는 optional
    a. dataset 명 수정 (?)
    b. dataset IRI 수정 (?)

39. Dataset의 삭제 순서는 아래와 같다
    a. 포함된 모든 Named Graph 처리
       - 삭제 또는 다른 Dataset으로 마이그레이션
    b. Dataset 선언 삭제

40. Reasoning의 수행 순서는 아래와 같다
    a. OOI 선택
    b. Reasoning 유형 선택
       - Class hierarchy inference (subClassOf 추론)
       - Property inference (domain, range 기반 타입 추론)
       - Consistency checking (온톨로지 무결성 검사)
       - Rule-based inference (SWRL / SPARQL rules)
    c. Reasoner 선택 (Jena 내장 Reasoner 기준)
       - OWL_DL_MEM_RULE: OWL DL + 추론 규칙 (일반 권장)
       - OWL_MEM_RULE: OWL Full + 추론 규칙
       - OWL_MEM_TRANS_INF: Transitive inference만
       - RDFS: RDFS 추론만
    d. 결과 출력 (미저장 상태로 미리보기)
       - 추론된 트리플 목록 (추가될 triples)
       - Consistency 여부 (consistent / inconsistent)
       - Inconsistency 원인 설명 (explanation)
    e. 사용자가 변동 사항을 검토 후 Materialization 여부 결정
       - 저장: 추론 결과를 트리플로 OOI에 반영
       - 취소: 추론 결과 폐기, OOI 변경 없음


