import { apiFetch } from './client'

export interface InferredTriple {
  s: string
  p: string
  o: string
}

export interface RunReasoningResponse {
  inferred_triples: InferredTriple[]
  total_inferred: number
  truncated: boolean
}

export interface MaterializeResponse {
  inferred_graph: string
  materialized_count: number
}

export interface ConsistencyResponse {
  consistent: boolean
  details: string | string[]
}

export const runReasoning = async (
  dataset: string, graph: string, reasoner: string,
): Promise<RunReasoningResponse> =>
  apiFetch<RunReasoningResponse>('POST', '/api/reasoning/run', { dataset, graph, reasoner })

export const materializeReasoning = async (
  dataset: string, graph: string, inferred_triples: InferredTriple[],
): Promise<MaterializeResponse> =>
  apiFetch<MaterializeResponse>('POST', '/api/reasoning/materialize', {
    dataset, graph, inferred_triples,
  })

export const checkConsistency = async (
  dataset: string, graph: string,
): Promise<ConsistencyResponse> =>
  apiFetch<ConsistencyResponse>('POST', '/api/reasoning/consistency', { dataset, graph })
