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
  graph: string | null
  namespace: string | null
  setOOI: (dataset: string, graph: string, namespace: string) => void
  clear: () => void
}

// ── TBox — Class ───────────────────────────────────────
export interface ClassSummary {
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
  iri: string
  label: string | null
  class_iri: string
}

export interface OutgoingRelation {
  property: string
  value: string
  value_type: 'iri' | 'literal'
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
