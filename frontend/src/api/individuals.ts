import { apiFetch, encodeIRI } from './client'
import type { IndividualSummary, IndividualDetail } from '../types/ontology'

export const listIndividuals = async (
  ds: string, graph: string, ns: string, classIri?: string,
): Promise<IndividualSummary[]> => {
  const p = new URLSearchParams({ dataset: ds, graph, namespace: ns })
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
