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

// ── v02-C Namespace CRUD ────────────────────────────────────────────────

export interface NsDeclResponse {
  ns_iri: string
  prefix: string
}

export interface RenamePreviewResponse {
  affected_triples: number
  old_ns: string
  new_ns: string
}

export interface RenameNsResponse {
  old_ns: string
  new_ns: string
  affected_triples: number
}

export const declareNamespace = async (
  ds: string, graph: string, ns_iri: string, prefix: string,
): Promise<NsDeclResponse> =>
  apiFetch<NsDeclResponse>('POST', `/api/datasets/${ds}/graphs/namespaces`, {
    graph, ns_iri, prefix,
  })

export const updateNsPrefix = async (
  ds: string, graph: string, ns_iri: string, prefix: string,
): Promise<NsDeclResponse> =>
  apiFetch<NsDeclResponse>('PATCH', `/api/datasets/${ds}/graphs/namespaces`, {
    graph, ns_iri, prefix,
  })

export const previewRenameNs = async (
  ds: string, graph: string, old_ns: string, new_ns: string,
): Promise<RenamePreviewResponse> => {
  const p = new URLSearchParams({ graph, old_ns, new_ns })
  return apiFetch<RenamePreviewResponse>(
    'GET', `/api/datasets/${ds}/graphs/namespaces/rename-preview?${p}`,
  )
}

export const renameNamespace = async (
  ds: string, graph: string, old_ns: string, new_ns: string,
): Promise<RenameNsResponse> =>
  apiFetch<RenameNsResponse>('POST', `/api/datasets/${ds}/graphs/namespaces/rename`, {
    graph, old_ns, new_ns,
  })

export const deleteNamespace = async (
  ds: string, graph: string, ns_iri: string,
): Promise<void> => {
  const p = new URLSearchParams({ graph, ns_iri })
  await apiFetch<void>('DELETE', `/api/datasets/${ds}/graphs/namespaces?${p}`)
}


// ── v03-D Universal Namespace ────────────────────────────────────────────

export interface UniversalNsItem {
  prefix: string
  ns_iri: string
}

export const listUniversalNamespaces = (): Promise<UniversalNsItem[]> =>
  apiFetch<UniversalNsItem[]>('GET', '/api/namespaces/universal')

export const importUniversalNs = (
  dataset: string,
  graph: string,
  prefix: string,
): Promise<{ ns_iri: string; prefix: string; graph: string }> =>
  apiFetch<{ ns_iri: string; prefix: string; graph: string }>(
    'POST', '/api/namespaces/universal/import', { dataset, graph, prefix },
  )


// ── TTL 파일 업로드 ─────────────────────────────────────────────────────────

const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export interface UploadTTLResponse {
  dataset: string
  graph: string
  mode: string
  triple_count: number
  message: string
}

export const uploadTTL = async (
  ds: string,
  graph: string,
  file: File,
  mode: 'append' | 'replace' = 'append',
): Promise<UploadTTLResponse> => {
  const formData = new FormData()
  formData.append('graph', graph)
  formData.append('mode', mode)
  formData.append('file', file)

  const res = await fetch(`${BASE}/api/datasets/${ds}/graphs/upload`, {
    method: 'POST',
    body: formData,
    // Content-Type은 브라우저가 multipart/form-data; boundary=... 자동 설정
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<UploadTTLResponse>
}
