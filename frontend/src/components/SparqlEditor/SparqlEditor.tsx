/**
 * v02-F SPARQL Editor
 * - OOI Named Graph 범위 내에서 SPARQL SELECT/ASK/UPDATE 실행
 * - 쿼리 히스토리 (localStorage 최근 10개)
 */

import React, { useEffect, useRef, useState } from 'react'
import {
  Alert, Badge, Button, Divider, Space, Table, Tag, Typography, message,
} from 'antd'
import { PlayCircleOutlined, HistoryOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { useOOI } from '../../context/OOIContext'
import { runSparqlQuery, runSparqlUpdate } from '../../api/sparqlEditor'

const { Text, Title } = Typography

const HISTORY_KEY = 'sparql_editor_history'
const MAX_HISTORY = 10

function loadHistory(): string[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? '[]')
  } catch {
    return []
  }
}

function saveHistory(queries: string[]) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(queries.slice(0, MAX_HISTORY)))
}

function addToHistory(query: string, history: string[]): string[] {
  const trimmed = query.trim()
  if (!trimmed) return history
  const filtered = history.filter((q) => q !== trimmed)
  return [trimmed, ...filtered].slice(0, MAX_HISTORY)
}

const SparqlEditor: React.FC = () => {
  const { dataset, graph } = useOOI()

  const [query, setQuery] = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<{
    type: 'select' | 'ask' | 'update' | 'error'
    columns?: string[]
    rows?: Record<string, string>[]
    boolean?: boolean
    message?: string
  } | null>(null)

  const [history, setHistory] = useState<string[]>(loadHistory)
  const [showHistory, setShowHistory] = useState(false)

  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    saveHistory(history)
  }, [history])

  const isUpdateQuery = (q: string) =>
    /^\s*(INSERT|DELETE|LOAD|CLEAR|CREATE|DROP|COPY|MOVE|ADD)\b/i.test(q.trim())

  const handleRun = async () => {
    if (!dataset || !graph) {
      message.warning('OOI를 먼저 설정하세요.')
      return
    }
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
    // Ctrl+Enter or Cmd+Enter to run
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      handleRun()
    }
  }

  const handleHistorySelect = (q: string) => {
    setQuery(q)
    setShowHistory(false)
    textareaRef.current?.focus()
  }

  return (
    <div style={{ padding: '8px 0' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 8 }}>
        <Title level={5} style={{ margin: 0 }}>SPARQL Editor</Title>
        <Space>
          {dataset && graph && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              OOI Graph: <Text code style={{ fontSize: 10 }}>
                {graph.length > 40 ? '…' + graph.slice(-39) : graph}
              </Text>
            </Text>
          )}
          <Button
            size="small"
            icon={<HistoryOutlined />}
            onClick={() => setShowHistory(!showHistory)}
          >
            히스토리
          </Button>
        </Space>
      </Space>

      {/* 히스토리 패널 */}
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
                onClick={() => handleHistorySelect(q)}
              >
                <ClockCircleOutlined style={{ marginRight: 6, color: '#999' }} />
                <Text style={{ fontSize: 11, fontFamily: 'monospace' }}>
                  {q.length > 80 ? q.slice(0, 77) + '…' : q}
                </Text>
              </div>
            ))}
        </div>
      )}

      {/* 쿼리 에디터 */}
      <textarea
        ref={textareaRef}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={`SPARQL 쿼리를 입력하세요 (Ctrl+Enter 실행)\n\n예:\nSELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10\n\n또는:\nINSERT DATA { <http://ex.org/A> a <http://ex.org/Class> . }`}
        style={{
          width: '100%',
          height: 180,
          fontFamily: 'monospace',
          fontSize: 13,
          padding: 10,
          border: '1px solid #d9d9d9',
          borderRadius: 4,
          resize: 'vertical',
          outline: 'none',
          boxSizing: 'border-box',
        }}
      />

      <Space style={{ marginTop: 8 }}>
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          loading={running}
          onClick={handleRun}
          disabled={!dataset || !graph || !query.trim()}
        >
          실행 (Ctrl+Enter)
        </Button>
        <Button onClick={() => { setQuery(''); setResult(null) }}>지우기</Button>
        <Text type="secondary" style={{ fontSize: 11 }}>
          ℹ️ WHERE/ASK 패턴이 자동으로 Named Graph로 감싸집니다.
        </Text>
      </Space>

      {/* 결과 영역 */}
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
              type={result.boolean ? 'success' : 'warning'}
              showIcon
              message={`ASK 결과: `}
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
                    title: col,
                    dataIndex: col,
                    key: col,
                    ellipsis: true,
                    render: (v: string) => (
                      <Text style={{ fontFamily: 'monospace', fontSize: 12 }} title={v}>
                        {v != null ? (v.length > 60 ? '…' + v.slice(-59) : v) : ''}
                      </Text>
                    ),
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
