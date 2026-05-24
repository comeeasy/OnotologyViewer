# Reasoning

**Category:** Reasoning  
**Related:** [[data-model]], [[class]], [[object-property]], [[apache-jena-fuseki]]  
**Sources:** [[ontology-viewer-spec]]

## 정의

선택된 OOI 내의 온톨로지에서 명시적으로 선언되지 않은 지식을 **추론 규칙을 통해 자동으로 도출**하는 작업.  
백엔드: Apache Jena 내장 Reasoner → [[apache-jena-fuseki]]

## 추론 유형

| 유형 | 설명 | 예시 |
|------|------|------|
| **Class hierarchy inference** | `rdfs:subClassOf` 전이적 추론 | `:Dog subClassOf :Animal` → `:Rex type :Animal` |
| **Property inference** | domain, range 기반 타입 추론 | `:hasOwner domain :Pet` → 주어가 `:Pet`임을 추론 |
| **Consistency checking** | 온톨로지 무결성 검사 | disjoint class에 동시 소속된 Individual 탐지 |
| **Rule-based inference** | SWRL / SPARQL 커스텀 규칙 | 사용자 정의 if-then 규칙 |

## Jena 내장 Reasoner

| Reasoner | 적용 범위 | 권장 상황 |
|----------|-----------|---------|
| `OWL_DL_MEM_RULE` | OWL DL + 추론 규칙 | **일반 권장** |
| `OWL_MEM_RULE` | OWL Full + 추론 규칙 | 표현력 최대 필요 시 |
| `OWL_MEM_TRANS_INF` | Transitive inference만 | 경량 hierarchy 추론 |
| `RDFS` | RDFS 추론만 | RDFS 수준 스키마 |

> HermiT, Pellet, ELK는 현재 스펙 범위 밖 (OWL API 기반 별도 통합 필요)

## 수행 절차

```
1. OOI 선택
2. Reasoning 유형 선택
3. Reasoner 선택 (Jena 내장)
4. 결과 미리보기 (미저장 상태)
   - 추론된 트리플 목록 (추가될 triples)
   - Consistency 여부 (consistent / inconsistent)
   - Inconsistency 원인 설명 (explanation)
5. 사용자 검토 후 Materialization 결정
   - 저장: 추론 결과를 트리플로 OOI에 반영
   - 취소: 추론 결과 폐기, OOI 변경 없음
```

## Materialization

추론 결과는 바로 저장되지 않는다.  
사용자가 변동 사항을 확인 후 저장 여부를 결정한다.  
저장 시: Jena `CONSTRUCT` → `INSERT` 패턴으로 트리플 반영.

## 추론 규칙이란?

온톨로지 axiom(선언)으로부터 새 트리플을 도출하는 if-then 패턴.  
Jena가 내장 규칙 파일(e.g. `owl-fb.rules`)에 수백 개의 규칙을 보유.

**예시 규칙:**
```
# TransitiveProperty 규칙
(?p type TransitiveProperty), (?a ?p ?b), (?b ?p ?c) → (?a ?p ?c)

# subClassOf 규칙
(?x type ?A), (?A subClassOf ?B) → (?x type ?B)

# domain 규칙
(?p domain ?C), (?x ?p ?y) → (?x type ?C)
```
