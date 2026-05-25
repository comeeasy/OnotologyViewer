# OntologyViewer — Plan v05: Datasource Import Engine

**Date:** 2026-05-26  
**Status:** ⬜ 미착수  
**Depends on:** plan_v04.md (완료 후 병행 가능)

---

## 배경 — 왜 v05가 필요한가

v03-C에서 구현한 Datasource 패널은 **매핑 정의 저장**까지만 완료됐다.  
실제 외부 데이터 → RDF 트리플 변환(Import) 기능이 없다.

지원할 소스 유형:

| 타입 | 설명 | 핵심 난이도 |
|------|------|------------|
| **CSV** | 로컬 파일 or URL | 컬럼 매핑, 타입 추론 |
| **JSON** | 로컬 파일 or URL, JSONPath 지원 | 중첩 구조, 배열 전개 |
| **REST API** | HTTP GET, 페이지네이션, 인증 | 페이지네이션 전략, 인증 |
| **RDB** | SQLite / PostgreSQL / MySQL | SQLAlchemy 어댑터, 타입 변환 |

---

## 아키텍처

```
services/datasource_import/
├── __init__.py          # import_datasource() 진입점
├── base.py              # AbstractImporter 인터페이스
├── csv_importer.py      # CSV (로컬/URL)
├── json_importer.py     # JSON + JSONPath (로컬/URL)
├── rest_importer.py     # REST API (페이지네이션, 인증)
└── rdb_importer.py      # SQLAlchemy 기반 RDB
```

### 공통 흐름

```
[Datasource 설정] ─→ [Importer.fetch_rows()] ─→ [rows: list[dict]]
                                                        │
                                                [매핑 적용]
                                                        │
                                              ┌─────────────────┐
                                              │ ClassMapping 순회 │
                                              │  pk = row[id_field]│
                                              │  iri = ns:Cls_pk  │
                                              │  rdf:type triple  │
                                              │  PropertyMapping  │
                                              │  → value triples  │
                                              └─────────────────┘
                                                        │
                                              [SPARQL INSERT]
                                                        │
                                              {imported_count, skipped, errors}
```

### IRI 생성 규칙

```
targetClass: http://library.org/onto#Book
pk_field:    isbn
pk_value:    978-89-6848-101-8

pk_safe = re.sub(r'[^A-Za-z0-9_\-]', '_', pk_value)
→ individual_iri = http://library.org/onto#Book_978-89-6848-101-8
```

### 리터럴 타입 추론

PropertyMapping에 `target_type` 선택 옵션 추가 (선택 안 하면 자동 추론):

| 값 형태 | 추론 타입 |
|---------|---------|
| `"true"` / `"false"` | `xsd:boolean` |
| 정수 문자열 | `xsd:integer` |
| 실수 문자열 | `xsd:decimal` |
| ISO 날짜 (`2024-01-01`) | `xsd:date` |
| ISO 날짜시간 | `xsd:dateTime` |
| 기타 | `xsd:string` |

---

## 구현 단계

### Step 1 — CSV Importer
### Step 2 — JSON Importer  
### Step 3 — REST API Importer
### Step 4 — RDB Importer (SQLite → PostgreSQL → MySQL)
### Step 5 — Frontend Import UI (Import 버튼 + 결과 리포트)
### Step 6 — connection_info 스키마 구조화 (JSON 형식으로 확장)

---

## 개발 원칙

> 매 Step마다:
> 1. **실제 데이터 기반 시나리오 10개** 먼저 작성
> 2. **pytest 테스트 코드** 구현
> 3. **테스트 통과** 확인
> 4. 다음 Step으로 이동

---

## Step 1 — CSV Importer

### 테스트 시나리오 10개

| # | 시나리오 | 입력 | 기대 결과 |
|---|---------|------|---------|
| 1 | 기본 flat CSV → Book 트리플 | `isbn,title` 5행 | 5 individuals, rdf:type Book, title 값 |
| 2 | 선택 필드 누락 (빈 값) | `isbn=X, title=""` | individual 생성, title 트리플 생략 |
| 3 | PK에 특수문자 (ISBN 대시) | `978-89-6848-101-8` | IRI: `Book_978-89-6848-101-8` |
| 4 | 쉼표 포함 필드 (따옴표 처리) | `"Foo, Bar",isbn-1` | title = `Foo, Bar` 정상 처리 |
| 5 | UTF-8 BOM 파일 | BOM+CSV | BOM 제거 후 정상 파싱 |
| 6 | 대용량 CSV (1000행) | 1000 rows | 1000 individuals INSERT |
| 7 | 숫자 타입 자동 추론 | `year=2024` | `"2024"^^xsd:integer` |
| 8 | 중복 PK 처리 | 같은 isbn 2개 | 두 번째 행으로 덮어쓰기 (upsert) |
| 9 | URL CSV 소스 | `https://example.com/books.csv` | httpx로 다운로드 후 처리 |
| 10 | 복수 ClassMapping | Book + Author mapping | 각 클래스별 individual 생성 |

### 테스트 데이터 파일

#### `tests/fixtures/books.csv`
```csv
isbn,title,authorName,publishYear,publisher
978-89-6848-101-8,시맨틱 웹 입문,홍길동,2024,한빛미디어
978-89-6848-102-5,온톨로지 설계,이영희,2023,위키북스
978-89-6848-103-2,SPARQL 마스터,박철수,2024,한빛미디어
978-89-6848-104-9,지식 표현과 추론,김민지,2023,위키북스
978-89-6848-105-6,RDF와 연결 데이터,최동현,2025,한빛미디어
```

#### `tests/fixtures/books_with_empty.csv`
```csv
isbn,title,authorName,publishYear
978-89-9999-001-0,제목없는책,,2024
978-89-9999-002-7,완전한책,홍길동,2023
```

#### `tests/fixtures/books_utf8bom.csv`
UTF-8 BOM 인코딩 파일 (테스트 setUp에서 생성)

#### `tests/fixtures/books_large.csv`
1000행 자동 생성 (테스트 setUp에서 생성)

### 테스트 코드 (`tests/test_v05_csv_importer.py`)

```python
"""
v05 Step 1 — CSV Importer 테스트
실제 데이터를 사용하는 통합 테스트.
Fuseki 없이 동작: importer.fetch_rows() 단위 테스트 + 트리플 생성 검증
"""
import csv
import io
import os
import pytest
from services.datasource_import.csv_importer import CsvImporter
from services.datasource_import.base import ImporterConfig, ClassMappingConfig, PropMappingConfig

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

# ── 공통 픽스처 ────────────────────────────────────────────────

BOOK_CLASS = "http://library.org/onto#Book"
TITLE_PROP = "http://library.org/onto#title"
ISBN_PROP  = "http://library.org/onto#isbn"
YEAR_PROP  = "http://library.org/onto#publishYear"

def make_config(conn: str, id_field="isbn") -> ImporterConfig:
    return ImporterConfig(
        connection_info=conn,
        mappings=[
            ClassMappingConfig(
                target_class=BOOK_CLASS,
                identifier_field=id_field,
                property_mappings=[
                    PropMappingConfig(source_field="title",       target_property=TITLE_PROP),
                    PropMappingConfig(source_field="isbn",        target_property=ISBN_PROP),
                    PropMappingConfig(source_field="publishYear", target_property=YEAR_PROP),
                ],
            )
        ],
    )


# ── Scenario 1: 기본 flat CSV ──────────────────────────────────

def test_s1_basic_flat_csv():
    cfg = make_config(os.path.join(FIXTURES, "books.csv"))
    importer = CsvImporter(cfg)
    rows = importer.fetch_rows()
    assert len(rows) == 5
    assert rows[0]["isbn"] == "978-89-6848-101-8"
    assert rows[0]["title"] == "시맨틱 웹 입문"

def test_s1_triples_generated():
    cfg = make_config(os.path.join(FIXTURES, "books.csv"))
    importer = CsvImporter(cfg)
    triples = importer.generate_triples()
    # 5 individuals × (rdf:type + title + isbn + year) = 20 triples
    type_triples = [t for t in triples if t.predicate == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"]
    assert len(type_triples) == 5
    assert all(t.object == BOOK_CLASS for t in type_triples)

def test_s1_iri_format():
    cfg = make_config(os.path.join(FIXTURES, "books.csv"))
    importer = CsvImporter(cfg)
    triples = importer.generate_triples()
    type_triples = [t for t in triples if t.predicate == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"]
    first_iri = type_triples[0].subject
    assert first_iri == f"{BOOK_CLASS}_978-89-6848-101-8"


# ── Scenario 2: 빈 값 처리 ─────────────────────────────────────

def test_s2_empty_optional_field():
    cfg = make_config(os.path.join(FIXTURES, "books_with_empty.csv"))
    importer = CsvImporter(cfg)
    triples = importer.generate_triples()
    # authorName이 없는 첫 번째 행: authorName 트리플 없어야 함
    subj = f"{BOOK_CLASS}_978-89-9999-001-0"
    subj_triples = [t for t in triples if t.subject == subj]
    prop_iris = [t.predicate for t in subj_triples]
    # title은 있고, authorName 매핑이 없으면 트리플 없음
    assert TITLE_PROP in prop_iris


# ── Scenario 3: PK 특수문자 (ISBN 대시) ────────────────────────

def test_s3_pk_special_chars():
    cfg = make_config(os.path.join(FIXTURES, "books.csv"))
    importer = CsvImporter(cfg)
    triples = importer.generate_triples()
    iris = {t.subject for t in triples}
    assert f"{BOOK_CLASS}_978-89-6848-101-8" in iris


# ── Scenario 4: 쉼표 포함 필드 ────────────────────────────────

def test_s4_quoted_commas(tmp_path):
    csv_file = tmp_path / "quoted.csv"
    csv_file.write_text('isbn,title\n"978-1","Foo, Bar"\n', encoding="utf-8")
    cfg = make_config(str(csv_file))
    importer = CsvImporter(cfg)
    rows = importer.fetch_rows()
    assert rows[0]["title"] == "Foo, Bar"


# ── Scenario 5: UTF-8 BOM ──────────────────────────────────────

def test_s5_utf8_bom(tmp_path):
    csv_file = tmp_path / "bom.csv"
    csv_file.write_bytes(
        b"\xef\xbb\xbf" + "isbn,title\n978-1,BOM Test\n".encode("utf-8")
    )
    cfg = make_config(str(csv_file))
    importer = CsvImporter(cfg)
    rows = importer.fetch_rows()
    assert rows[0]["isbn"] == "978-1"  # BOM이 isbn 컬럼명에 붙지 않아야 함
    assert rows[0]["title"] == "BOM Test"


# ── Scenario 6: 대용량 CSV (1000행) ───────────────────────────

def test_s6_large_csv(tmp_path):
    csv_file = tmp_path / "large.csv"
    lines = ["isbn,title"] + [f"isbn-{i:04d},Book {i}" for i in range(1000)]
    csv_file.write_text("\n".join(lines), encoding="utf-8")
    cfg = make_config(str(csv_file))
    importer = CsvImporter(cfg)
    rows = importer.fetch_rows()
    assert len(rows) == 1000


# ── Scenario 7: 숫자 타입 자동 추론 ──────────────────────────

def test_s7_integer_type_inference():
    cfg = make_config(os.path.join(FIXTURES, "books.csv"))
    importer = CsvImporter(cfg)
    triples = importer.generate_triples()
    year_triples = [t for t in triples if t.predicate == YEAR_PROP]
    assert len(year_triples) == 5
    for t in year_triples:
        assert t.datatype == "http://www.w3.org/2001/XMLSchema#integer"


# ── Scenario 8: 중복 PK (upsert) ─────────────────────────────

def test_s8_duplicate_pk(tmp_path):
    csv_file = tmp_path / "dup.csv"
    csv_file.write_text(
        "isbn,title\n978-1,First\n978-1,Second\n",
        encoding="utf-8",
    )
    cfg = make_config(str(csv_file))
    importer = CsvImporter(cfg)
    triples = importer.generate_triples()
    title_triples = [t for t in triples if t.predicate == TITLE_PROP and "978-1" in t.subject]
    # 마지막 값으로 덮어쓰기: "Second"
    assert len(title_triples) == 1
    assert title_triples[0].object == "Second"


# ── Scenario 9: URL CSV 소스 ──────────────────────────────────
# (실제 네트워크 없이 httpx mock 사용)

def test_s9_url_csv_source(monkeypatch):
    csv_content = "isbn,title\n978-url-1,URL Book\n"

    class MockResponse:
        text = csv_content
        def raise_for_status(self): pass

    class MockHttpx:
        @staticmethod
        def get(url, **kwargs): return MockResponse()

    import services.datasource_import.csv_importer as mod
    monkeypatch.setattr(mod, "httpx", MockHttpx)

    cfg = make_config("https://example.com/books.csv")
    importer = CsvImporter(cfg)
    rows = importer.fetch_rows()
    assert rows[0]["isbn"] == "978-url-1"


# ── Scenario 10: 복수 ClassMapping ───────────────────────────

AUTHOR_CLASS = "http://library.org/onto#Author"
AUTHOR_NAME_PROP = "http://library.org/onto#authorName"

def test_s10_multiple_class_mappings(tmp_path):
    csv_file = tmp_path / "multi.csv"
    csv_file.write_text(
        "isbn,title,authorId,authorName\n"
        "978-1,Book A,author-1,홍길동\n"
        "978-2,Book B,author-2,이영희\n",
        encoding="utf-8",
    )
    config = ImporterConfig(
        connection_info=str(csv_file),
        mappings=[
            ClassMappingConfig(
                target_class=BOOK_CLASS, identifier_field="isbn",
                property_mappings=[PropMappingConfig("title", TITLE_PROP)],
            ),
            ClassMappingConfig(
                target_class=AUTHOR_CLASS, identifier_field="authorId",
                property_mappings=[PropMappingConfig("authorName", AUTHOR_NAME_PROP)],
            ),
        ],
    )
    importer = CsvImporter(config)
    triples = importer.generate_triples()
    book_types = [t for t in triples if t.predicate.endswith("#type") and t.object == BOOK_CLASS]
    author_types = [t for t in triples if t.predicate.endswith("#type") and t.object == AUTHOR_CLASS]
    assert len(book_types) == 2
    assert len(author_types) == 2
```

---

## Step 2 — JSON Importer

### 테스트 시나리오 10개

| # | 시나리오 | 입력 | 기대 결과 |
|---|---------|------|---------|
| 1 | Flat JSON 배열 | `[{"isbn":"...","title":"..."}]` | 5 individuals |
| 2 | JSONPath: 배열 추출 | `{"books":[...]}` + path=`$.books[*]` | 배열 전개 |
| 3 | 중첩 필드 접근 | `{"isbn":"...","meta":{"year":2024}}` + path=`meta.year` | year 값 추출 |
| 4 | null 값 처리 | `{"isbn":"1","title":null}` | title 트리플 생략 |
| 5 | 깊은 중첩 JSONPath | `$.data.items[*].meta.title` | 다단계 경로 |
| 6 | URL JSON 소스 | `https://api.example.com/books` | 다운로드 후 처리 |
| 7 | datetime 값 | `"publishedAt":"2024-01-15T00:00:00Z"` | `xsd:dateTime` |
| 8 | 배열 안 배열 (1:N) | `{"tags":["owl","rdf"]}` | 첫 값만 or 다중 트리플 |
| 9 | 빈 배열 | `[]` | 0 individuals, 에러 없음 |
| 10 | 복수 ClassMapping (동일 JSON) | books + authors 배열 | 각각 매핑 |

### 테스트 데이터 파일

#### `tests/fixtures/books.json`
```json
[
  {"isbn":"978-89-6848-101-8","title":"시맨틱 웹 입문","publishYear":2024},
  {"isbn":"978-89-6848-102-5","title":"온톨로지 설계","publishYear":2023},
  {"isbn":"978-89-6848-103-2","title":"SPARQL 마스터","publishYear":2024},
  {"isbn":"978-89-6848-104-9","title":"지식 표현과 추론","publishYear":2023},
  {"isbn":"978-89-6848-105-6","title":"RDF와 연결 데이터","publishYear":2025}
]
```

#### `tests/fixtures/books_nested.json`
```json
{
  "data": {
    "books": [
      {"isbn":"978-1","meta":{"title":"Nested Book 1","year":2024}},
      {"isbn":"978-2","meta":{"title":"Nested Book 2","year":2023}}
    ]
  }
}
```

#### `tests/fixtures/books_with_authors.json`
```json
{
  "books": [
    {"isbn":"978-89-6848-101-8","title":"시맨틱 웹 입문"},
    {"isbn":"978-89-6848-102-5","title":"온톨로지 설계"}
  ],
  "authors": [
    {"authorId":"auth-001","name":"홍길동"},
    {"authorId":"auth-002","name":"이영희"}
  ]
}
```

### JSONPath 지원 명세

PropertyMapping의 `source_field`에 JSONPath 표기 허용:

```
source_field = "title"          → row["title"]
source_field = "meta.year"      → row["meta"]["year"]  (dot notation)
source_field = "$.tags[0]"      → row["tags"][0]       (JSONPath)
```

ClassMapping의 `json_path` 추가 (배열 진입점):
```
json_path = "$.books[*]"  → json["books"] 배열 순회
json_path = ""            → 최상위가 배열이면 직접 순회
```

---

## Step 3 — REST API Importer

### connection_info 스키마 (JSON 문자열)

```json
{
  "url": "https://api.example.com/books",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {TOKEN}",
    "X-API-Key": "{KEY}"
  },
  "auth": {
    "type": "bearer|apikey|basic",
    "token": "...",
    "header": "X-API-Key"
  },
  "pagination": {
    "type": "offset|cursor|link_header|none",
    "limit_param": "size",
    "offset_param": "page",
    "limit": 100,
    "cursor_field": "nextCursor",
    "cursor_param": "cursor"
  },
  "data_path": "$.results[*]",
  "max_pages": 10
}
```

### 테스트 시나리오 10개

| # | 시나리오 | 입력 | 기대 결과 |
|---|---------|------|---------|
| 1 | 단순 GET → JSON 배열 | mock server, 5 books | 5 individuals |
| 2 | Bearer 토큰 인증 | `Authorization: Bearer token` | 401 없이 200 |
| 3 | API Key 헤더 인증 | `X-API-Key: key` | 인증 성공 |
| 4 | Offset 페이지네이션 | page=1,2 each 3개 | 6 individuals |
| 5 | Cursor 페이지네이션 | nextCursor 방식 | 전체 수집 |
| 6 | Link 헤더 페이지네이션 | RFC 5988 `<url>; rel="next"` | 전체 수집 |
| 7 | max_pages 제한 | 10페이지 이상 API | max_pages 에서 중단 |
| 8 | 응답 에러 처리 | 429 Rate Limit | ImportError 발생, 메시지 포함 |
| 9 | data_path 적용 | `$.results[*]` | 중첩 응답에서 배열 추출 |
| 10 | 타임아웃 처리 | 응답 지연 5s 초과 | TimeoutError → ImportError |

---

## Step 4 — RDB Importer

### connection_info 스키마

```json
{
  "dialect": "sqlite|postgresql|mysql",
  "url": "sqlite:///tmp/library.db",
  "query": "SELECT isbn, title, publish_year FROM books",
  "pk_field": "isbn"
}
```

또는 shorthand URL:
```
sqlite:///tmp/library.db?query=SELECT+*+FROM+books
postgresql://user:pass@localhost:5432/library
mysql://user:pass@localhost:3306/library
```

ClassMapping의 `sql_query` 필드로 테이블별 쿼리 지정.

### 지원 드라이버 (SQLAlchemy)

| dialect | 패키지 | 비고 |
|---------|--------|------|
| `sqlite` | 내장 | 별도 설치 불필요 |
| `postgresql` | `psycopg2-binary` | Docker에 포함 |
| `mysql` | `pymysql` | 선택적 |

### 테스트 시나리오 10개

| # | 시나리오 | 입력 | 기대 결과 |
|---|---------|------|---------|
| 1 | SQLite: `SELECT * FROM books` | 5행 테이블 | 5 individuals |
| 2 | SQLite: JOIN (books + authors) | JOIN 쿼리 | author 이름 포함 트리플 |
| 3 | SQLite: 커스텀 SQL WHERE | `WHERE year > 2023` | 조건 필터링 |
| 4 | SQLite: NULL 컬럼 | `title IS NULL` 1행 | title 트리플 생략 |
| 5 | SQLite: 날짜 컬럼 | `DATE '2024-01-15'` | `xsd:date` 타입 |
| 6 | SQLite: 대용량 (1000행) | 1000행 | 청크 처리, 1000 individuals |
| 7 | SQLite: 복합 PK (연결) | `isbn + '_' + edition` | 복합 PK IRI |
| 8 | SQLite: 복수 ClassMapping | books + authors 테이블 | 각각 매핑 |
| 9 | PostgreSQL: 연결 테스트 | (CI에서 Docker PG) | 연결 성공 |
| 10 | 잘못된 connection URL | `badprotocol://...` | `ImportError("지원하지 않는 dialect")` |

### SQLite 테스트 DB 생성 (`tests/fixtures/library.sqlite`)

```python
# conftest.py
import sqlite3, os

def create_sqlite_fixture():
    db_path = "tests/fixtures/library.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS books (
        isbn TEXT PRIMARY KEY,
        title TEXT,
        author_name TEXT,
        publish_year INTEGER,
        publisher TEXT
    );
    INSERT OR REPLACE INTO books VALUES
        ('978-89-6848-101-8','시맨틱 웹 입문','홍길동',2024,'한빛미디어'),
        ('978-89-6848-102-5','온톨로지 설계','이영희',2023,'위키북스'),
        ('978-89-6848-103-2','SPARQL 마스터','박철수',2024,'한빛미디어'),
        ('978-89-6848-104-9','지식 표현과 추론','김민지',2023,'위키북스'),
        ('978-89-6848-105-6','RDF와 연결 데이터','최동현',2025,'한빛미디어');
    
    CREATE TABLE IF NOT EXISTS authors (
        author_id TEXT PRIMARY KEY,
        name TEXT,
        affiliation TEXT
    );
    INSERT OR REPLACE INTO authors VALUES
        ('auth-001','홍길동','서울대학교'),
        ('auth-002','이영희','KAIST'),
        ('auth-003','박철수','연세대학교');
    """)
    conn.commit()
    conn.close()
```

---

## Step 5 — Frontend Import UI

### Import 버튼 동작

```
[Import 실행] 클릭
      │
      ▼
POST /api/datasources/{ds_iri}/import
  { dataset, graph }
      │
      ▼
  로딩 스피너
      │
      ▼
결과 리포트 표시:
┌─────────────────────────────────────┐
│ ✅ Import 완료                        │
│ 생성된 Individual: 5개               │
│ 트리플: 25개                          │
│ 건너뜀: 0개 (PK 누락)               │
│ 오류: 0개                            │
│                                     │
│ [Individual 탭에서 확인]             │
└─────────────────────────────────────┘
```

### API 엔드포인트

```
POST /api/datasources/{ds_iri:path}/import
Body: { dataset: str, graph: str }
Response: {
  imported_individuals: int,
  inserted_triples: int,
  skipped_rows: int,
  errors: list[str],
  graph: str
}
```

### UI 변경사항 (DatasourcesPanel)

- `DatasourceDetailPanel`에 **Import 실행** 버튼 추가 (미리보기 버튼 옆)
- Import 중 로딩 표시
- Import 완료 후 결과 알림 (`Alert` 컴포넌트)
- "Individual 탭에서 확인" 클릭 시 탭 전환 콜백

---

## Step 6 — connection_info 스키마 구조화

### 현재 문제

현재 `connection_info`는 단순 문자열(`/tmp/file.csv`).  
JSON/REST/RDB는 URL + 옵션이 필요해 JSON 형식으로 저장해야 함.

### 마이그레이션 전략

- **CSV/단순 경로**: 기존 문자열 그대로 유지 (하위 호환)
- **JSON/REST/RDB**: `connection_info`에 JSON 문자열 저장

```python
def parse_connection_info(conn: str) -> dict:
    """connection_info가 JSON이면 파싱, 아니면 {"path": conn}으로 래핑"""
    try:
        return json.loads(conn)
    except (json.JSONDecodeError, TypeError):
        return {"path": conn}
```

### Frontend: 타입별 connection_info 입력 폼

| 타입 | 입력 필드 |
|------|---------|
| CSV | 파일 업로드 / URL 입력 |
| JSON | 파일 업로드 / URL 입력 / JSONPath 입력 |
| REST | URL, 인증 방식, 페이지네이션 설정 |
| RDB | dialect, connection URL, SQL 쿼리 |

---

## 전체 일정 (추정)

| Step | 내용 | 예상 |
|------|------|------|
| Step 1 | CSV Importer + 테스트 | 1 세션 |
| Step 2 | JSON Importer + 테스트 | 1 세션 |
| Step 3 | REST API Importer + 테스트 | 2 세션 |
| Step 4 | RDB Importer + 테스트 | 2 세션 |
| Step 5 | Frontend Import UI | 1 세션 |
| Step 6 | connection_info 스키마 + UI | 1 세션 |

---

## 의존성 추가 (`backend/requirements.txt`)

```
# v05 추가
jsonpath-ng>=1.6.0       # JSONPath 지원
sqlalchemy>=2.0.0        # RDB 어댑터
psycopg2-binary>=2.9.0   # PostgreSQL (선택)
pymysql>=1.1.0           # MySQL (선택)
httpx>=0.27.0            # 이미 있음 (REST/URL CSV)
```

---

## 미결 항목

| # | 항목 |
|---|------|
| 1 | Import 실행 시 기존 트리플 처리: append vs. replace |
| 2 | 스케줄 Import (cron 기반 자동 갱신) |
| 3 | Import 이력 저장 (마지막 실행 시각, 건수) |
| 4 | REST API OAuth2 지원 |
| 5 | RDB JOIN 결과를 Object Property 관계로 매핑하는 방법 |
| 6 | 대용량 Import 비동기 처리 (background task) |
