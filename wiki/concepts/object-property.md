# Object Property

**Category:** Ontology Language  
**Related:** [[class]], [[data-property]], [[individual]], [[data-model]]  
**Sources:** [[ontology-viewer-spec]]

## 정의

TBox의 구성요소. **Class ↔ Class** 간의 관계를 정의하는 Property.  
반드시 `domain`(출발 Class)과 `range`(도착 Class)를 가져야 한다.  
ABox에서는 **Individual ↔ Individual** 간의 관계로 실체화된다 (자기 자신 포함).

## Property Characteristics

| Characteristic | 설명 |
|----------------|------|
| `Functional` | 각 주어에 대해 목적어가 최대 1개 |
| `InverseFunctional` | 각 목적어에 대해 주어가 최대 1개 |
| `Transitive` | (?a ?p ?b), (?b ?p ?c) → (?a ?p ?c) |
| `Symmetric` | (?a ?p ?b) → (?b ?p ?a) |
| `Asymmetric` | (?a ?p ?b) → ¬(?b ?p ?a) |
| `Reflexive` | 모든 개체에 대해 (?x ?p ?x) 성립 |
| `Irreflexive` | 어떤 개체도 (?x ?p ?x) 불가 |

> `inverseOf`는 characteristics가 아닌 별도 axiom (`owl:inverseOf`)

## CRUD

### Create
```
1. Dataset 선택
2. OOI 선택
3. property 명 작성 (camelCase)
4. domain 설정 (Class)
5. range 설정 (Class)
6. property characteristics 설정
```

### Update (모두 optional)
- property 명 수정
- domain 수정
- range 수정
- characteristics 수정

### Delete
```
1. 해당 property를 사용하는 모든 Individual 간 관계 삭제
2. domain, range 선언 삭제
3. property 선언문 삭제
```

## 관련 개념
- **vs [[data-property]]**: Object Property는 Class↔Class, Data Property는 Class↔Literal
- **[[reasoning]]**: Transitive/Symmetric 등 characteristics는 Jena Reasoner가 추론에 활용
