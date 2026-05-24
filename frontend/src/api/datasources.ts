import { apiFetch } from './client'

export interface DatasourceSummary {
  datasource_iri: string
  label: string | null
  ds_type: string
  connection_info: string
  description: string | null
}

export interface PropertyMappingItem {
  prop_mapping_iri: string
  source_field: string
  target_property: string
}

export interface ClassMappingItem {
  mapping_iri: string
  target_class: string
  identifier_field: string
  label: string | null
  property_mappings: PropertyMappingItem[]
}

export interface DatasourceDetail extends DatasourceSummary {
  mappings: ClassMappingItem[]
}

export const listDatasources = (dataset: string, graph: string): Promise<DatasourceSummary[]> => {
  const params = new URLSearchParams({ dataset, graph })
  return apiFetch<DatasourceSummary[]>('GET', `/api/datasources?${params}`)
}

export const createDatasource = (body: {
  dataset: string
  graph: string
  label: string
  ds_type: string
  connection_info: string
  description?: string
}): Promise<DatasourceSummary> =>
  apiFetch<DatasourceSummary>('POST', '/api/datasources', body)

export const getDatasource = (
  dataset: string,
  graph: string,
  dsIri: string,
): Promise<DatasourceDetail> => {
  const encoded = encodeURIComponent(dsIri)
  const params = new URLSearchParams({ dataset, graph })
  return apiFetch<DatasourceDetail>('GET', `/api/datasources/${encoded}?${params}`)
}

export const updateDatasource = (
  dataset: string,
  graph: string,
  dsIri: string,
  body: { label?: string; ds_type?: string; connection_info?: string; description?: string },
): Promise<DatasourceDetail> => {
  const encoded = encodeURIComponent(dsIri)
  return apiFetch<DatasourceDetail>('PATCH', `/api/datasources/${encoded}`, { dataset, graph, ...body })
}

export const deleteDatasource = (
  dataset: string,
  graph: string,
  dsIri: string,
): Promise<{ deleted: string }> => {
  const encoded = encodeURIComponent(dsIri)
  const params = new URLSearchParams({ dataset, graph })
  return apiFetch<{ deleted: string }>('DELETE', `/api/datasources/${encoded}?${params}`)
}

export const addClassMapping = (
  dataset: string,
  graph: string,
  dsIri: string,
  body: { target_class: string; identifier_field: string; label?: string },
): Promise<{ mapping_iri: string; target_class: string; identifier_field: string }> => {
  const encoded = encodeURIComponent(dsIri)
  return apiFetch('POST', `/api/datasources/${encoded}/mappings`, { dataset, graph, ...body })
}

export const deleteClassMapping = (
  dataset: string,
  graph: string,
  dsIri: string,
  mappingIri: string,
): Promise<{ deleted: string }> => {
  const encodedDs = encodeURIComponent(dsIri)
  const encodedMap = encodeURIComponent(mappingIri)
  const params = new URLSearchParams({ dataset, graph })
  return apiFetch<{ deleted: string }>(
    'DELETE',
    `/api/datasources/${encodedDs}/mappings/${encodedMap}?${params}`,
  )
}

export const previewDatasource = (
  dataset: string,
  graph: string,
  dsIri: string,
  limit = 10,
): Promise<{
  datasource_iri: string
  label: string | null
  type: string
  connection_info: string
  rows: unknown[]
  error: string | null
}> => {
  const encoded = encodeURIComponent(dsIri)
  const params = new URLSearchParams({ dataset, graph, limit: String(limit) })
  return apiFetch('GET', `/api/datasources/${encoded}/preview?${params}`)
}

export const addPropertyMapping = (
  dataset: string,
  graph: string,
  dsIri: string,
  mappingIri: string,
  body: { source_field: string; target_property: string },
): Promise<{ prop_mapping_iri: string; source_field: string; target_property: string }> => {
  const encodedDs = encodeURIComponent(dsIri)
  const encodedMap = encodeURIComponent(mappingIri)
  return apiFetch(
    'POST',
    `/api/datasources/${encodedDs}/mappings/${encodedMap}/properties`,
    { dataset, graph, ...body },
  )
}
