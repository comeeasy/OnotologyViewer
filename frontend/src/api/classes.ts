import { apiFetch, encodeIRI } from './client'
import type { ClassSummary, ClassDetail } from '../types/ontology'

/** dataset + 복수 그래프 + 복수 namespace 를 URLSearchParams로 빌드 */
function buildParams(ds: string, graphs: string | string[], ns: string | string[]): URLSearchParams {
  const p = new URLSearchParams({ dataset: ds })
  const graphList = Array.isArray(graphs) ? graphs : [graphs]
  graphList.forEach((g) => p.append('graph', g))
  const nsList = Array.isArray(ns) ? ns : [ns]
  nsList.forEach((n) => p.append('namespace', n))
  return p
}

export const listClasses = async (
  ds: string, graphs: string | string[], ns: string | string[],
): Promise<ClassSummary[]> => {
  const p = buildParams(ds, graphs, ns)
  const res = await apiFetch<{ classes: ClassSummary[] }>('GET', `/api/tbox/classes?${p}`)
  return res.classes
}

export const createClass = async (
  ds: string, graph: string, ns: string, label: string, comment: string,
): Promise<string> => {
  const res = await apiFetch<{ iri: string }>('POST', '/api/tbox/classes', {
    dataset: ds, graph, namespace: ns, label, comment,
  })
  return res.iri
}

export const getClass = async (
  ds: string, graph: string, iri: string,
): Promise<ClassDetail> => {
  const p = new URLSearchParams({ dataset: ds, graph })
  return apiFetch<ClassDetail>('GET', `/api/tbox/classes/${encodeIRI(iri)}?${p}`)
}

export const updateClass = async (
  ds: string, graph: string, iri: string,
  patch: { label?: string; comment?: string },
): Promise<void> => {
  await apiFetch<void>('PATCH', `/api/tbox/classes/${encodeIRI(iri)}`, {
    dataset: ds, graph, ...patch,
  })
}

export const deleteClass = async (
  ds: string, graph: string, iri: string,
  onIndividual: 'delete' | 'migrate' = 'delete',
  targetClassIri?: string,
): Promise<void> => {
  const p = new URLSearchParams({ dataset: ds, graph, on_individual: onIndividual })
  if (targetClassIri) p.set('target_class_iri', targetClassIri)
  await apiFetch<void>('DELETE', `/api/tbox/classes/${encodeIRI(iri)}?${p}`)
}

export const addSuperClass = async (
  ds: string, graph: string, childIri: string, parentIri: string,
): Promise<void> => {
  await apiFetch<void>('POST', `/api/tbox/classes/${encodeIRI(childIri)}/super-classes`, {
    dataset: ds, graph, parent_iri: parentIri,
  })
}

export const removeSuperClass = async (
  ds: string, graph: string, childIri: string, parentIri: string,
): Promise<void> => {
  const p = new URLSearchParams({ dataset: ds, graph })
  await apiFetch<void>(
    'DELETE',
    `/api/tbox/classes/${encodeIRI(childIri)}/super-classes/${encodeIRI(parentIri)}?${p}`,
  )
}
