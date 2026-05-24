import { apiFetch } from './client'

// ── Interfaces ──────────────────────────────────────────────────────────────

export interface NodeShapeSummary {
  shape_iri: string
  target_class: string
  label: string | null
}

export interface PropertyShapeItem {
  prop_shape_iri: string
  path: string
  min_count: number | null
  max_count: number | null
  datatype: string | null
  label: string | null
}

export interface NodeShapeDetail {
  shape_iri: string
  target_class: string
  label: string | null
  property_shapes: PropertyShapeItem[]
}

export interface CreateShapeResponse {
  shape_iri: string
  target_class: string
  label: string | null
}

export interface AddPropShapeResponse {
  prop_shape_iri: string
  path: string
}

export interface ViolationItem {
  focus_node: string | null
  message: string | null
  result_path: string | null
  source_shape: string | null
  severity: string | null
}

export interface ValidationResponse {
  conforms: boolean
  violations: ViolationItem[]
}

// ── API Functions ───────────────────────────────────────────────────────────

export const listShapes = (dataset: string, graph: string): Promise<NodeShapeSummary[]> => {
  const params = new URLSearchParams({ dataset, graph })
  return apiFetch<NodeShapeSummary[]>('GET', `/api/shacl/shapes?${params}`)
}

export const createShape = (
  dataset: string,
  graph: string,
  target_class: string,
  label?: string,
): Promise<CreateShapeResponse> =>
  apiFetch<CreateShapeResponse>('POST', '/api/shacl/shapes', { dataset, graph, target_class, label })

export const getShapeDetail = (
  dataset: string,
  graph: string,
  shapeIri: string,
): Promise<NodeShapeDetail> => {
  const encoded = encodeURIComponent(shapeIri)
  const params = new URLSearchParams({ dataset, graph })
  return apiFetch<NodeShapeDetail>('GET', `/api/shacl/shapes/${encoded}?${params}`)
}

export const addPropertyShape = (
  dataset: string,
  graph: string,
  shapeIri: string,
  body: {
    path: string
    min_count?: number | null
    max_count?: number | null
    datatype?: string | null
    min_length?: number | null
    max_length?: number | null
    pattern?: string | null
    label?: string | null
  },
): Promise<AddPropShapeResponse> => {
  const encoded = encodeURIComponent(shapeIri)
  return apiFetch<AddPropShapeResponse>('POST', `/api/shacl/shapes/${encoded}/properties`, {
    dataset,
    graph,
    ...body,
  })
}

export const deletePropertyShape = (
  dataset: string,
  graph: string,
  shapeIri: string,
  propShapeIri: string,
): Promise<{ deleted: string }> => {
  const encodedShape = encodeURIComponent(shapeIri)
  const encodedProp = encodeURIComponent(propShapeIri)
  const params = new URLSearchParams({ dataset, graph })
  return apiFetch<{ deleted: string }>(
    'DELETE',
    `/api/shacl/shapes/${encodedShape}/properties/${encodedProp}?${params}`,
  )
}

export const deleteShape = (
  dataset: string,
  graph: string,
  shapeIri: string,
): Promise<{ deleted: string }> => {
  const encoded = encodeURIComponent(shapeIri)
  const params = new URLSearchParams({ dataset, graph })
  return apiFetch<{ deleted: string }>('DELETE', `/api/shacl/shapes/${encoded}?${params}`)
}

export const validateGraph = (dataset: string, graph: string): Promise<ValidationResponse> =>
  apiFetch<ValidationResponse>('POST', '/api/shacl/validate', { dataset, graph })

export const validateIndividual = (
  dataset: string,
  graph: string,
  individual_iri: string,
): Promise<ValidationResponse> =>
  apiFetch<ValidationResponse>('POST', '/api/shacl/validate/individual', {
    dataset,
    graph,
    individual_iri,
  })
