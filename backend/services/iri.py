"""IRI 자동 생성기 — content-addressed.

형식: {baseIRI}{PascalCaseSlug}_{SHA256(graph + label + timestamp_ns)[:64]}

설계 근거:
- DB 조회 없음
- 입력(graph, label, timestamp_ns)이 같으면 IRI도 같음 → 결정적
- timestamp_ns 가 다르면 IRI도 다름 → 중복 허용 (동명 개체 허용)
- SHA256 출력 256-bit: birthday bound ≈ 2^128 ≈ 3.4 × 10^38 건에서 충돌 확률 50%
- 충돌 확률 0이 아니나 어떠한 현실적 규모에서도 무시 가능한 수준
- 구분자 \x00 사용: "ab" + "c" 와 "a" + "bc" 가 같은 hash 로 합쳐지는
  prefix-collision 방지
"""

import hashlib
import re
import time


def _to_pascal(label: str) -> str:
    """
    임의 문자열을 PascalCase 슬러그로 변환한다.

    예)  "my ontology class" → "MyOntologyClass"
         "person_type"       → "PersonType"
         "HTTPRequest"       → "HTTPRequest"  (이미 PascalCase면 유지)
    """
    words = re.split(r"[\s_\-]+", label.strip())
    return "".join(w.capitalize() for w in words if w)


def generate_iri(base_iri: str, label: str, graph: str) -> str:
    """
    content-addressed IRI를 생성한다.

    Args:
        base_iri:  Namespace base IRI (e.g. "http://myorg.com/onto#")
        label:     인간 친화적 이름 (e.g. "Person", "has name")
        graph:     소속 Named Graph IRI (e.g. "http://myorg.com/graph/main")

    Returns:
        e.g. "http://myorg.com/onto#Person_3a7f2b..."  (suffix = 64자리 hex)
    """
    timestamp_ns = str(time.time_ns())
    content = f"{graph}\x00{label}\x00{timestamp_ns}".encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()  # 256-bit → 64자리 hex
    slug = _to_pascal(label)
    return f"{base_iri}{slug}_{digest}"
