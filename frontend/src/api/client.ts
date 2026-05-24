// 개발: VITE_API_BASE 미설정 → 'http://localhost:8000' 직접 연결
// Docker: VITE_API_BASE='' → nginx가 /api/ 를 backend 로 프록시
const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

/** IRI를 URL 경로에 포함할 때 반드시 사용 */
export const encodeIRI = (iri: string) => encodeURIComponent(iri)

/** 공통 fetch 래퍼. 에러 시 Error(detail) throw */
export async function apiFetch<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`)
  }
  return res.status === 204 ? (undefined as T) : (res.json() as Promise<T>)
}
