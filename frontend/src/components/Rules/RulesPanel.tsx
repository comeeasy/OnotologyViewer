/**
 * v03-C Rules Panel
 * - SPARQL 기반 추론 규칙 관리
 * - 규칙 생성 / 수정 / 삭제
 * - 규칙 적용 미리보기 + Materialization
 * - UI 빌더 모드 (triple-pattern 기반) ↔ SPARQL 직접 입력 전환
 */

import React, { useEffect, useState } from 'react'
import {
  Alert, Button, Card, Form, Input,
  Popconfirm, Select, Segmented, Space, Table, Tag, Typography, message,
} from 'antd'
import {
  DeleteOutlined, EditOutlined, MinusCircleOutlined, PlayCircleOutlined,
  PlusOutlined, SaveOutlined, CodeOutlined, BuildOutlined,
} from '@ant-design/icons'
import { useOOI } from '../../context/OOIContext'
import {
  listRules, createRule, getRule, updateRule, deleteRule, applyRule, materializeRule,
} from '../../api/rules'
import type { RuleSummary, RuleDetail, InferredTriple } from '../../api/rules'
import { listClasses } from '../../api/classes'
import { listObjProps } from '../../api/objProps'
import { listDataProps } from '../../api/dataProps'
import type { ClassSummary, ObjPropSummary, DataPropSummary } from '../../types/ontology'

const { Text, Title } = Typography
const { TextArea } = Input

// 로컬명 추출 (# 또는 / 뒤)
const localName = (iri: string) => iri.split(/[#/]/).filter(Boolean).pop() ?? iri

// 알려진 표준 prefix 매핑
const KNOWN_PREFIX: [string, string][] = [
  ['http://www.w3.org/1999/02/22-rdf-syntax-ns#', 'rdf:'],
  ['http://www.w3.org/2000/01/rdf-schema#', 'rdfs:'],
  ['http://www.w3.org/2002/07/owl#', 'owl:'],
  ['http://www.w3.org/2001/XMLSchema#', 'xsd:'],
]

// IRI → 표시 문자열: 레이블 맵 → 알려진 prefix → 로컬명
function formatIRI(iri: string, labelMap?: Map<string, string>): string {
  if (!iri) return iri
  if (labelMap?.has(iri)) return labelMap.get(iri)!
  for (const [ns, prefix] of KNOWN_PREFIX) {
    if (iri.startsWith(ns)) {
      const local = iri.slice(ns.length)
      if (prefix === 'rdf:' && local === 'type') return 'a'
      return prefix + local
    }
  }
  return localName(iri)
}

// 하위 호환용 (빌더 select 표시 등)
const shortIRI = (iri: string, _max = 50) => localName(iri)

// ── 트리플 패턴 빌더 ──────────────────────────────────────────────────────

interface TriplePattern {
  id: string
  subject: string        // 변수, e.g. "?book"
  predicateType: 'type' | 'objprop' | 'dataprop'
  predicateIri: string   // prop IRI (type 이면 '')
  object: string         // class IRI(type) or 변수(prop)
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
      return r.predicateIri
        ? `${r.subject} <${r.predicateIri}> ${obj} .`
        : `${r.subject} ?p ${obj} .`
    })
    .join('\n')
}

interface TriplePatternBuilderProps {
  rows: TriplePattern[]
  onChange: (rows: TriplePattern[]) => void
  classes: ClassSummary[]
  objProps: ObjPropSummary[]
  dataProps: DataPropSummary[]
}

const TriplePatternBuilder: React.FC<TriplePatternBuilderProps> = ({
  rows, onChange, classes, objProps, dataProps,
}) => {
  const update = (id: string, patch: Partial<TriplePattern>) => {
    onChange(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)))
  }
  const remove = (id: string) => onChange(rows.filter((r) => r.id !== id))
  const add = () => onChange([...rows, makeRow()])

  const classOptions = classes.map((c) => ({
    label: c.label ?? shortIRI(c.iri, 40),
    value: c.iri,
    title: c.iri,
  }))

  // predicate Select 옵션: type + objprop group + dataprop group
  const predicateOptions = [
    {
      label: '타입',
      options: [{ label: 'a (rdf:type)', value: '__type__' }],
    },
    {
      label: 'Object Property',
      options: objProps.map((p) => ({
        label: p.label ?? shortIRI(p.iri, 40),
        value: `objprop::${p.iri}`,
        title: p.iri,
      })),
    },
    {
      label: 'Data Property',
      options: dataProps.map((p) => ({
        label: p.label ?? shortIRI(p.iri, 40),
        value: `dataprop::${p.iri}`,
        title: p.iri,
      })),
    },
  ]

  const predicateValue = (row: TriplePattern) => {
    if (row.predicateType === 'type') return '__type__'
    const prefix = row.predicateType === 'objprop' ? 'objprop' : 'dataprop'
    return row.predicateIri ? `${prefix}::${row.predicateIri}` : undefined
  }

  const handlePredicateChange = (id: string, val: string) => {
    if (val === '__type__') {
      update(id, { predicateType: 'type', predicateIri: '', object: '' })
    } else if (val.startsWith('objprop::')) {
      update(id, { predicateType: 'objprop', predicateIri: val.replace('objprop::', ''), object: '' })
    } else if (val.startsWith('dataprop::')) {
      update(id, { predicateType: 'dataprop', predicateIri: val.replace('dataprop::', ''), object: '' })
    }
  }

  return (
    <div>
      {rows.map((row) => (
        <div
          key={row.id}
          style={{ display: 'flex', gap: 6, marginBottom: 6, alignItems: 'center', flexWrap: 'wrap' }}
        >
          {/* Subject */}
          <Input
            size="small"
            placeholder="?subject"
            value={row.subject}
            onChange={(e) => update(row.id, { subject: e.target.value })}
            style={{ width: 90, fontFamily: 'monospace' }}
          />

          {/* Predicate */}
          <Select
            size="small"
            placeholder="술어 선택"
            value={predicateValue(row)}
            onChange={(v) => handlePredicateChange(row.id, v)}
            options={predicateOptions}
            style={{ width: 200 }}
            showSearch
            optionFilterProp="label"
            allowClear
          />

          {/* Object */}
          {row.predicateType === 'type' ? (
            <Select
              size="small"
              placeholder="Class 선택"
              value={row.object || undefined}
              onChange={(v) => update(row.id, { object: v })}
              options={classOptions}
              style={{ width: 200 }}
              showSearch
              optionFilterProp="label"
              allowClear
            />
          ) : (
            <Input
              size="small"
              placeholder="?variable"
              value={row.object}
              onChange={(e) => update(row.id, { object: e.target.value })}
              style={{ width: 110, fontFamily: 'monospace' }}
            />
          )}

          <Button
            type="text" danger size="small"
            icon={<MinusCircleOutlined />}
            onClick={() => remove(row.id)}
          />
        </div>
      ))}
      <Button size="small" icon={<PlusOutlined />} onClick={add} style={{ marginTop: 2 }}>
        패턴 추가
      </Button>
    </div>
  )
}

// ── Rule 생성 / 수정 폼 ──────────────────────────────────────────────────

interface RuleFormProps {
  dataset: string
  graph: string
  classes: ClassSummary[]
  objProps: ObjPropSummary[]
  dataProps: DataPropSummary[]
  initial?: RuleDetail
  onSaved: () => void
  onCancel?: () => void
}

type EditorMode = 'builder' | 'sparql'

const RuleForm: React.FC<RuleFormProps> = ({
  dataset, graph,
  classes, objProps, dataProps,
  initial, onSaved, onCancel,
}) => {
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [mode, setMode] = useState<EditorMode>('builder')
  const isEdit = !!initial

  // 빌더 상태
  const [condRows, setCondRows] = useState<TriplePattern[]>([makeRow()])
  const [consRows, setConsRows] = useState<TriplePattern[]>([makeRow()])

  useEffect(() => {
    if (initial) {
      form.setFieldsValue({
        label: initial.label,
        description: initial.description,
        condition: initial.condition,
        consequence: initial.consequence,
      })
    }
  }, [initial])

  // 빌더 → SPARQL 전환 시 텍스트 동기화
  const switchToSparql = () => {
    const cond = rowsToSparql(condRows)
    const cons = rowsToSparql(consRows)
    if (cond) form.setFieldValue('condition', cond)
    if (cons) form.setFieldValue('consequence', cons)
    setMode('sparql')
  }

  const handleSave = async () => {
    const vals = await form.validateFields()
    let condition = vals.condition
    let consequence = vals.consequence

    // 빌더 모드면 rows에서 생성
    if (mode === 'builder') {
      condition = rowsToSparql(condRows)
      consequence = rowsToSparql(consRows)
      if (!condition || !consequence) {
        message.warning('Condition과 Consequence를 모두 입력해주세요.')
        return
      }
    }

    setSaving(true)
    try {
      if (isEdit) {
        await updateRule(dataset, graph, initial!.rule_iri, {
          label: vals.label,
          description: vals.description,
          condition,
          consequence,
        })
        message.success('규칙 수정됨')
      } else {
        await createRule({ dataset, graph, label: vals.label, condition, consequence, description: vals.description })
        message.success('규칙 생성됨')
        form.resetFields()
        setCondRows([makeRow()])
        setConsRows([makeRow()])
      }
      onSaved()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card
      size="small"
      title={isEdit ? '규칙 수정' : '새 규칙 추가'}
      style={{ marginBottom: 12 }}
      extra={
        <Space>
          <Segmented
            size="small"
            value={mode}
            options={[
              { value: 'builder', icon: <BuildOutlined />, label: '빌더' },
              { value: 'sparql', icon: <CodeOutlined />, label: 'SPARQL' },
            ]}
            onChange={(v) => {
              if (v === 'sparql') switchToSparql()
              else setMode('builder')
            }}
          />
          {onCancel && <Button size="small" onClick={onCancel}>취소</Button>}
        </Space>
      }
    >
      <Form form={form} layout="vertical">
        <Form.Item name="label" label="Label" rules={[{ required: true }]}>
          <Input placeholder="규칙 이름" />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <Input placeholder="설명 (선택)" />
        </Form.Item>

        {mode === 'builder' ? (
          <>
            <Form.Item label="Condition (WHERE 패턴)">
              <TriplePatternBuilder
                rows={condRows}
                onChange={setCondRows}
                classes={classes}
                objProps={objProps}
                dataProps={dataProps}
              />
              {/* 미리보기 */}
              {rowsToSparql(condRows) && (
                <Text
                  type="secondary"
                  style={{ fontFamily: 'monospace', fontSize: 11, display: 'block', marginTop: 6, whiteSpace: 'pre' }}
                >
                  {rowsToSparql(condRows)}
                </Text>
              )}
            </Form.Item>

            <Form.Item label="Consequence (CONSTRUCT 패턴)">
              <TriplePatternBuilder
                rows={consRows}
                onChange={setConsRows}
                classes={classes}
                objProps={objProps}
                dataProps={dataProps}
              />
              {rowsToSparql(consRows) && (
                <Text
                  type="secondary"
                  style={{ fontFamily: 'monospace', fontSize: 11, display: 'block', marginTop: 6, whiteSpace: 'pre' }}
                >
                  {rowsToSparql(consRows)}
                </Text>
              )}
            </Form.Item>
          </>
        ) : (
          <>
            <Form.Item
              name="condition"
              label="Condition (SPARQL WHERE 패턴)"
              rules={[{ required: true }]}
              extra="예: ?x a <http://example.org/ns#Dog> ."
            >
              <TextArea rows={3} style={{ fontFamily: 'monospace', fontSize: 12 }} />
            </Form.Item>
            <Form.Item
              name="consequence"
              label="Consequence (CONSTRUCT 패턴)"
              rules={[{ required: true }]}
              extra="예: ?x a <http://example.org/ns#Animal> ."
            >
              <TextArea rows={3} style={{ fontFamily: 'monospace', fontSize: 12 }} />
            </Form.Item>
          </>
        )}

        <Form.Item>
          <Button type="primary" loading={saving} onClick={handleSave} icon={<SaveOutlined />}>
            {isEdit ? '저장' : '추가'}
          </Button>
        </Form.Item>
      </Form>
    </Card>
  )
}

// ── Rule 카드 ─────────────────────────────────────────────────────────────

interface RuleCardProps {
  rule: RuleSummary
  dataset: string
  graph: string
  classes: ClassSummary[]
  objProps: ObjPropSummary[]
  dataProps: DataPropSummary[]
  onDeleted: () => void
  onEdited: () => void
  onBeforeEdit?: () => void
}

const RuleCard: React.FC<RuleCardProps> = ({
  rule, dataset, graph,
  classes, objProps, dataProps,
  onDeleted, onEdited, onBeforeEdit,
}) => {
  const [inferred, setInferred] = useState<InferredTriple[] | null>(null)
  const [applying, setApplying] = useState(false)
  const [materializing, setMaterializing] = useState(false)
  const [matGraph, setMatGraph] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [detail, setDetail] = useState<RuleDetail | null>(null)

  const handleApply = async () => {
    setApplying(true)
    setInferred(null)
    setMatGraph(null)
    try {
      const res = await applyRule(dataset, graph, rule.rule_iri)
      setInferred(res.inferred_triples)
      if (res.inferred_triples.length === 0) {
        message.info('매칭되는 트리플 없음')
      } else {
        message.success(`${res.inferred_triples.length}개 트리플 추론됨`)
      }
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setApplying(false)
    }
  }

  const handleMaterialize = async () => {
    setMaterializing(true)
    try {
      const res = await materializeRule(dataset, graph, rule.rule_iri)
      setMatGraph(res.materialized_graph)
      message.success(`${res.materialized_count}개 트리플 저장됨`)
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setMaterializing(false)
    }
  }

  const handleDelete = async () => {
    try {
      await deleteRule(dataset, graph, rule.rule_iri)
      message.success('규칙 삭제됨')
      onDeleted()
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  const handleEditClick = async () => {
    onBeforeEdit?.()
    if (!detail) {
      const d = await getRule(dataset, graph, rule.rule_iri)
      setDetail(d)
    }
    setEditing(true)
  }

  // IRI → label 맵: class + objprop + dataprop
  const labelMap = React.useMemo(() => {
    const m = new Map<string, string>()
    classes.forEach((c) => { if (c.label) m.set(c.iri, c.label) })
    objProps.forEach((p) => { if (p.label) m.set(p.iri, p.label) })
    dataProps.forEach((p) => { if (p.label) m.set(p.iri, p.label) })
    return m
  }, [classes, objProps, dataProps])

  const tripleColumns = [
    {
      title: 'Subject', dataIndex: 's', key: 's', ellipsis: true,
      render: (v: string) => (
        <Text style={{ fontSize: 12 }} title={v}>{formatIRI(v, labelMap)}</Text>
      ),
    },
    {
      title: 'Predicate', dataIndex: 'p', key: 'p', ellipsis: true,
      render: (v: string) => (
        <Text style={{ fontSize: 12 }} title={v}>{formatIRI(v, labelMap)}</Text>
      ),
    },
    {
      title: 'Object', dataIndex: 'o', key: 'o', ellipsis: true,
      render: (v: string) => (
        <Text style={{ fontSize: 12 }} title={v}>{formatIRI(v, labelMap)}</Text>
      ),
    },
  ]

  if (editing && detail) {
    return (
      <RuleForm
        dataset={dataset} graph={graph}
        classes={classes} objProps={objProps} dataProps={dataProps}
        initial={detail}
        onSaved={() => { setEditing(false); onEdited() }}
        onCancel={() => setEditing(false)}
      />
    )
  }

  return (
    <Card
      size="small"
      title={
        <Space>
          <Tag color="purple">Rule</Tag>
          <Text strong>{rule.label ?? rule.rule_iri}</Text>
        </Space>
      }
      extra={
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={handleEditClick}>수정</Button>
          <Popconfirm title="규칙을 삭제합니다." onConfirm={handleDelete}>
            <Button size="small" danger icon={<DeleteOutlined />}>삭제</Button>
          </Popconfirm>
        </Space>
      }
      style={{ marginBottom: 8 }}
    >
      {rule.description && (
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          {rule.description}
        </Text>
      )}

      <Space wrap>
        <Button
          size="small" icon={<PlayCircleOutlined />} loading={applying} onClick={handleApply}
        >
          적용 미리보기
        </Button>
        {inferred !== null && inferred.length > 0 && !matGraph && (
          <Popconfirm
            title={`${inferred.length}개 트리플을 저장합니다.`}
            onConfirm={handleMaterialize}
          >
            <Button size="small" type="primary" icon={<SaveOutlined />} loading={materializing}>
              Materialize
            </Button>
          </Popconfirm>
        )}
      </Space>

      {matGraph && (
        <Alert
          type="success" showIcon message="저장 완료"
          description={<Text code style={{ fontSize: 11 }}>{matGraph}</Text>}
          style={{ marginTop: 8 }}
        />
      )}

      {inferred !== null && (
        inferred.length === 0 ? (
          <Alert type="info" showIcon message="추론된 트리플 없음" style={{ marginTop: 8 }} />
        ) : (
          <Table
            size="small" dataSource={inferred} columns={tripleColumns}
            rowKey={(_, i) => String(i)}
            pagination={{ pageSize: 10, showSizeChanger: false }}
            style={{ marginTop: 8 }}
          />
        )
      )}
    </Card>
  )
}

// ── Main Panel ─────────────────────────────────────────────────────────────

const RulesPanel: React.FC = () => {
  const { dataset, graph, graphs, namespace } = useOOI()

  const [rules, setRules] = useState<RuleSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)

  // 온톨로지 데이터 (빌더용)
  const [classes, setClasses] = useState<ClassSummary[]>([])
  const [objProps, setObjProps] = useState<ObjPropSummary[]>([])
  const [dataProps, setDataProps] = useState<DataPropSummary[]>([])

  const reload = async () => {
    if (!dataset || !graph) return
    setLoading(true)
    try {
      const data = await listRules(dataset, graph)
      setRules(data)
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  // 빌더용 온톨로지 데이터 로드
  const loadOntology = async () => {
    if (!dataset || graphs.length === 0 || !namespace) return
    try {
      const [c, op, dp] = await Promise.all([
        listClasses(dataset, graphs, namespace),
        listObjProps(dataset, graphs, namespace),
        listDataProps(dataset, graphs, namespace),
      ])
      setClasses(c)
      setObjProps(op)
      setDataProps(dp)
    } catch { /* 무시 */ }
  }

  useEffect(() => { reload() }, [dataset, graph])
  useEffect(() => { loadOntology() }, [dataset, graphs, namespace])

  return (
    <div style={{ padding: '8px 0' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}>
        <Title level={5} style={{ margin: 0 }}>⚡ Inference Rules</Title>
        <Button
          type="primary" icon={<PlusOutlined />}
          onClick={() => { loadOntology(); setShowCreate(true) }}
          disabled={!dataset || !graph}
        >
          규칙 추가
        </Button>
      </Space>

      {showCreate && (
        <RuleForm
          dataset={dataset!} graph={graph!}
          classes={classes} objProps={objProps} dataProps={dataProps}
          onSaved={() => { setShowCreate(false); reload() }}
          onCancel={() => setShowCreate(false)}
        />
      )}

      {loading ? (
        <Text type="secondary">로딩 중...</Text>
      ) : rules.length === 0 ? (
        <Alert type="info" showIcon message="등록된 추론 규칙이 없습니다." />
      ) : (
        rules.map((rule) => (
          <RuleCard
            key={rule.rule_iri}
            rule={rule}
            dataset={dataset!} graph={graph!}
            classes={classes} objProps={objProps} dataProps={dataProps}
            onDeleted={reload}
            onEdited={reload}
            onBeforeEdit={loadOntology}
          />
        ))
      )}
    </div>
  )
}

export default RulesPanel
