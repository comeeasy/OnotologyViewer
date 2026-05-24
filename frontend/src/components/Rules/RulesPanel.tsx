/**
 * v03-B Rules Panel
 * - SPARQL 기반 추론 규칙 관리
 * - 규칙 생성 / 수정 / 삭제
 * - 규칙 적용 미리보기
 * - Materialization (저장)
 */

import React, { useEffect, useState } from 'react'
import {
  Alert, Button, Card, Form, Input,
  Popconfirm, Space, Table, Tag, Typography, message,
} from 'antd'
import {
  DeleteOutlined, EditOutlined, PlayCircleOutlined, PlusOutlined, SaveOutlined,
} from '@ant-design/icons'
import { useOOI } from '../../context/OOIContext'
import {
  listRules, createRule, getRule, updateRule, deleteRule, applyRule, materializeRule,
} from '../../api/rules'
import type { RuleSummary, RuleDetail, InferredTriple } from '../../api/rules'

const { Text, Title } = Typography
const { TextArea } = Input

const shortIRI = (iri: string, max = 50) =>
  iri.length > max ? '…' + iri.slice(-(max - 1)) : iri

// ── Rule 생성 / 수정 폼 ──────────────────────────────────────────────────

interface RuleFormProps {
  dataset: string
  graph: string
  initial?: RuleDetail
  onSaved: () => void
  onCancel?: () => void
}

const RuleForm: React.FC<RuleFormProps> = ({ dataset, graph, initial, onSaved, onCancel }) => {
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const isEdit = !!initial

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

  const handleSave = async () => {
    const vals = await form.validateFields()
    setSaving(true)
    try {
      if (isEdit) {
        await updateRule(dataset, graph, initial!.rule_iri, {
          label: vals.label,
          description: vals.description,
          condition: vals.condition,
          consequence: vals.consequence,
        })
        message.success('규칙 수정됨')
      } else {
        await createRule({
          dataset,
          graph,
          label: vals.label,
          condition: vals.condition,
          consequence: vals.consequence,
          description: vals.description,
        })
        message.success('규칙 생성됨')
        form.resetFields()
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
      extra={onCancel && <Button size="small" onClick={onCancel}>취소</Button>}
    >
      <Form form={form} layout="vertical">
        <Form.Item name="label" label="Label" rules={[{ required: true }]}>
          <Input placeholder="규칙 이름" />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <Input placeholder="설명 (선택)" />
        </Form.Item>
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
  onDeleted: () => void
  onEdited: () => void
}

const RuleCard: React.FC<RuleCardProps> = ({ rule, dataset, graph, onDeleted, onEdited }) => {
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
    if (!detail) {
      const d = await getRule(dataset, graph, rule.rule_iri)
      setDetail(d)
    }
    setEditing(true)
  }

  const tripleColumns = [
    {
      title: 'S',
      dataIndex: 's',
      key: 's',
      ellipsis: true,
      render: (v: string) => (
        <Text style={{ fontFamily: 'monospace', fontSize: 11 }} title={v}>{shortIRI(v)}</Text>
      ),
    },
    {
      title: 'P',
      dataIndex: 'p',
      key: 'p',
      ellipsis: true,
      render: (v: string) => (
        <Text style={{ fontFamily: 'monospace', fontSize: 11 }} title={v}>{shortIRI(v)}</Text>
      ),
    },
    {
      title: 'O',
      dataIndex: 'o',
      key: 'o',
      ellipsis: true,
      render: (v: string) => (
        <Text style={{ fontFamily: 'monospace', fontSize: 11 }} title={v}>{shortIRI(v)}</Text>
      ),
    },
  ]

  if (editing && detail) {
    return (
      <RuleForm
        dataset={dataset}
        graph={graph}
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
          size="small"
          icon={<PlayCircleOutlined />}
          loading={applying}
          onClick={handleApply}
        >
          적용 미리보기
        </Button>
        {inferred !== null && inferred.length > 0 && !matGraph && (
          <Popconfirm
            title={`${inferred.length}개 트리플을 graph/materialized에 저장합니다.`}
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
          type="success"
          showIcon
          message="저장 완료"
          description={<Text code style={{ fontSize: 11 }}>{matGraph}</Text>}
          style={{ marginTop: 8 }}
        />
      )}

      {inferred !== null && (
        inferred.length === 0 ? (
          <Alert type="info" showIcon message="추론된 트리플 없음" style={{ marginTop: 8 }} />
        ) : (
          <Table
            size="small"
            dataSource={inferred}
            columns={tripleColumns}
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
  const { dataset, graph } = useOOI()

  const [rules, setRules] = useState<RuleSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)

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

  useEffect(() => { reload() }, [dataset, graph])

  return (
    <div style={{ padding: '8px 0' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}>
        <Title level={5} style={{ margin: 0 }}>⚡ Inference Rules</Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setShowCreate(true)}
          disabled={!dataset || !graph}
        >
          규칙 추가
        </Button>
      </Space>

      {showCreate && (
        <RuleForm
          dataset={dataset!}
          graph={graph!}
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
            dataset={dataset!}
            graph={graph!}
            onDeleted={reload}
            onEdited={reload}
          />
        ))
      )}
    </div>
  )
}

export default RulesPanel
