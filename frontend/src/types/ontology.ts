// ── Navigator ──────────────────────────────────────────
export interface Dataset {
  name: string
  state: string
}

export interface Namespace {
  base_iri: string
  prefix: string | null
  type: 'custom' | 'universal'
}

// ── OOI Context ────────────────────────────────────────
export interface OOIState {
  dataset: string | null
  /** 선택된 Named Graph IRI 배열 (복수 그래프 지원) */
  graphs: string[]
  /** 하위 호환: 첫 번째 선택 그래프 (또는 null) */
  graph: string | null
  /** 하위 호환: 첫 번째 namespace (또는 null) */
  namespace: string | null
  /** v02-I: 선택된 namespace 배열 */
  namespaces: string[]
  setOOI: (dataset: string, graphs: string[], namespaces: string[]) => void
  clear: () => void
}

// ── TBox — Class ───────────────────────────────────────
export interface ClassSummary {
  source_graph?: string | null  // 복수 그래프 지원: 출처 Named Graph IRI
  iri: string
  label: string | null
  comment: string | null
}

export interface ClassDetail extends ClassSummary {
  super_classes: string[]
  sub_classes: string[]
  object_properties: { iri: string; label: string | null; role: string }[]
  data_properties: { iri: string; label: string | null; range: string | null }[]
  individual_count: number
}

// ── TBox — Object Property ─────────────────────────────
// 목록 응답: characteristics 없음 / 상세 응답: characteristics 포함
export interface ObjPropSummary {
  source_graph?: string | null
  iri: string
  label: string | null
  domain: string | null
  range: string | null
}

export interface ObjPropDetail extends ObjPropSummary {
  characteristics: string[]
  inverse_of: string[]
}

// characteristics 가능 값
export const OBJ_PROP_CHARACTERISTICS = [
  'Functional',
  'InverseFunctional',
  'Transitive',
  'Symmetric',
  'Asymmetric',
  'Reflexive',
  'Irreflexive',
] as const

// ── TBox — Data Property ───────────────────────────────
// 목록 응답: functional 없음 / 상세 응답: functional 포함
export interface DataPropSummary {
  source_graph?: string | null
  iri: string
  label: string | null
  domain: string | null
  range: string | null   // full XSD IRI (예: "http://www.w3.org/2001/XMLSchema#integer")
}

export interface DataPropDetail extends DataPropSummary {
  functional: boolean
}

// 생성·수정 시 사용하는 shortname 목록
export const XSD_SHORTTYPES = [
  'string',
  'integer',
  'float',
  'boolean',
  'dateTime',
  'anyURI',
] as const

export type XsdShortType = typeof XSD_SHORTTYPES[number]

// full XSD IRI → shortname 변환
export function xsdShortname(fullIri: string): string {
  const m = fullIri.match(/#(.+)$/)
  return m ? m[1] : fullIri
}

// ── ABox — Individual ──────────────────────────────────
export interface IndividualSummary {
  source_graph?: string | null
  iri: string
  label: string | null
  class_iri: string
}

export interface OutgoingRelation {
  property: string
  value: string
  value_type: 'iri' | 'literal'
  datatype: string | null
}

export interface IncomingRelation {
  subject: string
  property: string
}

export interface IndividualDetail {
  iri: string
  class_iri: string
  label: string | null
  comment: string | null
  outgoing: OutgoingRelation[]
  incoming: IncomingRelation[]
}
