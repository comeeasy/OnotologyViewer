import { apiFetch, encodeIRI } from './client'
import type { IndividualSummary, IndividualDetail } from '../types/ontology'

export const listIndividuals = async (
  ds: string, graphs: string | string[], ns: string | string[], classIri?: string,
): Promise<IndividualSummary[]> => {
  const p = new URLSearchParams({ dataset: ds })
  const graphList = Array.isArray(graphs) ? graphs : [graphs]
  graphList.forEach((g) => p.append('graph', g))
  const nsList = Array.isArray(ns) ? ns : [ns]
  nsList.forEach((n) => p.append('namespace', n))
  if (classIri) p.set('class_iri', classIri)
  const res = await apiFetch<{ individuals: IndividualSummary[] }>(
    'GET', `/api/abox/individuals?${p}`,
  )
  return res.individuals
}

export const createIndividual = async (
  ds: string, graph: string, ns: string,
  body: {
    class_iri: string
    label: string
    comment?: string
    iri?: string
    data_properties?: { property_iri: string; value: string; datatype: string }[]
    object_properties?: { property_iri: string; target_iri: string }[]
  },
): Promise<string> => {
  const res = await apiFetch<{ iri: string }>('POST', '/api/abox/individuals', {
    dataset: ds, graph, namespace: ns, ...body,
  })
  return res.iri
}

export const getIndividual = async (
  ds: string, graph: string, iri: string,
): Promise<IndividualDetail> => {
  const p = new URLSearchParams({ dataset: ds, graph })
  return apiFetch<IndividualDetail>('GET', `/api/abox/individuals/${encodeIRI(iri)}?${p}`)
}

export const updateIndividual = async (
  ds: string, graph: string, iri: string,
  patch: {
    label?: string
    comment?: string
    data_property_updates?: { property_iri: string; value: string; datatype: string }[]
    object_property_updates?: { property_iri: string; target_iri: string; action: 'add' | 'remove' }[]
  },
): Promise<void> => {
  await apiFetch<void>('PATCH', `/api/abox/individuals/${encodeIRI(iri)}`, {
    dataset: ds, graph, ...patch,
  })
}

export const deleteIndividual = async (
  ds: string, graph: string, iri: string,
): Promise<void> => {
  const p = new URLSearchParams({ dataset: ds, graph })
  await apiFetch<void>('DELETE', `/api/abox/individuals/${encodeIRI(iri)}?${p}`)
}

// ── v02-E: Class 마이그레이션 ────────────────────────────────────────────

export interface MigratePreviewResponse {
  individual_iri: string
  current_class_iri: string
  new_class_iri: string
  incompatible_properties: string[]
}

export interface MigrateClassResponse {
  old_class_iri: string
  new_class_iri: string
  deleted_properties: string[]
}

export const previewClassMigrate = async (
  ds: string, graph: string, iri: string, new_class_iri: string,
): Promise<MigratePreviewResponse> => {
  const p = new URLSearchParams({ dataset: ds, graph, new_class_iri })
  return apiFetch<MigratePreviewResponse>(
    'GET', `/api/abox/individuals/${encodeIRI(iri)}/class-migrate-preview?${p}`,
  )
}

export const migrateIndividualClass = async (
  ds: string, graph: string, iri: string,
  new_class_iri: string, incompatible_props: 'keep' | 'delete',
): Promise<MigrateClassResponse> =>
  apiFetch<MigrateClassResponse>('PATCH', `/api/abox/individuals/${encodeIRI(iri)}/class`, {
    dataset: ds, graph, new_class_iri, incompatible_props,
  })
