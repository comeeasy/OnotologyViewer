# Data Property

**Category:** Ontology Language  
**Related:** [[class]], [[object-property]], [[individual]], [[data-model]]  
**Sources:** [[ontology-viewer-spec]]

## 정의

TBox의 구성요소. **Class ↔ Literal** 간의 관계를 정의하는 Property.  
- `domain`: Class
- `range`: xsd datatype

## 지원 xsd Datatype (range)

| Datatype | 예시 |
|----------|------|
| `xsd:string` | `"홍길동"` |
| `xsd:integer` | `42` |
| `xsd:float` | `3.14` |
| `xsd:boolean` | `true` |
| `xsd:dateTime` | `2026-05-24T00:00:00` |
| `xsd:anyURI` | `http://example.org/` |

## Property Characteristics

Data Property에는 **`Functional`만 적용 가능**.  
(Transitive, Symmetric 등은 Object Property 전용)

| Characteristic | 설명 |
|----------------|------|
| `Functional` | 각 주어에 대해 Literal 값이 최대 1개 |

## CRUD

### Create
```
1. Dataset 선택
2. OOI 선택
3. property 명 작성 (camelCase)
4. domain 설정 (Class)
5. range 설정 (xsd datatype)
6. property characteristics 설정 (Functional만)
```

### Update (모두 optional)
- property 명 수정
- domain 수정
- range(datatype) 수정
- characteristics 수정

### Delete
```
1. 해당 property를 사용하는 모든 Individual의 값 삭제
2. property 선언문 삭제
```

## 관련 개념
- **vs [[object-property]]**: Data Property는 Literal 값, Object Property는 다른 Individual
