/**
 * v02-F SPARQL Editor (+ v05 Builder 모드)
 * - OOI Named Graph 범위 내에서 SPARQL SELECT/ASK/UPDATE 실행
 * - 쿼리 히스토리 (localStorage 최근 10개)
 * - 빌더 모드: SELECT / INSERT DATA / ASK / DELETE WHERE
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert, Badge, Button, Checkbox, Divider, Input,
  InputNumber, Select, Segmented, Space, Table,
  Tag, Tooltip, Typography, message,
} from 'antd'
import {
  BuildOutlined, ClockCircleOutlined, CodeOutlined,
  HistoryOutlined, MinusCircleOutlined,
  PlayCircleOutlined, PlusOutlined,
} from '@ant-design/icons'
import { useOOI } from '../../context/OOIContext'
import { runSparqlQuery, runSparqlUpdate } from '../../api/sparqlEditor'
import { listClasses } from '../../api/classes'
import { listObjProps } from '../../api/objProps'
import { listDataProps } from '../../api/dataProps'
import type { ClassSummary, ObjPropSummary, DataPropSummary } from '../../types/ontology'

const { Text, Title } = Typography

// ── 히스토리 ──────────────────────────────────────────────────────────────

const HISTORY_KEY = 'sparql_editor_history'
const MAX_HISTORY = 10

function loadHistory(): string[] {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? '[]') } catch { return [] }
}
function saveHistory(queries: string[]) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(queries.slice(0, MAX_HISTORY)))
}
function addToHistory(query: string, history: string[]): string[] {
  const trimmed = query.trim()
  if (!trimmed) return history
  return [trimmed, ...history.filter((q) => q !== trimmed)].slice(0, MAX_HISTORY)
}

// ── SPARQL 빌더 ──────────────────────────────────────────────────────────

type QueryType = 'select' | 'insert' | 'ask' | 'delete'

interface TriplePattern {
  id: string
  subject: string
  predicateType: 'type' | 'objprop' | 'dataprop'
  predicateIri: string
  object: string
}

function makeRow(): TriplePattern {
  return { id: Math.random().toString(36).slice(2), subject: '', predicateType: 'type', predicateIri: '', object: '' }
}

function rowsToSparql(rows: TriplePattern[]): string {
  return rows
    .filter((r) => r.subject)
    .map((r) => {
      if (r.predicateType === 'type') {
        return r.object ? `${r.subject} a <${r.object}> .` : `${r.subject} a ?class .`
      }
      const obj = r.object || '?value'
      return r.predicateIri ? `${r.subject} <${r.predicateIri}> ${obj} .` : `${r.subject} ?p ${obj} .`
    })
    .join('\n')
}

function detectVars(rows: TriplePattern[]): string[] {
  const vars = new Set<string>()
  rows.forEach((r) => {
    if (r.subject.startsWith('?')) vars.add(r.subject)
    if (r.object.startsWith('?')) vars.add(r.object)
  })
  return Array.from(vars)
}

function buildSparql(
  queryType: QueryType,
  whereRows: TriplePattern[],
  selectedVars: string[],
  limit: number | null,
  graph: string,
): string {
  const patterns = rowsToSparql(whereRows)
  const indented = patterns.replace(/^/gm, '  ')

  if (queryType === 'select') {
    const vars = selectedVars.length > 0 ? selectedVars.join(' ') : '*'
    const limitLine = limit ? `\nLIMIT ${limit}` : ''
    return `SELECT ${vars} WHERE {\n${indented}\n}${limitLine}`
  }
  if (queryType === 'ask') {
    return `ASK {\n${indented}\n}`
  }
  if (queryType === 'insert') {
    return `INSERT DATA {\n  GRAPH <${graph}> {\n${patterns.replace(/^/gm, '    ')}\n  }\n}`
  }
  if (queryType === 'delete') {
    return `DELETE WHERE {\n  GRAPH <${graph}> {\n${patterns.replace(/^/gm, '    ')}\n  }\n}`
  }
  return ''
}

const localName = (iri: string) => iri.split(/[#/]/).filter(Boolean).pop() ?? iri

// ── TriplePatternBuilder ────────────────────────────────────────────────

interface TriplePatternBuilderProps {
  rows: TriplePattern[]
  onChange: (rows: TriplePattern[]) => void
  classes: ClassSummary[]
  objProps: ObjPropSummary[]
  dataProps: DataPropSummary[]
  showObjectInput?: boolean  // INSERT/DELETE: object도 IRI 입력 허용
}

const TriplePatternBuilder: React.FC<TriplePatternBuilderProps> = ({
  rows, onChange, classes, objProps, dataProps,
}) => {
  const update = (id: string, patch: Partial<TriplePattern>) =>
    onChange(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)))
  const remove = (id: string) => onChange(rows.filter((r) => r.id !== id))
  const add = () => onChange([...rows, makeRow()])

  const classOptions = classes.map((c) => ({
    label: c.label ?? localName(c.iri), value: c.iri, title: c.iri,
  }))

  const predicateOptions = [
    {
      label: '타입',
      options: [{ label: 'a (rdf:type)', value: '__type__' }],
    },
    {
      label: 'Object Property',
      options: objProps.map((p) => ({
        label: p.label ?? localName(p.iri), value: `objprop::${p.iri}`, title: p.iri,
      })),
    },
    {
      label: 'Data Property',
      options: dataProps.map((p) => ({
        label: p.label ?? localName(p.iri), value: `dataprop::${p.iri}`, title: p.iri,
      })),
    },
  ]

  const predicateValue = (row: TriplePattern) => {
    if (row.predicateType === 'type') return '__type__'
    return row.predicateIri
      ? `${row.predicateType}::${row.predicateIri}`
      : undefined
  }

  const handlePredicateChange = (id: string, val: string) => {
    if (val === '__type__') update(id, { predicateType: 'type', predicateIri: '', object: '' })
    else if (val.startsWith('objprop::'))
      update(id, { predicateType: 'objprop', predicateIri: val.replace('objprop::', ''), object: '' })
    else if (val.startsWith('dataprop::'))
      update(id, { predicateType: 'dataprop', predicateIri: val.replace('dataprop::', ''), object: '' })
  }

  return (
    <div>
      {rows.map((row) => (
        <div key={row.id} style={{ display: 'flex', gap: 6, marginBottom: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          <Input
            size="small" placeholder="?subject" value={row.subject}
            onChange={(e) => update(row.id, { subject: e.target.value })}
            style={{ width: 90, fontFamily: 'monospace' }}
          />
          <Select
            size="small" placeholder="술어 선택"
            value={predicateValue(row)}
            onChange={(v) => handlePredicateChange(row.id, v)}
            options={predicateOptions}
            style={{ width: 200 }} showSearch optionFilterProp="label" allowClear
          />
          {row.predicateType === 'type' ? (
            <Select
              size="small" placeholder="Class 또는 ?var"
              value={row.object || undefined}
              onChange={(v) => update(row.id, { object: v })}
              options={classOptions}
              style={{ width: 180 }} showSearch optionFilterProp="label" allowClear
            />
          ) : (
            <Input
              size="small" placeholder="?variable 또는 값"
              value={row.object}
              onChange={(e) => update(row.id, { object: e.target.value })}
              style={{ width: 140, fontFamily: 'monospace' }}
            />
          )}
          <Button type="text" danger size="small" icon={<MinusCircleOutlined />} onClick={() => remove(row.id)} />
        </div>
      ))}
      <Button size="small" icon={<PlusOutlined />} onClick={add} style={{ marginTop: 2 }}>
        패턴 추가
      </Button>
    </div>
  )
}

// ── SPARQL 빌더 패널 ────────────────────────────────────────────────────

interface SparqlBuilderProps {
  graph: string
  classes: ClassSummary[]
  objProps: ObjPropSummary[]
  dataProps: DataPropSummary[]
  onGenerate: (sparql: string) => void
}

const QUERY_TYPE_OPTIONS = [
  { value: 'select', label: 'SELECT' },
  { value: 'ask',    label: 'ASK' },
  { value: 'insert', label: 'INSERT DATA' },
  { value: 'delete', label: 'DELETE WHERE' },
]

const SparqlBuilder: React.FC<SparqlBuilderProps> = ({
  graph, classes, objProps, dataProps, onGenerate,
}) => {
  const [queryType, setQueryType] = useState<QueryType>('select')
  const [whereRows, setWhereRows] = useState<TriplePattern[]>([makeRow()])
  const [checkedVars, setCheckedVars] = useState<Set<string>>(new Set())
  const [limit, setLimit] = useState<number | null>(100)
  const [insertGraph, setInsertGraph] = useState(graph)

  // graph prop 바뀌면 동기화
  useEffect(() => setInsertGraph(graph), [graph])

  // WHERE 패턴에서 변수 자동 감지
  const detectedVars = useMemo(() => detectVars(whereRows), [whereRows])

  // 새 변수 자동 체크
  useEffect(() => {
    setCheckedVars((prev) => {
      const next = new Set(prev)
      detectedVars.forEach((v) => next.add(v))
      return next
    })
  }, [detectedVars.join(',')])

  const selectedVars = detectedVars.filter((v) => checkedVars.has(v))

  const preview = useMemo(
    () => buildSparql(queryType, whereRows, selectedVars, limit, insertGraph),
    [queryType, whereRows, selectedVars, limit, insertGraph],
  )

  return (
    <div style={{ border: '1px solid #e8e8e8', borderRadius: 6, padding: 12, background: '#fafafa' }}>
      {/* 쿼리 타입 */}
      <Space style={{ marginBottom: 12 }}>
        <Text strong style={{ fontSize: 13 }}>쿼리 유형:</Text>
        <Select
          value={queryType}
          onChange={(v) => setQueryType(v as QueryType)}
          options={QUERY_TYPE_OPTIONS}
          style={{ width: 140 }}
          size="small"
        />
      </Space>

      {/* WHERE / 트리플 패턴 */}
      <div style={{ marginBottom: 12 }}>
        <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
          {queryType === 'insert' ? 'INSERT 트리플' : queryType === 'delete' ? 'DELETE 패턴' : 'WHERE 패턴'}
        </Text>
        <TriplePatternBuilder
          rows={whereRows}
          onChange={setWhereRows}
          classes={classes}
          objProps={objProps}
          dataProps={dataProps}
        />
      </div>

      {/* SELECT 전용: 변수 선택 + LIMIT */}
      {queryType === 'select' && (
        <Space direction="vertical" size={6} style={{ width: '100%', marginBottom: 12 }}>
          {detectedVars.length > 0 && (
            <div>
              <Text strong style={{ fontSize: 12 }}>SELECT 변수:</Text>
              <Space style={{ marginLeft: 8 }}>
                {detectedVars.map((v) => (
                  <Checkbox
                    key={v}
                    checked={checkedVars.has(v)}
                    onChange={(e) => {
                      const next = new Set(checkedVars)
                      e.target.checked ? next.add(v) : next.delete(v)
                      setCheckedVars(next)
                    }}
                  >
                    <Text style={{ fontFamily: 'monospace', fontSize: 12 }}>{v}</Text>
                  </Checkbox>
                ))}
                {detectedVars.length > 0 && selectedVars.length === 0 && (
                  <Tag color="orange">미선택 → SELECT *</Tag>
                )}
              </Space>
            </div>
          )}
          <Space>
            <Text strong style={{ fontSize: 12 }}>LIMIT:</Text>
            <InputNumber
              size="small" min={1} max={10000}
              value={limit ?? undefined}
              onChange={(v) => setLimit(v ?? null)}
              style={{ width: 90 }}
              placeholder="없음"
            />
          </Space>
        </Space>
      )}

      {/* INSERT / DELETE 전용: 대상 GRAPH */}
      {(queryType === 'insert' || queryType === 'delete') && (
        <div style={{ marginBottom: 12 }}>
          <Text strong style={{ fontSize: 12 }}>대상 GRAPH:</Text>
          <Input
            size="small" value={insertGraph}
            onChange={(e) => setInsertGraph(e.target.value)}
            style={{ width: '100%', fontFamily: 'monospace', fontSize: 11, marginTop: 4 }}
          />
        </div>
      )}

      {/* SPARQL 미리보기 */}
      {preview && (
        <div style={{ marginBottom: 10 }}>
          <Text strong style={{ fontSize: 12 }}>생성된 SPARQL:</Text>
          <pre style={{
            fontFamily: 'monospace', fontSize: 11, background: '#f0f0f0',
            padding: '6px 10px', borderRadius: 4, margin: '4px 0 0',
            maxHeight: 120, overflow: 'auto', whiteSpace: 'pre-wrap',
          }}>
            {preview}
          </pre>
        </div>
      )}

      <Space>
        <Button
          type="primary" size="small"
          onClick={() => onGenerate(preview)}
          disabled={!preview}
        >
          SPARQL 편집기로 보내기
        </Button>
        <Button size="small" onClick={() => { setWhereRows([makeRow()]); setCheckedVars(new Set()) }}>
          초기화
        </Button>
      </Space>
    </div>
  )
}

// ── Main SparqlEditor ──────────────────────────────────────────────────

const SparqlEditor: React.FC = () => {
  const { dataset, graph, graphs, namespace, navigate } = useOOI()

  const [query, setQuery]   = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<{
    type: 'select' | 'ask' | 'update' | 'error'
    columns?: string[]
    rows?: Record<string, string>[]
    boolean?: boolean
    message?: string
  } | null>(null)

  const [history, setHistory]     = useState<string[]>(loadHistory)
  const [showHistory, setShowHistory] = useState(false)
  const [mode, setMode]           = useState<'builder' | 'sparql'>('sparql')

  // 빌더용 온톨로지 데이터
  const [classes, setClasses]     = useState<ClassSummary[]>([])
  const [objProps, setObjProps]   = useState<ObjPropSummary[]>([])
  const [dataProps, setDataProps] = useState<DataPropSummary[]>([])

  // ── 결과 IRI 라벨 맵 ────────────────────────────────────────────────────
  const [resultLabelMap, setResultLabelMap] = useState<Record<string, string>>({})

  // 온톨로지에서 가져온 라벨 (클래스/프로퍼티)
  const ontologyLabelMap = useMemo<Record<string, string>>(() => {
    const map: Record<string, string> = {}
    classes.forEach(c => { if (c.label) map[c.iri] = c.label })
    objProps.forEach(p => { if (p.label) map[p.iri] = p.label })
    dataProps.forEach(p => { if (p.label) map[p.iri] = p.label })
    return map
  }, [classes, objProps, dataProps])

  // 두 맵 합산
  const labelMap = useMemo(
    () => ({ ...ontologyLabelMap, ...resultLabelMap }),
    [ontologyLabelMap, resultLabelMap],
  )

  // SPARQL 결과에서 미지 IRI들의 rdfs:label 일괄 조회
  const fetchResultLabels = useCallback(async (rows: Record<string, string>[]) => {
    if (!dataset || !graph) return
    const iris = new Set<string>()
    rows.forEach(row =>
      Object.values(row).forEach(v => {
        if (typeof v === 'string' && v.startsWith('http') && !ontologyLabelMap[v])
          iris.add(v)
      }),
    )
    if (iris.size === 0) return
    const values = Array.from(iris).map(i => `<${i}>`).join(' ')
    try {
      const res = await runSparqlQuery(
        dataset, graph,
        `SELECT ?s ?label WHERE { VALUES ?s { ${values} } OPTIONAL { ?s <http://www.w3.org/2000/01/rdf-schema#label> ?label } }`,
      )
      const map: Record<string, string> = {}
      res.results.forEach((r: Record<string, string>) => { if (r.label) map[r.s] = r.label })
      setResultLabelMap(prev => ({ ...prev, ...map }))
    } catch { /* 무시 */ }
  }, [dataset, graph, ontologyLabelMap])

  // IRI인지 감지 (boolean 반환 — string 타입 좁히기 없이 사용)
  const isIri = (v: string): boolean =>
    v.startsWith('http://') || v.startsWith('https://')

  // 엔티티 타입 감지 → 이동할 탭 결정
  const detectTab = useCallback((iri: string): string => {
    if (classes.some(c => c.iri === iri)) return 'classes'
    if (objProps.some(p => p.iri === iri)) return 'objprops'
    if (dataProps.some(p => p.iri === iri)) return 'dataprops'
    return 'individuals'
  }, [classes, objProps, dataProps])

  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => { saveHistory(history) }, [history])

  useEffect(() => {
    if (!dataset || graphs.length === 0 || !namespace) return
    Promise.all([
      listClasses(dataset, graphs, namespace),
      listObjProps(dataset, graphs, namespace),
      listDataProps(dataset, graphs, namespace),
    ]).then(([c, op, dp]) => { setClasses(c); setObjProps(op); setDataProps(dp) })
      .catch(() => { /* 무시 */ })
  }, [dataset, graphs, namespace])

  const isUpdateQuery = (q: string) =>
    /^\s*(INSERT|DELETE|LOAD|CLEAR|CREATE|DROP|COPY|MOVE|ADD)\b/i.test(q.trim())

  const handleRun = async () => {
    if (!dataset || !graph) { message.warning('OOI를 먼저 설정하세요.'); return }
    const q = query.trim()
    if (!q) return
    setRunning(true)
    setResult(null)
    try {
      if (isUpdateQuery(q)) {
        const res = await runSparqlUpdate(dataset, graph, q)
        setResult({ type: 'update', message: res.message })
        message.success(res.message)
      } else {
        const res = await runSparqlQuery(dataset, graph, q)
        if (res.query_type === 'ask') {
          setResult({ type: 'ask', boolean: res.boolean ?? false })
        } else {
          const columns = res.results.length > 0 ? Object.keys(res.results[0]) : []
          setResult({ type: 'select', columns, rows: res.results })
          fetchResultLabels(res.results) // 백그라운드 라벨 조회
        }
      }
      setHistory((h) => addToHistory(q, h))
    } catch (e: unknown) {
      setResult({ type: 'error', message: (e as Error).message })
    } finally {
      setRunning(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); handleRun() }
  }

  const handleBuilderGenerate = (sparql: string) => {
    setQuery(sparql)
    setMode('sparql')
    setTimeout(() => textareaRef.current?.focus(), 100)
  }

  return (
    <div style={{ padding: '8px 0' }}>
      {/* 헤더 */}
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 8 }}>
        <Title level={5} style={{ margin: 0 }}>🔍 SPARQL Editor</Title>
        <Space>
          {dataset && graph && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              Graph: <Text code style={{ fontSize: 10 }}>
                {graph.length > 40 ? '…' + graph.slice(-39) : graph}
              </Text>
            </Text>
          )}
          <Segmented
            size="small"
            value={mode}
            onChange={(v) => setMode(v as 'builder' | 'sparql')}
            options={[
              { value: 'builder', icon: <BuildOutlined />, label: '빌더' },
              { value: 'sparql',  icon: <CodeOutlined />,  label: 'SPARQL' },
            ]}
          />
          <Button size="small" icon={<HistoryOutlined />} onClick={() => setShowHistory(!showHistory)}>
            히스토리
          </Button>
        </Space>
      </Space>

      {/* 히스토리 */}
      {showHistory && (
        <div style={{
          border: '1px solid #d9d9d9', borderRadius: 4, padding: 8,
          marginBottom: 8, maxHeight: 200, overflowY: 'auto', background: '#fafafa',
        }}>
          {history.length === 0
            ? <Text type="secondary">히스토리가 없습니다.</Text>
            : history.map((q, i) => (
              <div
                key={i}
                style={{ cursor: 'pointer', padding: '4px 0', borderBottom: '1px solid #f0f0f0' }}
                onClick={() => { setQuery(q); setShowHistory(false); setMode('sparql') }}
              >
                <ClockCircleOutlined style={{ marginRight: 6, color: '#999' }} />
                <Text style={{ fontSize: 11, fontFamily: 'monospace' }}>
                  {q.length > 80 ? q.slice(0, 77) + '…' : q}
                </Text>
              </div>
            ))}
        </div>
      )}

      {/* 빌더 모드 */}
      {mode === 'builder' && (
        <div style={{ marginBottom: 12 }}>
          <SparqlBuilder
            graph={graph ?? ''}
            classes={classes}
            objProps={objProps}
            dataProps={dataProps}
            onGenerate={handleBuilderGenerate}
          />
        </div>
      )}

      {/* SPARQL 에디터 */}
      {mode === 'sparql' && (
        <textarea
          ref={textareaRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={`SPARQL 쿼리를 입력하세요 (Ctrl+Enter 실행)\n\n예:\nSELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10`}
          style={{
            width: '100%', height: 180, fontFamily: 'monospace', fontSize: 13,
            padding: 10, border: '1px solid #d9d9d9', borderRadius: 4,
            resize: 'vertical', outline: 'none', boxSizing: 'border-box',
          }}
        />
      )}

      {/* 실행 버튼 (양 모드에서 표시) */}
      <Space style={{ marginTop: 8 }}>
        <Button
          type="primary" icon={<PlayCircleOutlined />} loading={running}
          onClick={handleRun}
          disabled={!dataset || !graph || !query.trim()}
        >
          실행 {mode === 'sparql' ? '(Ctrl+Enter)' : ''}
        </Button>
        <Button onClick={() => { setQuery(''); setResult(null) }}>지우기</Button>
        {mode === 'sparql' && (
          <Text type="secondary" style={{ fontSize: 11 }}>
            ℹ️ WHERE/ASK 패턴이 Named Graph로 자동 적용됩니다.
          </Text>
        )}
      </Space>

      {/* 결과 */}
      {result && (
        <>
          <Divider style={{ margin: '12px 0' }} />
          {result.type === 'error' && (
            <Alert type="error" showIcon message="SPARQL 오류" description={result.message} />
          )}
          {result.type === 'update' && (
            <Alert type="success" showIcon message={result.message} />
          )}
          {result.type === 'ask' && (
            <Alert
              type={result.boolean ? 'success' : 'warning'} showIcon
              message="ASK 결과"
              description={
                <Tag color={result.boolean ? 'green' : 'orange'} style={{ fontSize: 14 }}>
                  {result.boolean ? 'true' : 'false'}
                </Tag>
              }
            />
          )}
          {result.type === 'select' && (
            <>
              <Space style={{ marginBottom: 8 }}>
                <Text strong>결과</Text>
                <Badge count={result.rows?.length ?? 0} showZero color="#1677ff" />
                <Text type="secondary" style={{ fontSize: 11 }}>행</Text>
              </Space>
              {result.rows?.length === 0 ? (
                <Alert type="info" showIcon message="결과가 없습니다." />
              ) : (
                <Table
                  size="small"
                  pagination={{ pageSize: 20, showSizeChanger: false }}
                  scroll={{ x: 'max-content' }}
                  rowKey={(_, i) => String(i)}
                  dataSource={result.rows}
                  columns={(result.columns ?? []).map((col) => ({
                    title: col, dataIndex: col, key: col, ellipsis: true,
                    render: (v: string) => {
                      if (v == null || v === '') return null
                      if (isIri(v)) {
                        const label = labelMap[v] ?? localName(v)
                        return (
                          <Tooltip title={v} placement="topLeft">
                            <a
                              style={{ fontSize: 12, fontWeight: 500 }}
                              onClick={() => navigate(detectTab(v), v)}
                            >
                              {label}
                            </a>
                          </Tooltip>
                        )
                      }
                      return (
                        <Text style={{ fontFamily: 'monospace', fontSize: 12 }}>
                          {v.length > 60 ? '…' + v.slice(-59) : v}
                        </Text>
                      )
                    },
                  }))}
                />
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}

export default SparqlEditor
