/**
 * v03-A SHACL Panel
 * - NodeShape 목록 + 생성
 * - PropertyShape 추가/삭제
 * - 그래프 전체 검증
 * - Individual 단위 검증
 */

import React, { useEffect, useState } from 'react'
import {
  Alert, Button, Collapse, Divider, Form, Input, InputNumber,
  List, Popconfirm, Select, Space, Spin, Table, Tag, Typography, message,
} from 'antd'
import {
  CheckCircleOutlined, CloseCircleOutlined, DeleteOutlined, PlusOutlined, SafetyOutlined,
} from '@ant-design/icons'
import { useOOI } from '../../context/OOIContext'
import {
  listShapes, createShape, getShapeDetail, addPropertyShape,
  deletePropertyShape, deleteShape, validateGraph, validateIndividual,
} from '../../api/shacl'
import type { NodeShapeSummary, NodeShapeDetail, ViolationItem } from '../../api/shacl'

const { Text, Title } = Typography
const { Panel } = Collapse

const shortIRI = (iri: string, max = 55) =>
  iri.length > max ? '…' + iri.slice(-(max - 1)) : iri

// ── PropertyShape 추가 폼 ──────────────────────────────────────────────────

interface AddPropFormProps {
  dataset: string
  graph: string
  shapeIri: string
  onAdded: () => void
}

const XSD_TYPES = [
  { value: 'http://www.w3.org/2001/XMLSchema#string', label: 'xsd:string' },
  { value: 'http://www.w3.org/2001/XMLSchema#integer', label: 'xsd:integer' },
  { value: 'http://www.w3.org/2001/XMLSchema#float', label: 'xsd:float' },
  { value: 'http://www.w3.org/2001/XMLSchema#boolean', label: 'xsd:boolean' },
  { value: 'http://www.w3.org/2001/XMLSchema#dateTime', label: 'xsd:dateTime' },
  { value: 'http://www.w3.org/2001/XMLSchema#anyURI', label: 'xsd:anyURI' },
]

const AddPropForm: React.FC<AddPropFormProps> = ({ dataset, graph, shapeIri, onAdded }) => {
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  const handleAdd = async () => {
    const vals = await form.validateFields()
    setSaving(true)
    try {
      await addPropertyShape(dataset, graph, shapeIri, {
        path: vals.path,
        min_count: vals.min_count ?? null,
        max_count: vals.max_count ?? null,
        datatype: vals.datatype ?? null,
        label: vals.label ?? null,
      })
      message.success('PropertyShape 추가됨')
      form.resetFields()
      onAdded()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Form form={form} layout="inline" style={{ marginTop: 8 }}>
      <Form.Item name="path" rules={[{ required: true, message: 'Property IRI 필수' }]}>
        <Input placeholder="sh:path (IRI)" style={{ width: 220 }} />
      </Form.Item>
      <Form.Item name="min_count">
        <InputNumber placeholder="minCount" min={0} style={{ width: 90 }} />
      </Form.Item>
      <Form.Item name="max_count">
        <InputNumber placeholder="maxCount" min={0} style={{ width: 90 }} />
      </Form.Item>
      <Form.Item name="datatype">
        <Select
          placeholder="datatype"
          style={{ width: 130 }}
          allowClear
          options={XSD_TYPES}
        />
      </Form.Item>
      <Form.Item name="label">
        <Input placeholder="label" style={{ width: 110 }} />
      </Form.Item>
      <Form.Item>
        <Button type="primary" size="small" loading={saving} onClick={handleAdd} icon={<PlusOutlined />}>
          추가
        </Button>
      </Form.Item>
    </Form>
  )
}

// ── NodeShape 상세 패널 ────────────────────────────────────────────────────

interface ShapeDetailPanelProps {
  dataset: string
  graph: string
  shapeIri: string
  onDeleted: () => void
}

const ShapeDetailPanel: React.FC<ShapeDetailPanelProps> = ({
  dataset, graph, shapeIri, onDeleted,
}) => {
  const [detail, setDetail] = useState<NodeShapeDetail | null>(null)
  const [loading, setLoading] = useState(false)

  const reload = async () => {
    setLoading(true)
    try {
      const d = await getShapeDetail(dataset, graph, shapeIri)
      setDetail(d)
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { reload() }, [shapeIri])

  const handleDeleteProp = async (propIri: string) => {
    try {
      await deletePropertyShape(dataset, graph, shapeIri, propIri)
      message.success('PropertyShape 삭제됨')
      reload()
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  const handleDeleteShape = async () => {
    try {
      await deleteShape(dataset, graph, shapeIri)
      message.success('NodeShape 삭제됨')
      onDeleted()
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  if (loading) return <Spin size="small" />
  if (!detail) return null

  return (
    <div style={{ paddingLeft: 8 }}>
      <Space style={{ marginBottom: 8 }}>
        <Tag color="blue">targetClass</Tag>
        <Text code style={{ fontSize: 11 }}>{shortIRI(detail.target_class)}</Text>
        <Popconfirm title="NodeShape와 모든 PropertyShape를 삭제합니다." onConfirm={handleDeleteShape}>
          <Button size="small" danger icon={<DeleteOutlined />}>Shape 삭제</Button>
        </Popconfirm>
      </Space>

      <Text strong style={{ display: 'block', marginBottom: 4 }}>PropertyShapes</Text>
      {detail.property_shapes.length === 0 ? (
        <Text type="secondary" style={{ fontSize: 12 }}>PropertyShape 없음</Text>
      ) : (
        <List
          size="small"
          dataSource={detail.property_shapes}
          renderItem={(ps) => (
            <List.Item
              actions={[
                <Popconfirm
                  key="del"
                  title="PropertyShape 삭제"
                  onConfirm={() => handleDeleteProp(ps.prop_shape_iri)}
                >
                  <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>,
              ]}
            >
              <Space wrap>
                <Tag>path</Tag>
                <Text code style={{ fontSize: 11 }}>{shortIRI(ps.path)}</Text>
                {ps.min_count != null && <Tag color="gold">minCount={ps.min_count}</Tag>}
                {ps.max_count != null && <Tag color="gold">maxCount={ps.max_count}</Tag>}
                {ps.datatype && (
                  <Tag color="cyan">{ps.datatype.replace('http://www.w3.org/2001/XMLSchema#', 'xsd:')}</Tag>
                )}
              </Space>
            </List.Item>
          )}
        />
      )}

      <AddPropForm
        dataset={dataset}
        graph={graph}
        shapeIri={shapeIri}
        onAdded={reload}
      />
    </div>
  )
}

// ── Main Panel ────────────────────────────────────────────────────────────

const ShaclPanel: React.FC = () => {
  const { dataset, graph } = useOOI()

  const [shapes, setShapes] = useState<NodeShapeSummary[]>([])
  const [loadingShapes, setLoadingShapes] = useState(false)

  // Create shape form
  const [createForm] = Form.useForm()
  const [creating, setCreating] = useState(false)

  // Validation
  const [validating, setValidating] = useState(false)
  const [validResult, setValidResult] = useState<{
    conforms: boolean
    violations: ViolationItem[]
  } | null>(null)

  // Individual validation
  const [indIri, setIndIri] = useState('')
  const [validatingInd, setValidatingInd] = useState(false)
  const [indResult, setIndResult] = useState<{
    conforms: boolean
    violations: ViolationItem[]
  } | null>(null)

  const reloadShapes = async () => {
    if (!dataset || !graph) return
    setLoadingShapes(true)
    try {
      const data = await listShapes(dataset, graph)
      setShapes(data)
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setLoadingShapes(false)
    }
  }

  useEffect(() => {
    reloadShapes()
  }, [dataset, graph])

  const handleCreateShape = async () => {
    const vals = await createForm.validateFields()
    setCreating(true)
    try {
      await createShape(dataset!, graph!, vals.target_class, vals.label)
      message.success('NodeShape 생성됨')
      createForm.resetFields()
      reloadShapes()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setCreating(false)
    }
  }

  const handleValidate = async () => {
    if (!dataset || !graph) return
    setValidating(true)
    setValidResult(null)
    try {
      const res = await validateGraph(dataset, graph)
      setValidResult(res)
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setValidating(false)
    }
  }

  const handleValidateIndividual = async () => {
    if (!dataset || !graph || !indIri) return
    setValidatingInd(true)
    setIndResult(null)
    try {
      const res = await validateIndividual(dataset, graph, indIri)
      setIndResult(res)
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setValidatingInd(false)
    }
  }

  const violationColumns = [
    {
      title: 'Focus Node',
      dataIndex: 'focus_node',
      key: 'fn',
      ellipsis: true,
      render: (v: string | null) => (
        <Text style={{ fontFamily: 'monospace', fontSize: 11 }}>{v ? shortIRI(v) : '-'}</Text>
      ),
    },
    {
      title: 'Result Path',
      dataIndex: 'result_path',
      key: 'rp',
      ellipsis: true,
      render: (v: string | null) => (
        <Text style={{ fontFamily: 'monospace', fontSize: 11 }}>{v ? shortIRI(v) : '-'}</Text>
      ),
    },
    {
      title: 'Message',
      dataIndex: 'message',
      key: 'msg',
      ellipsis: true,
      render: (v: string | null) => <Text style={{ fontSize: 11 }}>{v ?? '-'}</Text>,
    },
  ]

  return (
    <div style={{ padding: '8px 0' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}>
        <Title level={5} style={{ margin: 0 }}>🛡️ SHACL Shapes</Title>
        <Text type="secondary" style={{ fontSize: 11 }}>pyshacl 기반 제약 검증</Text>
      </Space>

      {/* NodeShape 생성 */}
      <Form form={createForm} layout="inline" style={{ marginBottom: 12 }}>
        <Form.Item
          name="target_class"
          rules={[{ required: true, message: 'targetClass IRI 필수' }]}
        >
          <Input
            placeholder="sh:targetClass (IRI)"
            style={{ width: 260 }}
            prefix={<Tag style={{ margin: 0 }}>Class IRI</Tag>}
          />
        </Form.Item>
        <Form.Item name="label">
          <Input placeholder="Label (선택)" style={{ width: 160 }} />
        </Form.Item>
        <Form.Item>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            loading={creating}
            onClick={handleCreateShape}
            disabled={!dataset || !graph}
          >
            NodeShape 추가
          </Button>
        </Form.Item>
      </Form>

      {/* Shapes 목록 */}
      <Spin spinning={loadingShapes}>
        {shapes.length === 0 ? (
          <Alert type="info" showIcon message="SHACL Shape이 없습니다. NodeShape를 추가하세요." />
        ) : (
          <Collapse accordion>
            {shapes.map((shape) => (
              <Panel
                key={shape.shape_iri}
                header={
                  <Space>
                    <SafetyOutlined />
                    <Text strong>{shape.label ?? 'NodeShape'}</Text>
                    <Tag>{shortIRI(shape.target_class, 40)}</Tag>
                  </Space>
                }
              >
                <ShapeDetailPanel
                  dataset={dataset!}
                  graph={graph!}
                  shapeIri={shape.shape_iri}
                  onDeleted={reloadShapes}
                />
              </Panel>
            ))}
          </Collapse>
        )}
      </Spin>

      <Divider style={{ margin: '16px 0 12px' }} />

      {/* 그래프 전체 검증 */}
      <Space style={{ marginBottom: 12 }}>
        <Text strong>그래프 전체 검증</Text>
        <Button
          icon={<SafetyOutlined />}
          loading={validating}
          onClick={handleValidate}
          disabled={!dataset || !graph}
        >
          SHACL 검증 실행
        </Button>
      </Space>

      {validResult && (
        <Alert
          type={validResult.conforms ? 'success' : 'error'}
          showIcon
          icon={validResult.conforms ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
          message={validResult.conforms ? '검증 통과' : `위반 ${validResult.violations.length}건`}
          style={{ marginBottom: 8 }}
        />
      )}

      {validResult && !validResult.conforms && (
        <Table
          size="small"
          dataSource={validResult.violations}
          columns={violationColumns}
          rowKey={(_, i) => String(i)}
          pagination={{ pageSize: 10 }}
          style={{ marginBottom: 16 }}
        />
      )}

      <Divider style={{ margin: '12px 0' }} />

      {/* Individual 단위 검증 */}
      <Space wrap style={{ marginBottom: 8 }}>
        <Text strong>Individual 검증</Text>
        <Input
          placeholder="Individual IRI"
          style={{ width: 300 }}
          value={indIri}
          onChange={(e) => setIndIri(e.target.value)}
        />
        <Button
          loading={validatingInd}
          onClick={handleValidateIndividual}
          disabled={!dataset || !graph || !indIri}
        >
          검증
        </Button>
      </Space>

      {indResult && (
        <>
          <Alert
            type={indResult.conforms ? 'success' : 'error'}
            showIcon
            message={indResult.conforms ? '위반 없음' : `위반 ${indResult.violations.length}건`}
            style={{ marginBottom: 8 }}
          />
          {!indResult.conforms && (
            <Table
              size="small"
              dataSource={indResult.violations}
              columns={violationColumns}
              rowKey={(_, i) => String(i)}
              pagination={false}
            />
          )}
        </>
      )}
    </div>
  )
}

export default ShaclPanel
