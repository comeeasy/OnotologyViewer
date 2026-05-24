import { apiFetch, encodeIRI } from './client'
import type { ObjPropSummary, ObjPropDetail } from '../types/ontology'

export const listObjProps = async (
  ds: string, graph: string, ns: string,
): Promise<ObjPropSummary[]> => {
  const p = new URLSearchParams({ dataset: ds, graph, namespace: ns })
  const res = await apiFetch<{ object_properties: ObjPropSummary[] }>(
    'GET', `/api/tbox/object-properties?${p}`,
  )
  return res.object_properties
}

export const createObjProp = async (
  ds: string, graph: string, ns: string,
  body: { label: string; domain?: string; range?: string; characteristics: string[] },
): Promise<string> => {
  const res = await apiFetch<{ iri: string }>('POST', '/api/tbox/object-properties', {
    dataset: ds, graph, namespace: ns, ...body,
  })
  return res.iri
}

export const getObjProp = async (
  ds: string, graph: string, iri: string,
): Promise<ObjPropDetail> => {
  const p = new URLSearchParams({ dataset: ds, graph })
  return apiFetch<ObjPropDetail>('GET', `/api/tbox/object-properties/${encodeIRI(iri)}?${p}`)
}

export const updateObjProp = async (
  ds: string, graph: string, iri: string,
  patch: { label?: string; domain?: string | null; range?: string | null; characteristics?: string[] },
): Promise<void> => {
  await apiFetch<void>('PATCH', `/api/tbox/object-properties/${encodeIRI(iri)}`, {
    dataset: ds, graph, ...patch,
  })
}

export const deleteObjProp = async (
  ds: string, graph: string, iri: string,
): Promise<void> => {
  const p = new URLSearchParams({ dataset: ds, graph })
  await apiFetch<void>('DELETE', `/api/tbox/object-properties/${encodeIRI(iri)}?${p}`)
}
