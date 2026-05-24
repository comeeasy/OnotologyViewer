# Wiki Log

> 이 파일은 append-only 로그입니다. 모든 ingest·query·lint 작업이 기록됩니다.
> LLM이 자동으로 항목을 추가합니다. 직접 수정하지 마세요.
>
> 파싱 팁: `grep "^## \[" wiki/log.md | tail -10` 으로 최근 10개 항목 확인

---

## [2026-05-24] query | 기술 스택 결정 → plan_v01.md 반영

- 결정 사항:
  - Backend: Python (FastAPI + SPARQLWrapper + rdflib)
  - Frontend: 백엔드 완성 후 진행
  - Fuseki: 멀티 dataset (Admin API 활용)
  - IRI 생성: baseIRI(사용자 입력) + label_slug + uuid4_short, 충돌 시 재생성
- Pages updated: `plans/plan_v01.md`

---

## [2026-05-24] ingest | raw/spec.md → wiki 전체 구조화

- Pages created:
  - `wiki/concepts/data-model.md`
  - `wiki/concepts/class.md`
  - `wiki/concepts/object-property.md`
  - `wiki/concepts/data-property.md`
  - `wiki/concepts/individual.md`
  - `wiki/concepts/reasoning.md`
- Pages updated:
  - `wiki/queries/ontology-viewer-spec.md` (전면 재작성, items 1~40 반영)
  - `wiki/index.md`
- 아키텍처 결정: 백엔드 Fuseki, Reasoner = Jena 내장

---

## [2026-05-24] query | OntologyViewer 기능 명세 정리 (초안)

- Pages created: `wiki/queries/ontology-viewer-spec.md`
- Pages updated: `wiki/index.md`
- 내용: Dataset/NamedGraph/Namespace 계층 구조, OOI 정의, TBox/ABox, Class CRUD, Object Property Create 명세

---

## [2026-05-24] init | Wiki initialized

- 위키 디렉토리 구조 생성
- CLAUDE.md 스키마 작성
- `wiki/index.md`, `wiki/log.md` 초기화
- 빈 카테고리 디렉토리 생성: `concepts/`, `entities/`, `sources/`
