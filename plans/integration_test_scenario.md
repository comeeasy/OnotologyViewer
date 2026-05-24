# OntologyViewer — 통합 테스트 시나리오

**Date:** 2026-05-25  
**Domain:** 도서관(Library) 온톨로지  
**목적:** v01~v03 전 기능 End-to-End 검증

---

## 도메인 구조

### Classes
```
Book
  ├── Novel       (subClassOf Book)
  └── Textbook    (subClassOf Book)
Author
Publisher
LibraryMember
Loan
Genre           ← Stage 3에서 신규 생성
```

### Object Properties
| Property | Domain | Range |
|---------|--------|-------|
| writtenBy | Book | Author |
| publishedBy | Book | Publisher |
| loanOf | Loan | Book |
| borrowedBy | Loan | LibraryMember |
| hasGenre | Book | Genre |

### Data Properties
| Property | Domain | Range |
|---------|--------|-------|
| title | Book | xsd:string |
| isbn | Book | xsd:string |
| birthYear | Author | xsd:integer |
| memberSince | LibraryMember | xsd:integer |
| loanDate | Loan | xsd:string |
| dueDate | Loan | xsd:string |
| pageCount | Book | xsd:integer |

### 초기 Individual (library.ttl에 포함)
| IRI | Class | 주요 값 |
|-----|-------|---------|
| Author_KimCheolsu | Author | label=김철수, birthYear=1975 |
| Author_LeeMina | Author | label=이미나, birthYear=1982 |
| Publisher_HanbitMedia | Publisher | label=한빛미디어 |
| Publisher_Wikibooks | Publisher | label=위키북스 |
| Book_OWLPrimer | Book | title=OWL 온톨로지 입문, isbn=978-89-6848-001-1 |
| Book_KnowledgeGraph | Book | title=지식 그래프 기초, isbn=978-89-6848-002-2 |
| Member_ParkJiyeon | LibraryMember | label=박지연, memberSince=2020 |
| Member_ChoiSungjun | LibraryMember | label=최성준, memberSince=2022 |
| Loan_001 | Loan | loanOf=Book_OWLPrimer, borrowedBy=Member_ParkJiyeon |

---

## 필요 파일

| 파일 | 위치 | 용도 |
|------|------|------|
| `library.ttl` | `test-data/library.ttl` | Stage 2 TTL 업로드 |
| `new_books.csv` | `test-data/new_books.csv` | Stage 8 Datasource 등록 |

### new_books.csv 컬럼
`title, isbn, authorName, publishYear, publisher` — 5행

---

## 시나리오

---

### STAGE 1 — 환경 설정 (Navigator)

| # | 액션 | 검증 포인트 |
|---|------|------------|
| 1-1 | 앱 접속, Fuseki 연결 확인 | "Fuseki 연결됨" 녹색 뱃지 |
| 1-2 | Dataset `library-test` 생성 | Dataset Select에 등장 |
| 1-3 | Named Graph `http://library.org/graph/v1` 생성 | Graph Select에 등장 |
| 1-4 | Universal Namespace import: owl, rdfs, xsd | Namespace 목록 Universal 3개 확인 |

---

### STAGE 2 — TTL 업로드 & OOI 설정

| # | 액션 | 검증 포인트 |
|---|------|------------|
| 2-1 | Named Graph 선택 후 ⬆ 버튼 클릭 → `library.ttl` 업로드 (mode=append) | 성공 메시지 + 트리플 수 표시 |
| 2-2 | Namespace 선언: IRI=`http://library.org/onto#`, prefix=`lib` | Namespace 목록에 `lib:` 등장 |
| 2-3 | `lib:` 체크박스 선택 → OOI 설정 클릭 | 탭 전체 활성화 |
| 2-4 | Class 탭: Book, Author, Publisher, LibraryMember, Loan 5개 확인 | label 기준으로 표시 |
| 2-5 | Individual 탭: 저자 2, 출판사 2, 도서 2, 회원 2, 대출 1 = 총 9건 확인 | |

---

### STAGE 3 — TBox 편집

| # | 액션 | 검증 포인트 |
|---|------|------------|
| 3-1 | Class `Genre` 신규 생성 (label=장르) | Class 목록 6개 |
| 3-2 | Class `Novel` 생성 → ClassDetail > 계층 편집 > 상위 Class에 `Book` 추가 | Book 하위에 Novel 표시 |
| 3-3 | Class `Textbook` 생성 → 상위 Class에 `Book` 추가 | Book 하위에 Novel, Textbook |
| 3-4 | Object Property `hasGenre` 생성 (domain=Book, range=Genre) | ObjProp 목록 5개 |
| 3-5 | Data Property `pageCount` 생성 (domain=Book, range=xsd:integer) | DataProp 목록 7개 |
| 3-6 | `writtenBy` ObjPropDetail > inverseOf 섹션 → `authorOf` 선택해서 설정 | ObjPropDetail에 inverseOf 표시 |

---

### STAGE 4 — ABox 편집 (Individual)

| # | 액션 | 검증 포인트 |
|---|------|------------|
| 4-1 | Individual `Genre_SF` 생성 (class=Genre, label=SF소설) | Genre 필터 시 1건 |
| 4-2 | `Book_OWLPrimer` 수정 → `hasGenre`→`Genre_SF` 관계 추가, `pageCount`=320 추가 | Detail Drawer outgoing에 표시 |
| 4-3 | `Book_OWLPrimer` Detail > Class 변경(SwapOutlined) → `Novel`로 마이그레이션 | Detail Drawer class=Novel |
| 4-4 | `Loan_002` 신규 생성 (borrowedBy=최성준, loanOf=지식 그래프 기초) | Loan 필터 2건 |
| 4-5 | `Book_NoTitle` 생성 (class=Book, title 없음, isbn 없음) | SHACL 테스트용 |

---

### STAGE 5 — SHACL 검증

| # | 액션 | 검증 포인트 |
|---|------|------------|
| 5-1 | SHACL 탭 > NodeShape `BookShape` 생성 (targetClass=`lib:Book`) | Shape 목록 1건 |
| 5-2 | BookShape에 PropertyShape 추가: path=`lib:title`, minCount=1, datatype=xsd:string | Shape 상세에 PropertyShape 확인 |
| 5-3 | PropertyShape 추가: path=`lib:isbn`, minCount=1 | |
| 5-4 | Individual 탭 > `Book_OWLPrimer` Detail > SHACL 검증 실행 | conforms=True, 녹색 Alert |
| 5-5 | `Book_NoTitle` Detail > SHACL 검증 실행 | conforms=False, 위반 2건 (title, isbn 누락) |
| 5-6 | Class 탭 > `Book` 클릭 > SHACL 탭 | BookShape 1건 표시 |

---

### STAGE 6 — Rule

| # | 액션 | 검증 포인트 |
|---|------|------------|
| 6-1 | Rules 탭 > `PublishedAuthorRule` 생성 | Rules 목록 1건 |

**Rule 내용**
```
label:       PublishedAuthorRule
description: 책을 출판한 저자를 PublishedAuthor로 분류

Condition (WHERE):
  ?book a <http://library.org/onto#Book> .
  ?book <http://library.org/onto#writtenBy> ?author .
  ?book <http://library.org/onto#publishedBy> ?pub .

Consequence (CONSTRUCT):
  ?author a <http://library.org/onto#PublishedAuthor> .
```

| # | 액션 | 검증 포인트 |
|---|------|------------|
| 6-2 | Rule > Apply (미리보기) | Author_KimCheolsu, Author_LeeMina에 PublishedAuthor 타입 추론 |
| 6-3 | Rule > Materialize | SPARQL Editor로 inferred graph 조회해서 저장 확인 |

---

### STAGE 7 — Reasoning

| # | 액션 | 검증 포인트 |
|---|------|------------|
| 7-1 | Reasoning 탭 > Reasoner=OWL_DL_MEM_RULE 선택 > 추론 실행 | inferred triples 미리보기 표시 |
| 7-2 | 주목할 추론 결과 | Novel individual(`Book_OWLPrimer`) → a `lib:Book` 추론 (subClassOf 전파) |
| 7-3 | Materialize 실행 | 성공 메시지, materialized_count 확인 |

---

### STAGE 8 — Datasource 매핑

| # | 액션 | 검증 포인트 |
|---|------|------------|
| 8-1 | Datasource 탭 > `NewBooks` 생성 (type=csv, connection_info=new_books.csv 파일 경로) | Datasource 목록 1건 |
| 8-2 | ClassMapping 추가: targetClass=`lib:Book`, identifierField=isbn | 매핑 카드 등장 |
| 8-3 | PropertyMapping 추가: `title` → `lib:title` | 매핑 카드에 표시 |
| 8-4 | PropertyMapping 추가: `isbn` → `lib:isbn` | |
| 8-5 | 미리보기 버튼 → CSV 5행 JSON 표시 | error=null, rows 5개 |
| 8-6 | Class 탭 > `Book` > Datasource 탭 | NewBooks 1건 표시 |

---

### STAGE 9 — SPARQL Editor

| # | 쿼리 | 기대 결과 |
|---|------|----------|
| 9-1 | `SELECT ?book ?title WHERE { ?book a <lib:Book> ; <lib:title> ?title }` | 2건 이상 (Book_OWLPrimer, Book_KnowledgeGraph) |
| 9-2 | `SELECT ?loan ?member ?book WHERE { ?loan <lib:borrowedBy> ?member ; <lib:loanOf> ?book }` | 2건 (Loan_001, Loan_002) |
| 9-3 | `INSERT DATA { GRAPH <...> { <lib:Book_TestSPARQL> a <lib:Book> ; rdfs:label "SPARQL 테스트도서" } }` | 성공, Individual 탭 새로고침 시 등장 |

---

### STAGE 10 — 정리 (삭제 플로우)

| # | 액션 | 검증 포인트 |
|---|------|------------|
| 10-1 | `Book_NoTitle` Individual 삭제 | 목록에서 제거 |
| 10-2 | `Novel` > 계층 편집 > 상위 Class `Book` 관계 삭제 | Book 하위 Class에서 Novel 제거 |
| 10-3 | `Genre` Class 삭제 → Individual 처리 Modal → `Genre_SF`를 `Book`으로 migrate 선택 | 완료 후 Genre_SF의 class_iri=Book |
| 10-4 | `BookShape` SHACL Shape 삭제 | SHACL 목록 0건 |
| 10-5 | `PublishedAuthorRule` Rule 삭제 | Rules 목록 0건 |

---

## 커버되는 기능 목록

| 기능 | Stage |
|------|-------|
| Fuseki 연결 | 1 |
| Dataset 생성 | 1 |
| Named Graph 생성 | 1 |
| Universal NS import | 1 |
| TTL 파일 업로드 (append) | 2 |
| Namespace 선언 | 2 |
| OOI 설정 | 2 |
| Class 목록 조회 | 2 |
| Individual 목록 조회 | 2 |
| Class 생성 | 3 |
| Class 계층 편집 (subClassOf) | 3 |
| Object Property 생성 | 3 |
| Data Property 생성 | 3 |
| inverseOf 설정 | 3 |
| Individual 생성 | 4 |
| Individual 수정 (DP + OP 추가) | 4 |
| Individual Class 마이그레이션 | 4 |
| SHACL NodeShape 생성 | 5 |
| SHACL PropertyShape 추가 | 5 |
| Individual SHACL 검증 (pass) | 5 |
| Individual SHACL 검증 (fail) | 5 |
| ClassDetail SHACL 탭 | 5 |
| Rule 생성 | 6 |
| Rule Apply (미리보기) | 6 |
| Rule Materialize | 6 |
| ClassDetail Rules 탭 | 6 |
| Reasoning 실행 | 7 |
| Reasoning Materialize | 7 |
| Datasource 생성 | 8 |
| ClassMapping 추가 | 8 |
| PropertyMapping 추가 | 8 |
| Datasource 미리보기 | 8 |
| ClassDetail Datasource 탭 | 8 |
| SPARQL SELECT | 9 |
| SPARQL UPDATE | 9 |
| Individual 삭제 | 10 |
| Class 계층 관계 삭제 | 10 |
| Class 삭제 (Individual migrate) | 10 |
| SHACL Shape 삭제 | 10 |
| Rule 삭제 | 10 |
