import { apiFetch } from './client'

export interface SparqlQueryResponse {
  query_type: 'select' | 'ask'
  results: Record<string, string>[]
  boolean: boolean | null
}

export interface SparqlUpdateResponse {
  success: boolean
  message: string
}

export const runSparqlQuery = async (
  dataset: string, graph: string, query: string,
): Promise<SparqlQueryResponse> =>
  apiFetch<SparqlQueryResponse>('POST', '/api/sparql/query', { dataset, graph, query })

export const runSparqlUpdate = async (
  dataset: string, graph: string, update: string,
): Promise<SparqlUpdateResponse> =>
  apiFetch<SparqlUpdateResponse>('POST', '/api/sparql/update', { dataset, graph, update })
