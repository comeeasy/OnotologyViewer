import { apiFetch, encodeIRI } from './client'
import type { DataPropSummary, DataPropDetail } from '../types/ontology'

export const listDataProps = async (
  ds: string, graphs: string | string[], ns: string | string[],
): Promise<DataPropSummary[]> => {
  const p = new URLSearchParams({ dataset: ds })
  const graphList = Array.isArray(graphs) ? graphs : [graphs]
  graphList.forEach((g) => p.append('graph', g))
  const nsList = Array.isArray(ns) ? ns : [ns]
  nsList.forEach((n) => p.append('namespace', n))
  const res = await apiFetch<{ data_properties: DataPropSummary[] }>(
    'GET', `/api/tbox/data-properties?${p}`,
  )
  return res.data_properties
}

export const createDataProp = async (
  ds: string, graph: string, ns: string,
  body: { label: string; domain: string; range: string; functional: boolean },
): Promise<string> => {
  const res = await apiFetch<{ iri: string }>('POST', '/api/tbox/data-properties', {
    dataset: ds, graph, namespace: ns, ...body,
  })
  return res.iri
}

export const getDataProp = async (
  ds: string, graph: string, iri: string,
): Promise<DataPropDetail> => {
  const p = new URLSearchParams({ dataset: ds, graph })
  return apiFetch<DataPropDetail>('GET', `/api/tbox/data-properties/${encodeIRI(iri)}?${p}`)
}

export const updateDataProp = async (
  ds: string, graph: string, iri: string,
  patch: { label?: string; domain?: string; range?: string; functional?: boolean },
): Promise<void> => {
  await apiFetch<void>('PATCH', `/api/tbox/data-properties/${encodeIRI(iri)}`, {
    dataset: ds, graph, ...patch,
  })
}

export const deleteDataProp = async (
  ds: string, graph: string, iri: string,
): Promise<void> => {
  const p = new URLSearchParams({ dataset: ds, graph })
  await apiFetch<void>('DELETE', `/api/tbox/data-properties/${encodeIRI(iri)}?${p}`)
}
