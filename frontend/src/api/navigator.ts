import { apiFetch } from './client'
import type { Dataset, Namespace } from '../types/ontology'

export interface GraphDetail {
  graph:        string
  label:        string | null
  comment:      string | null
  triple_count: number
}

export const checkHealth = () =>
  apiFetch<{ status: string }>('GET', '/api/health')

export const createDataset = async (name: string): Promise<{ name: string }> =>
  apiFetch<{ name: string }>('POST', '/api/datasets', { name })

export const deleteDataset = async (name: string): Promise<void> =>
  apiFetch<void>('DELETE', `/api/datasets/${encodeURIComponent(name)}`)

export const getDatasets = async (): Promise<Dataset[]> => {
  const res = await apiFetch<{ datasets: Dataset[] }>('GET', '/api/datasets')
  return res.datasets
}

export const getGraphs = async (ds: string): Promise<string[]> => {
  const res = await apiFetch<{ graphs: string[] }>('GET', `/api/datasets/${ds}/graphs`)
  return res.graphs
}

export const getGraphDetail = async (ds: string, graph: string): Promise<GraphDetail> => {
  const p = new URLSearchParams({ graph })
  return apiFetch<GraphDetail>('GET', `/api/datasets/${ds}/graphs/detail?${p}`)
}

export const createGraph = async (
  ds: string,
  graph: string,
  label?: string,
): Promise<string> => {
  const res = await apiFetch<{ graph: string }>('POST', `/api/datasets/${ds}/graphs`, {
    graph,
    label: label || undefined,
  })
  return res.graph
}

export const patchGraph = async (
  ds: string,
  graph: string,
  patch: { label?: string; comment?: string },
): Promise<GraphDetail> =>
  apiFetch<GraphDetail>('PATCH', `/api/datasets/${ds}/graphs`, { graph, ...patch })

export const deleteGraph = async (ds: string, graph: string): Promise<void> => {
  const p = new URLSearchParams({ graph })
  await apiFetch<void>('DELETE', `/api/datasets/${ds}/graphs?${p}`)
}

/** 특정 Named Graph 에 속한 Namespace 목록 (custom/universal 구분 포함) */
export const getNamespacesInGraph = async (
  ds: string,
  graph: string,
): Promise<Namespace[]> => {
  const res = await apiFetch<{ namespaces: Namespace[] }>(
    'GET',
    `/api/datasets/${ds}/graphs/namespaces?graph=${encodeURIComponent(graph)}`,
  )
  return res.namespaces
}
