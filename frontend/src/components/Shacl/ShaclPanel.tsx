/**
 * v03-A SHACL Panel
 * - NodeShape 목록 + 생성
 * - PropertyShape 추가/삭제
 * - 그래프 전체 검증 (Focus Node = label + 클릭 시 Detail)
 * - Individual 단위 검증 (label 기반 Select)
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
import { listClasses } from '../../api/classes'
import { listObjProps } from '../../api/objProps'
import { listDataProps } from '../../api/dataProps'
import { listIndividuals, getIndividual } from '../../api/individuals'
import type {
  ClassSummary, ObjPropSummary, DataPropSummary,
  IndividualSummary, IndividualDetail,
} from '../../types/ontology'
import IndividualDetailDrawer from '../Individuals/IndividualDetail'

const { Text, Title } = Typography
const { Panel } = Collapse

const shortIRI = (iri: string, max = 55) =>
  iri.length > max ? '…' + iri.slice(-(max - 1)) : iri

// ── PropertyShape 추가 폼 ──────────────────────────────────────────────────

interface AddPropFormProps {
  dataset: string
  graph: string
  shapeIri: string
  propOptions: { label: string; value: string; title: string }[]
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

const AddPropForm: React.FC<AddPropFormProps> = ({ dataset, graph, shapeIri, propOptions, onAdded }) => {
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
      <Form.Item name="path" rules={[{ required: true, message: 'Property 선택 필수' }]}>
        <Select
          placeholder="sh:path (Property)"
          style={{ width: 220 }}
          showSearch
          optionFilterProp="label"
          options={propOptions}
        />
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
  propOptions: { label: string; value: string; title: string }[]
  onDeleted: () => void
}

const ShapeDetailPanel: React.FC<ShapeDetailPanelProps> = ({
  dataset, graph, shapeIri, propOptions, onDeleted,
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
        propOptions={propOptions}
        onAdded={reload}
      />
    </div>
  )
}

// ── Main Panel ────────────────────────────────────────────────────────────

interface ShaclPanelProps {
  defaultOpenShapeIri?: string  // 이 IRI의 Collapse 패널을 자동 오픈
  onOpenHandled?: () => void    // 오픈 처리 후 부모에게 알림 (state 초기화)
}

const ShaclPanel: React.FC<ShaclPanelProps> = ({ defaultOpenShapeIri, onOpenHandled }) => {
  const { dataset, graph, graphs, namespace } = useOOI()

  const [shapes, setShapes] = useState<NodeShapeSummary[]>([])
  const [loadingShapes, setLoadingShapes] = useState(false)

  // Class / Property / Individual 메타데이터
  const [classes, setClasses] = useState<ClassSummary[]>([])
  const [objProps, setObjProps] = useState<ObjPropSummary[]>([])
  const [dataProps, setDataProps] = useState<DataPropSummary[]>([])
  const [individuals, setIndividuals] = useState<IndividualSummary[]>([])
  // Shape target class 기준으로 필터링된 Individual 목록
  const [targetIndividuals, setTargetIndividuals] = useState<IndividualSummary[]>([])

  // Collapse 열린 패널 key
  const [collapseKey, setCollapseKey] = useState<string | undefined>(undefined)

  // Create shape form
  const [createForm] = Form.useForm()
  const [creating, setCreating] = useState(false)

  // 그래프 전체 검증
  const [validating, setValidating] = useState(false)
  const [validResult, setValidResult] = useState<{
    conforms: boolean
    violations: ViolationItem[]
  } | null>(null)

  // Individual 단위 검증
  const [indIri, setIndIri] = useState<string | undefined>(undefined)
  const [validatingInd, setValidatingInd] = useState(false)
  const [indResult, setIndResult] = useState<{
    conforms: boolean
    violations: ViolationItem[]
  } | null>(null)

  // Individual Detail Drawer
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerDetail, setDrawerDetail] = useState<IndividualDetail | null>(null)
  const [drawerLoading, setDrawerLoading] = useState(false)

  const shortLabel = (iri: string) => iri.split(/[#/]/).pop() ?? iri
  const indLabel = (iri: string) =>
    individuals.find((i) => i.iri === iri)?.label ?? shortLabel(iri)

  const openIndividualDetail = async (iri: string) => {
    if (!dataset || !graph) return
    setDrawerDetail(null)
    setDrawerOpen(true)
    setDrawerLoading(true)
    try {
      setDrawerDetail(await getIndividual(dataset, graph, iri))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDrawerLoading(false)
    }
  }

  const reloadTargetIndividuals = async (loadedShapes: NodeShapeSummary[]) => {
    if (!dataset || graphs.length === 0 || !namespace) return
    const targetClasses = [...new Set(loadedShapes.map((s) => s.target_class))]
    if (targetClasses.length === 0) { setTargetIndividuals([]); return }
    try {
      const results = await Promise.all(
        targetClasses.map((cls) => listIndividuals(dataset, graphs, namespace, cls))
      )
      // 중복 제거 (한 individual이 여러 target class에 걸칠 수 있음)
      const seen = new Set<string>()
      const merged: IndividualSummary[] = []
      for (const list of results) {
        for (const ind of list) {
          if (!seen.has(ind.iri)) { seen.add(ind.iri); merged.push(ind) }
        }
      }
      setTargetIndividuals(merged)
    } catch { /* 무시 */ }
  }

  const reloadShapes = async () => {
    if (!dataset || !graph) return
    setLoadingShapes(true)
    try {
      const data = await listShapes(dataset, graph)
      setShapes(data)
      await reloadTargetIndividuals(data)
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setLoadingShapes(false)
    }
  }

  // defaultOpenShapeIri가 주어지면 해당 Collapse 자동 오픈
  useEffect(() => {
    if (!defaultOpenShapeIri) return
    setCollapseKey(defaultOpenShapeIri)
    onOpenHandled?.()
  }, [defaultOpenShapeIri])

  useEffect(() => {
    reloadShapes()
    if (!dataset || graphs.length === 0 || !namespace) return
    Promise.all([
      listClasses(dataset, graphs, namespace),
      listObjProps(dataset, graphs, namespace),
      listDataProps(dataset, graphs, namespace),
      listIndividuals(dataset, graphs, namespace),
    ]).then(([cls, op, dp, inds]) => {
      setClasses(cls)
      setObjProps(op)
      setDataProps(dp)
      setIndividuals(inds)
    }).catch(() => {})
  }, [dataset, graph, graphs, namespace])

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

  // Focus Node: label 클릭 시 Detail Drawer 오픈
  const violationColumns = [
    {
      title: 'Focus Node',
      dataIndex: 'focus_node',
      key: 'fn',
      render: (v: string | null) =>
        v ? (
          <a
            style={{ fontSize: 11 }}
            title={v}
            onClick={() => openIndividualDetail(v)}
          >
            {indLabel(v)}
          </a>
        ) : (
          <Text style={{ fontSize: 11 }}>-</Text>
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

  const classOptions = classes.map((c) => ({
    label: c.label ?? shortLabel(c.iri),
    value: c.iri,
    title: c.iri,
  }))

  // Shape가 있으면 target class 기준 필터링, 없으면 전체
  const indOptions = (targetIndividuals.length > 0 ? targetIndividuals : individuals).map((i) => ({
    label: i.label ?? shortLabel(i.iri),
    value: i.iri,
    title: i.iri,
  }))

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
          rules={[{ required: true, message: 'Target Class 선택 필수' }]}
        >
          <Select
            placeholder="Target Class"
            style={{ width: 220 }}
            showSearch
            optionFilterProp="label"
            options={classOptions}
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
          <Collapse
            accordion
            activeKey={collapseKey}
            onChange={(k) => setCollapseKey(Array.isArray(k) ? k[0] : k as string | undefined)}
          >
            {shapes.map((shape) => {
              const propOptions = [
                ...objProps.map((p) => ({
                  label: p.label ?? shortLabel(p.iri),
                  value: p.iri,
                  title: p.iri,
                })),
                ...dataProps.map((p) => ({
                  label: p.label ?? shortLabel(p.iri),
                  value: p.iri,
                  title: p.iri,
                })),
              ]
              const targetLabel = classes.find((c) => c.iri === shape.target_class)?.label
                ?? shortLabel(shape.target_class)
              return (
                <Panel
                  key={shape.shape_iri}
                  header={
                    <Space>
                      <SafetyOutlined />
                      <Text strong>{shape.label ?? 'NodeShape'}</Text>
                      <Tag>{targetLabel}</Tag>
                    </Space>
                  }
                >
                  <ShapeDetailPanel
                    dataset={dataset!}
                    graph={graph!}
                    shapeIri={shape.shape_iri}
                    propOptions={propOptions}
                    onDeleted={reloadShapes}
                  />
                </Panel>
              )
            })}
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
        <Select
          placeholder="Individual 선택"
          style={{ width: 260 }}
          showSearch
          optionFilterProp="label"
          allowClear
          options={indOptions}
          value={indIri}
          onChange={(v) => { setIndIri(v); setIndResult(null) }}
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

      {/* Individual Detail Drawer */}
      <IndividualDetailDrawer
        open={drawerOpen}
        detail={drawerDetail}
        loading={drawerLoading}
        dataset={dataset ?? ''}
        graph={graph ?? ''}
        namespaces={namespace ? [namespace] : []}
        allClasses={classes}
        allDataProps={dataProps}
        allObjProps={objProps}
        onClose={() => setDrawerOpen(false)}
        onRefresh={() => {}}
      />
    </div>
  )
}

export default ShaclPanel
