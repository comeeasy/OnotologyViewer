/**
 * v03-C Datasource 매핑 Panel
 * - Datasource 목록 + 생성
 * - ClassMapping 관리
 * - PropertyMapping 관리
 */

import React, { useEffect, useState } from 'react'
import {
  Alert, Button, Card, Collapse, Descriptions, Form, Input, List,
  Popconfirm, Select, Space, Tag, Typography, message,
} from 'antd'
import {
  DatabaseOutlined, DeleteOutlined, EyeOutlined, PlusOutlined,
} from '@ant-design/icons'
import { useOOI } from '../../context/OOIContext'
import {
  listDatasources, createDatasource, getDatasource,
  deleteDatasource, addClassMapping, deleteClassMapping, addPropertyMapping,
  previewDatasource,
} from '../../api/datasources'
import type { DatasourceSummary, DatasourceDetail, ClassMappingItem } from '../../api/datasources'

const { Text, Title } = Typography
const { Panel } = Collapse

const DS_TYPES = [
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON' },
  { value: 'rest', label: 'REST API' },
  { value: 'sparql', label: 'SPARQL' },
]

const shortIRI = (iri: string, max = 50) =>
  iri.length > max ? '…' + iri.slice(-(max - 1)) : iri

// ── PropertyMapping 추가 폼 ───────────────────────────────────────────────

interface PropMappingFormProps {
  dataset: string
  graph: string
  dsIri: string
  mappingIri: string
  onAdded: () => void
}

const PropMappingForm: React.FC<PropMappingFormProps> = ({
  dataset, graph, dsIri, mappingIri, onAdded,
}) => {
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  const handleAdd = async () => {
    const vals = await form.validateFields()
    setSaving(true)
    try {
      await addPropertyMapping(dataset, graph, dsIri, mappingIri, {
        source_field: vals.source_field,
        target_property: vals.target_property,
      })
      message.success('Property 매핑 추가됨')
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
      <Form.Item name="source_field" rules={[{ required: true }]}>
        <Input placeholder="소스 필드명" style={{ width: 140 }} />
      </Form.Item>
      <Form.Item name="target_property" rules={[{ required: true }]}>
        <Input placeholder="타겟 Property IRI" style={{ width: 240 }} />
      </Form.Item>
      <Form.Item>
        <Button size="small" type="primary" loading={saving} onClick={handleAdd} icon={<PlusOutlined />}>
          추가
        </Button>
      </Form.Item>
    </Form>
  )
}

// ── ClassMapping 상세 ─────────────────────────────────────────────────────

interface ClassMappingCardProps {
  mapping: ClassMappingItem
  dataset: string
  graph: string
  dsIri: string
  onDeleted: () => void
  onPropAdded: () => void
}

const ClassMappingCard: React.FC<ClassMappingCardProps> = ({
  mapping, dataset, graph, dsIri, onDeleted, onPropAdded,
}) => {
  const handleDeleteMapping = async () => {
    try {
      await deleteClassMapping(dataset, graph, dsIri, mapping.mapping_iri)
      message.success('ClassMapping 삭제됨')
      onDeleted()
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  return (
    <Card
      size="small"
      title={
        <Space>
          <Tag color="blue">Class</Tag>
          <Text code style={{ fontSize: 11 }}>{shortIRI(mapping.target_class, 45)}</Text>
          {mapping.label && <Text type="secondary" style={{ fontSize: 11 }}>({mapping.label})</Text>}
        </Space>
      }
      extra={
        <Popconfirm title="ClassMapping과 PropertyMapping을 모두 삭제합니다." onConfirm={handleDeleteMapping}>
          <Button size="small" danger icon={<DeleteOutlined />}>삭제</Button>
        </Popconfirm>
      }
      style={{ marginBottom: 6 }}
    >
      <Text style={{ fontSize: 12 }}>ID 필드: <Text code>{mapping.identifier_field}</Text></Text>

      <div style={{ marginTop: 6 }}>
        <Text style={{ fontSize: 12, fontWeight: 600 }}>Property 매핑</Text>
        {mapping.property_mappings.length === 0 ? (
          <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>없음</Text>
        ) : (
          <List
            size="small"
            dataSource={mapping.property_mappings}
            renderItem={(pm) => (
              <List.Item>
                <Space>
                  <Tag>{pm.source_field}</Tag>
                  <Text style={{ fontSize: 11 }}>→</Text>
                  <Text code style={{ fontSize: 11 }}>{shortIRI(pm.target_property, 40)}</Text>
                </Space>
              </List.Item>
            )}
          />
        )}
        <PropMappingForm
          dataset={dataset}
          graph={graph}
          dsIri={dsIri}
          mappingIri={mapping.mapping_iri}
          onAdded={onPropAdded}
        />
      </div>
    </Card>
  )
}

// ── Datasource 상세 패널 ──────────────────────────────────────────────────

interface DatasourceDetailPanelProps {
  dataset: string
  graph: string
  dsIri: string
}

const DatasourceDetailPanel: React.FC<DatasourceDetailPanelProps> = ({
  dataset, graph, dsIri,
}) => {
  const [detail, setDetail] = useState<DatasourceDetail | null>(null)
  const [mappingForm] = Form.useForm()
  const [addingMapping, setAddingMapping] = useState(false)

  // 미리보기
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewData, setPreviewData] = useState<{ rows: unknown[]; error: string | null } | null>(null)

  const handlePreview = async () => {
    setPreviewLoading(true)
    setPreviewData(null)
    try {
      const res = await previewDatasource(dataset, graph, dsIri)
      setPreviewData({ rows: res.rows, error: res.error })
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setPreviewLoading(false)
    }
  }

  const reload = async () => {
    try {
      const d = await getDatasource(dataset, graph, dsIri)
      setDetail(d)
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  useEffect(() => { reload() }, [dsIri])

  const handleAddMapping = async () => {
    const vals = await mappingForm.validateFields()
    setAddingMapping(true)
    try {
      await addClassMapping(dataset, graph, dsIri, {
        target_class: vals.target_class,
        identifier_field: vals.identifier_field,
        label: vals.label,
      })
      message.success('ClassMapping 추가됨')
      mappingForm.resetFields()
      reload()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setAddingMapping(false)
    }
  }

  if (!detail) return <Text type="secondary">로딩 중...</Text>

  return (
    <div>
      <Descriptions size="small" column={1} style={{ marginBottom: 8 }}>
        <Descriptions.Item label="타입"><Tag>{detail.ds_type.toUpperCase()}</Tag></Descriptions.Item>
        <Descriptions.Item label="연결 정보">
          <Text code style={{ fontSize: 11 }}>{detail.connection_info}</Text>
        </Descriptions.Item>
        {detail.description && (
          <Descriptions.Item label="설명">{detail.description}</Descriptions.Item>
        )}
      </Descriptions>

      {/* 미리보기 */}
      <Space style={{ marginBottom: 8 }}>
        <Button
          size="small"
          icon={<EyeOutlined />}
          loading={previewLoading}
          onClick={handlePreview}
        >
          미리보기
        </Button>
      </Space>
      {previewData && (
        previewData.error ? (
          <Alert type="error" message={`미리보기 오류: ${previewData.error}`} style={{ marginBottom: 8 }} />
        ) : (
          <Alert
            type="info"
            message={`미리보기 (${previewData.rows.length}행)`}
            description={
              <pre style={{ fontSize: 11, maxHeight: 150, overflow: 'auto', margin: 0 }}>
                {JSON.stringify(previewData.rows, null, 2)}
              </pre>
            }
            style={{ marginBottom: 8 }}
          />
        )
      )}

      <Text strong style={{ display: 'block', marginBottom: 4 }}>Class 매핑</Text>

      {detail.mappings.length === 0 ? (
        <Alert type="info" showIcon message="ClassMapping 없음" style={{ marginBottom: 8 }} />
      ) : (
        detail.mappings.map((m) => (
          <ClassMappingCard
            key={m.mapping_iri}
            mapping={m}
            dataset={dataset}
            graph={graph}
            dsIri={dsIri}
            onDeleted={reload}
            onPropAdded={reload}
          />
        ))
      )}

      {/* ClassMapping 추가 폼 */}
      <Card size="small" title="ClassMapping 추가" style={{ marginTop: 8 }}>
        <Form form={mappingForm} layout="inline">
          <Form.Item name="target_class" rules={[{ required: true }]}>
            <Input placeholder="타겟 Class IRI" style={{ width: 220 }} />
          </Form.Item>
          <Form.Item name="identifier_field" rules={[{ required: true }]}>
            <Input placeholder="ID 필드명" style={{ width: 130 }} />
          </Form.Item>
          <Form.Item name="label">
            <Input placeholder="Label (선택)" style={{ width: 110 }} />
          </Form.Item>
          <Form.Item>
            <Button
              size="small"
              type="primary"
              loading={addingMapping}
              onClick={handleAddMapping}
              icon={<PlusOutlined />}
            >
              추가
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}

// ── Main Panel ─────────────────────────────────────────────────────────────

const DatasourcesPanel: React.FC = () => {
  const { dataset, graph } = useOOI()

  const [datasources, setDatasources] = useState<DatasourceSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [createForm] = Form.useForm()
  const [creating, setCreating] = useState(false)

  const reload = async () => {
    if (!dataset || !graph) return
    setLoading(true)
    try {
      const data = await listDatasources(dataset, graph)
      setDatasources(data)
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { reload() }, [dataset, graph])

  const handleCreate = async () => {
    const vals = await createForm.validateFields()
    setCreating(true)
    try {
      await createDatasource({
        dataset: dataset!,
        graph: graph!,
        label: vals.label,
        ds_type: vals.ds_type,
        connection_info: vals.connection_info,
        description: vals.description,
      })
      message.success('Datasource 생성됨')
      createForm.resetFields()
      reload()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (dsIri: string) => {
    try {
      await deleteDatasource(dataset!, graph!, dsIri)
      message.success('Datasource 삭제됨')
      reload()
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  return (
    <div style={{ padding: '8px 0' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}>
        <Title level={5} style={{ margin: 0 }}>🗄️ Datasource 매핑</Title>
        <Text type="secondary" style={{ fontSize: 11 }}>외부 데이터소스 ↔ 온톨로지 매핑</Text>
      </Space>

      {/* Datasource 생성 폼 */}
      <Card size="small" title="Datasource 추가" style={{ marginBottom: 12 }}>
        <Form form={createForm} layout="inline">
          <Form.Item name="label" rules={[{ required: true }]}>
            <Input placeholder="이름" style={{ width: 150 }} />
          </Form.Item>
          <Form.Item name="ds_type" rules={[{ required: true }]}>
            <Select placeholder="타입" style={{ width: 110 }} options={DS_TYPES} />
          </Form.Item>
          <Form.Item name="connection_info" rules={[{ required: true }]}>
            <Input placeholder="연결 정보 (URL/경로)" style={{ width: 200 }} />
          </Form.Item>
          <Form.Item name="description">
            <Input placeholder="설명 (선택)" style={{ width: 140 }} />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              loading={creating}
              onClick={handleCreate}
              disabled={!dataset || !graph}
            >
              추가
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {/* Datasource 목록 */}
      {loading ? (
        <Text type="secondary">로딩 중...</Text>
      ) : datasources.length === 0 ? (
        <Alert type="info" showIcon message="등록된 Datasource가 없습니다." />
      ) : (
        <Collapse accordion>
          {datasources.map((ds) => (
            <Panel
              key={ds.datasource_iri}
              header={
                <Space>
                  <DatabaseOutlined />
                  <Text strong>{ds.label ?? ds.datasource_iri}</Text>
                  <Tag color="geekblue">{ds.ds_type.toUpperCase()}</Tag>
                  <Text type="secondary" style={{ fontSize: 11 }}>{ds.connection_info}</Text>
                </Space>
              }
              extra={
                <Popconfirm
                  title="Datasource와 모든 매핑을 삭제합니다."
                  onConfirm={() => handleDelete(ds.datasource_iri)}
                >
                  <Button
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={(e) => e.stopPropagation()}
                  >
                    삭제
                  </Button>
                </Popconfirm>
              }
            >
              <DatasourceDetailPanel
                dataset={dataset!}
                graph={graph!}
                dsIri={ds.datasource_iri}
              />
            </Panel>
          ))}
        </Collapse>
      )}
    </div>
  )
}

export default DatasourcesPanel
