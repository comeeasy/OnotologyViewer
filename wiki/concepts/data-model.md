# 데이터 모델 (Data Model)

**Category:** Data Model  
**Related:** [[class]], [[object-property]], [[data-property]], [[individual]], [[reasoning]]  
**Sources:** [[ontology-viewer-spec]]

## 계층 구조

```
Dataset
└── Named Graph          ← 온톨로지 구분 축 1
    └── Namespace        ← 온톨로지 구분 축 2 (= Base IRI)
```

온톨로지를 구분하는 축이 두 개 존재한다.  
**OOI (Ontology of Interest)** = Namespace + Named Graph 조합으로 선택된 온톨로지 단위.

## Namespace

- **정의**: Base IRI. prefix의 기저가 되는 IRI.
- **분류**:
  - `Custom`: 사용자가 직접 정의
  - `Universal`: import한 표준 namespace (e.g. `rdf:`, `owl:`, `xsd:`, `rdfs:`)
- Namespace 수정(prefix/base IRI) 시 사용 중인 IRI **일괄 치환** 필요

## Named Graph

- Fuseki dataset 내의 named graph로 관리됨
- IRI로 식별됨

## Dataset

- Apache Jena Fuseki의 dataset 개념과 1:1 매핑 → [[apache-jena-fuseki]]

## TBox / ABox

모든 온톨로지는 TBox와 ABox로 구분된다.

| 구분 | 내용 | 구성요소 |
|------|------|---------|
| **TBox** | 스키마 (Schema) | [[class]], [[object-property]], [[data-property]] |
| **ABox** | 인스턴스 (Instances) | [[individual]] |

## 상호 포함 관계 조회

- 선택한 Named Graph → 속하는 모든 Namespace 목록 출력
- 선택한 Namespace → 속하는 모든 Named Graph 목록 출력
