import { apiFetch } from './client'

export interface FusekiConfig {
  fuseki_base_url: string
  fuseki_admin_user: string
  fuseki_admin_password: string
}

export const getFusekiConfig = () =>
  apiFetch<FusekiConfig>('GET', '/api/config/fuseki')

export const patchFusekiConfig = (body: {
  fuseki_base_url: string
  fuseki_admin_user?: string
  fuseki_admin_password?: string
}) => apiFetch<FusekiConfig>('PATCH', '/api/config/fuseki', body)

export const testFusekiConnection = (url: string) =>
  apiFetch<{ reachable: boolean; url: string }>(
    'POST', '/api/config/fuseki/test', { fuseki_base_url: url },
  )
