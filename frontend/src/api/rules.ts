import { apiFetch } from './client'

export interface RuleSummary {
  rule_iri: string
  label: string | null
  description: string | null
}

export interface RuleDetail {
  rule_iri: string
  label: string | null
  condition: string
  consequence: string
  description: string | null
}

export interface InferredTriple {
  s: string
  p: string
  o: string
}

export interface ApplyResponse {
  inferred_triples: InferredTriple[]
}

export interface MaterializeResponse {
  materialized_graph: string
  materialized_count: number
}

export const listRules = (dataset: string, graph: string): Promise<RuleSummary[]> => {
  const params = new URLSearchParams({ dataset, graph })
  return apiFetch<RuleSummary[]>('GET', `/api/rules?${params}`)
}

export const createRule = (body: {
  dataset: string
  graph: string
  label: string
  condition: string
  consequence: string
  description?: string
}): Promise<RuleDetail> =>
  apiFetch<RuleDetail>('POST', '/api/rules', body)

export const getRule = (
  dataset: string,
  graph: string,
  ruleIri: string,
): Promise<RuleDetail> => {
  const encoded = encodeURIComponent(ruleIri)
  const params = new URLSearchParams({ dataset, graph })
  return apiFetch<RuleDetail>('GET', `/api/rules/${encoded}?${params}`)
}

export const updateRule = (
  dataset: string,
  graph: string,
  ruleIri: string,
  body: { label?: string; description?: string; condition?: string; consequence?: string },
): Promise<RuleDetail> => {
  const encoded = encodeURIComponent(ruleIri)
  return apiFetch<RuleDetail>('PATCH', `/api/rules/${encoded}`, { dataset, graph, ...body })
}

export const deleteRule = (
  dataset: string,
  graph: string,
  ruleIri: string,
): Promise<{ deleted: string }> => {
  const encoded = encodeURIComponent(ruleIri)
  const params = new URLSearchParams({ dataset, graph })
  return apiFetch<{ deleted: string }>('DELETE', `/api/rules/${encoded}?${params}`)
}

export const applyRule = (
  dataset: string,
  graph: string,
  ruleIri: string,
): Promise<ApplyResponse> => {
  const encoded = encodeURIComponent(ruleIri)
  return apiFetch<ApplyResponse>('POST', `/api/rules/${encoded}/apply`, { dataset, graph })
}

export const materializeRule = (
  dataset: string,
  graph: string,
  ruleIri: string,
): Promise<MaterializeResponse> => {
  const encoded = encodeURIComponent(ruleIri)
  return apiFetch<MaterializeResponse>('POST', `/api/rules/${encoded}/materialize`, { dataset, graph })
}
