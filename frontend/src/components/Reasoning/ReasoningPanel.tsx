/**
 * v02-G Reasoning Panel
 * - Reasoner 선택
 * - 추론 실행 (미리보기)
 * - 결과 Table
 * - Materialization (저장)
 * - 일관성 검사
 */

import React, { useMemo, useState } from 'react'
import {
  Alert, Badge, Button, Divider, Popconfirm, Select, Space, Switch, Table, Tag, Tooltip, Typography, message,
} from 'antd'
import {
  BulbOutlined, CheckCircleOutlined, CloseCircleOutlined, FilterOutlined, SaveOutlined,
} from '@ant-design/icons'
import { useOOI } from '../../context/OOIContext'
import {
  runReasoning, materializeReasoning, checkConsistency,
} from '../../api/reasoning'
import type { InferredTriple } from '../../api/reasoning'

const { Text, Title } = Typography

const REASONER_OPTIONS = [
  { value: 'RDFS', label: 'RDFS — RDFS 추론 (빠름)' },
  { value: 'OWL_RL', label: 'OWL_RL — OWL RL 추론 (권장)' },
  { value: 'RDFS_OWL_RL', label: 'RDFS+OWL_RL — 결합 추론 (느림)' },
]

// 로컬명 추출
const localName = (iri: string) => iri.split(/[#/]/).filter(Boolean).pop() ?? iri

// 알려진 prefix 단축
const KNOWN_PREFIX: [string, string][] = [
  ['http://www.w3.org/1999/02/22-rdf-syntax-ns#', 'rdf:'],
  ['http://www.w3.org/2000/01/rdf-schema#', 'rdfs:'],
  ['http://www.w3.org/2002/07/owl#', 'owl:'],
  ['http://www.w3.org/2001/XMLSchema#', 'xsd:'],
]
const formatIRI = (iri: string) => {
  for (const [ns, prefix] of KNOWN_PREFIX) {
    if (iri.startsWith(ns)) {
      const local = iri.slice(ns.length)
      if (prefix === 'rdf:' && local === 'type') return 'a'
      return prefix + local
    }
  }
  return localName(iri)
}

// ── 노이즈 판별 ──────────────────────────────────────────────────────────
const STD_PREFIXES = [
  'http://www.w3.org/2002/07/owl#',
  'http://www.w3.org/2000/01/rdf-schema#',
  'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
  'http://www.w3.org/2001/XMLSchema#',
]
// UUID / blank node: 16자 이상의 hex 문자열 포함 여부
const UUID_RE = /[0-9a-f]{16,}/i

function isNoise(t: { s: string; p: string; o: string }): boolean {
  // 1) tautological (S == O 이고 P == sameAs / equivalentClass)
  if (t.s === t.o) return true
  // 2) 표준 어휘가 Subject인 경우 (owl:Nothing, rdfs:Resource, xsd:int, …)
  if (STD_PREFIXES.some((p) => t.s.startsWith(p))) return true
  // 3) blank node / UUID-like subject (내부 식별자)
  if (t.s.startsWith('_:') || UUID_RE.test(t.s)) return true
  return false
}

const ReasoningPanel: React.FC = () => {
  const { dataset, graph } = useOOI()

  const [reasoner, setReasoner] = useState('RDFS')
  const [running, setRunning] = useState(false)
  const [inferred, setInferred] = useState<InferredTriple[] | null>(null)
  const [totalInferred, setTotalInferred] = useState(0)
  const [truncated, setTruncated] = useState(false)

  const [materializing, setMaterializing] = useState(false)
  const [materializedGraph, setMaterializedGraph] = useState<string | null>(null)

  const [filterNoise, setFilterNoise] = useState(true)   // 노이즈 필터 (기본 ON)

  const [checking, setChecking] = useState(false)
  const [consistencyResult, setConsistencyResult] = useState<{
    consistent: boolean
    details: string | string[]
  } | null>(null)

  // 필터 적용된 목록
  const displayedTriples = useMemo(() => {
    if (!inferred) return []
    return filterNoise ? inferred.filter((t) => !isNoise(t)) : inferred
  }, [inferred, filterNoise])

  const handleRun = async () => {
    if (!dataset || !graph) return
    setRunning(true)
    setInferred(null)
    setMaterializedGraph(null)
    try {
      const res = await runReasoning(dataset, graph, reasoner)
      setInferred(res.inferred_triples)
      setTotalInferred(res.total_inferred)
      setTruncated(res.truncated)
      if (res.truncated) {
        message.warning(`추론 결과가 많습니다. 최대 1000개만 표시됩니다. (총 ${res.total_inferred}개)`)
      } else {
        message.success(`추론 완료 — ${res.total_inferred}개 새 트리플 발견`)
      }
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setRunning(false)
    }
  }

  const handleMaterialize = async () => {
    if (!dataset || !graph || !inferred) return
    setMaterializing(true)
    try {
      const res = await materializeReasoning(dataset, graph, inferred)
      setMaterializedGraph(res.inferred_graph)
      message.success(`${res.materialized_count}개 트리플이 저장되었습니다.`)
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setMaterializing(false)
    }
  }

  const handleConsistencyCheck = async () => {
    if (!dataset || !graph) return
    setChecking(true)
    setConsistencyResult(null)
    try {
      const res = await checkConsistency(dataset, graph)
      setConsistencyResult(res)
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setChecking(false)
    }
  }

  const columns = [
    {
      title: 'Subject', dataIndex: 's', key: 's', ellipsis: true,
      render: (v: string) => (
        <Tooltip title={v}>
          <Text style={{ fontSize: 12 }}>{formatIRI(v)}</Text>
        </Tooltip>
      ),
    },
    {
      title: 'Predicate', dataIndex: 'p', key: 'p', ellipsis: true,
      render: (v: string) => (
        <Tooltip title={v}>
          <Text style={{ fontSize: 12 }}>{formatIRI(v)}</Text>
        </Tooltip>
      ),
    },
    {
      title: 'Object', dataIndex: 'o', key: 'o', ellipsis: true,
      render: (v: string) => (
        <Tooltip title={v}>
          <Text style={{ fontSize: 12 }}>{formatIRI(v)}</Text>
        </Tooltip>
      ),
    },
  ]

  return (
    <div style={{ padding: '8px 0' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}>
        <Title level={5} style={{ margin: 0 }}>🧠 Reasoning</Title>
        <Text type="secondary" style={{ fontSize: 11 }}>
          owlrl 기반 OWL/RDFS 추론 엔진
        </Text>
      </Space>

      {/* 추론 실행 섹션 */}
      <Space wrap style={{ marginBottom: 12 }}>
        <Select
          value={reasoner}
          onChange={setReasoner}
          style={{ width: 260 }}
          options={REASONER_OPTIONS}
        />
        <Button
          type="primary"
          icon={<BulbOutlined />}
          loading={running}
          onClick={handleRun}
          disabled={!dataset || !graph}
        >
          추론 실행
        </Button>
        <Button
          icon={<CheckCircleOutlined />}
          loading={checking}
          onClick={handleConsistencyCheck}
          disabled={!dataset || !graph}
        >
          일관성 검사
        </Button>
      </Space>

      {/* 일관성 검사 결과 */}
      {consistencyResult && (
        <Alert
          type={consistencyResult.consistent ? 'success' : 'error'}
          showIcon
          icon={
            consistencyResult.consistent
              ? <CheckCircleOutlined />
              : <CloseCircleOutlined />
          }
          message={consistencyResult.consistent ? '일관성 검사 통과' : '일관성 오류 발견'}
          description={
            Array.isArray(consistencyResult.details)
              ? consistencyResult.details.map((d, i) => <div key={i}>{d}</div>)
              : consistencyResult.details
          }
          style={{ marginBottom: 12 }}
        />
      )}

      {/* 추론 결과 */}
      {inferred !== null && (
        <>
          <Divider style={{ margin: '8px 0' }} />
          <Space style={{ marginBottom: 8, width: '100%', justifyContent: 'space-between' }}>
            <Space wrap>
              <Text strong>추론된 새 트리플</Text>
              <Badge count={totalInferred} showZero color="#1677ff" />
              {truncated && <Tag color="orange">최대 1000개 표시 중</Tag>}
              {filterNoise && inferred.length !== displayedTriples.length && (
                <Tag color="geekblue">
                  {inferred.length - displayedTriples.length}개 노이즈 숨김
                </Tag>
              )}
              <Tooltip title="표준 어휘(owl/rdf/xsd) subject, tautological sameAs, blank node 숨기기">
                <Space size={4}>
                  <FilterOutlined style={{ fontSize: 12, color: '#888' }} />
                  <Text style={{ fontSize: 12 }}>노이즈 필터</Text>
                  <Switch
                    size="small"
                    checked={filterNoise}
                    onChange={setFilterNoise}
                  />
                </Space>
              </Tooltip>
            </Space>
            {inferred.length > 0 && !materializedGraph && (
              <Popconfirm
                title={`${inferred.length}개 트리플을 {graph}/inferred 로 저장합니다.`}
                onConfirm={handleMaterialize}
                okText="저장" okButtonProps={{ type: 'primary' }}
              >
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  loading={materializing}
                >
                  Materialization (저장)
                </Button>
              </Popconfirm>
            )}
          </Space>

          {materializedGraph && (
            <Alert
              type="success"
              showIcon
              message="저장 완료"
              description={
                <Text style={{ fontSize: 11 }}>
                  추론 결과가 <Text code style={{ fontSize: 11 }}>{materializedGraph}</Text>에 저장되었습니다.
                </Text>
              }
              style={{ marginBottom: 8 }}
            />
          )}

          {displayedTriples.length === 0 ? (
            <Alert
              type="info" showIcon
              message={
                inferred.length === 0
                  ? '새로 추론된 트리플이 없습니다.'
                  : `필터 적용 후 표시할 트리플이 없습니다. (전체 ${inferred.length}개)`
              }
            />
          ) : (
            <Table
              size="small"
              dataSource={displayedTriples}
              columns={columns}
              rowKey={(_, i) => String(i)}
              pagination={{ pageSize: 20, showSizeChanger: false }}
              scroll={{ x: 'max-content' }}
            />
          )}
        </>
      )}
    </div>
  )
}

export default ReasoningPanel
