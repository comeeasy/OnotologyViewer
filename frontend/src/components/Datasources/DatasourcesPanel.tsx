/**
 * v03-D Datasource 매핑 Panel
 * - Datasource 목록 + 생성
 * - ClassMapping: targetClass → Select(레이블 기반)
 * - PropertyMapping: targetProperty → Select(레이블 기반)
 */

import React, { useEffect, useMemo, useState } from 'react'
import {
  Alert, Button, Card, Collapse, Descriptions, Form, Input, List,
  Popconfirm, Select, Space, Tag, Typography, message,
} from 'antd'
import {
  DatabaseOutlined, DeleteOutlined, EyeOutlined, ImportOutlined, PlusOutlined, UploadOutlined,
} from '@ant-design/icons'
import { useOOI } from '../../context/OOIContext'
import {
  listDatasources, createDatasource, getDatasource,
  deleteDatasource, addClassMapping, deleteClassMapping, addPropertyMapping,
  previewDatasource, uploadDatasourceFile, importDatasource,
} from '../../api/datasources'
import type { DatasourceSummary, DatasourceDetail, ClassMappingItem, ImportResult } from '../../api/datasources'
import { listClasses } from '../../api/classes'
import { listObjProps } from '../../api/objProps'
import { listDataProps } from '../../api/dataProps'
import type { ClassSummary, ObjPropSummary, DataPropSummary } from '../../types/ontology'

const { Text, Title } = Typography
const { Panel } = Collapse

const DS_TYPES = [
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON' },
  { value: 'rest', label: 'REST API' },
  { value: 'sparql', label: 'SPARQL' },
]

const localName = (iri: string) => iri.split(/[#/]/).filter(Boolean).pop() ?? iri

// ── PropertyMapping 추가 폼 ───────────────────────────────────────────────

interface PropMappingFormProps {
  dataset: string
  graph: string
  dsIri: string
  mappingIri: string
  objProps: ObjPropSummary[]
  dataProps: DataPropSummary[]
  onAdded: () => void
}

const PropMappingForm: React.FC<PropMappingFormProps> = ({
  dataset, graph, dsIri, mappingIri, objProps, dataProps, onAdded,
}) => {
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  const propOptions = useMemo(() => [
    {
      label: 'Object Property',
      options: objProps.map((p) => ({
        label: p.label ?? localName(p.iri),
        value: p.iri,
        title: p.iri,
      })),
    },
    {
      label: 'Data Property',
      options: dataProps.map((p) => ({
        label: p.label ?? localName(p.iri),
        value: p.iri,
        title: p.iri,
      })),
    },
  ], [objProps, dataProps])

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
        <Input placeholder="소스 필드명" style={{ width: 130 }} />
      </Form.Item>
      <Form.Item name="target_property" rules={[{ required: true }]}>
        <Select
          placeholder="타겟 Property"
          style={{ width: 200 }}
          options={propOptions}
          showSearch
          optionFilterProp="label"
          allowClear
        />
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
  classMap: Map<string, string>   // iri → label
  propLabelMap: Map<string, string>
  objProps: ObjPropSummary[]
  dataProps: DataPropSummary[]
  onDeleted: () => void
  onPropAdded: () => void
}

const ClassMappingCard: React.FC<ClassMappingCardProps> = ({
  mapping, dataset, graph, dsIri,
  classMap, propLabelMap, objProps, dataProps,
  onDeleted, onPropAdded,
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

  const classLabel = classMap.get(mapping.target_class) ?? localName(mapping.target_class)

  return (
    <Card
      size="small"
      title={
        <Space>
          <Tag color="blue">Class</Tag>
          <Text strong style={{ fontSize: 13 }}>{classLabel}</Text>
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
      <Space size={16} style={{ display: 'flex', flexWrap: 'wrap', marginBottom: 4 }}>
        <Text style={{ fontSize: 12 }}>식별자 (PK): <Text code>{mapping.identifier_field}</Text></Text>
        {mapping.label_field && (
          <Text style={{ fontSize: 12 }}>rdfs:label ← <Text code>{mapping.label_field}</Text></Text>
        )}
        {mapping.comment_field && (
          <Text style={{ fontSize: 12 }}>rdfs:comment ← <Text code>{mapping.comment_field}</Text></Text>
        )}
      </Space>

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
                  <Text strong style={{ fontSize: 12 }}>
                    {propLabelMap.get(pm.target_property) ?? localName(pm.target_property)}
                  </Text>
                  <Text type="secondary" style={{ fontSize: 10 }} title={pm.target_property}>
                    ({localName(pm.target_property)})
                  </Text>
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
          objProps={objProps}
          dataProps={dataProps}
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
  classes: ClassSummary[]
  objProps: ObjPropSummary[]
  dataProps: DataPropSummary[]
}

const DatasourceDetailPanel: React.FC<DatasourceDetailPanelProps> = ({
  dataset, graph, dsIri, classes, objProps, dataProps,
}) => {
  const [detail, setDetail] = useState<DatasourceDetail | null>(null)
  const [mappingForm] = Form.useForm()
  const [addingMapping, setAddingMapping] = useState(false)

  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewData, setPreviewData] = useState<{ rows: unknown[]; error: string | null } | null>(null)

  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)

  // iri → label 맵
  const classMap = useMemo(() => new Map(classes.map((c) => [c.iri, c.label ?? localName(c.iri)])), [classes])
  const propLabelMap = useMemo(() => {
    const m = new Map<string, string>()
    objProps.forEach((p) => m.set(p.iri, p.label ?? localName(p.iri)))
    dataProps.forEach((p) => m.set(p.iri, p.label ?? localName(p.iri)))
    return m
  }, [objProps, dataProps])

  const classOptions = useMemo(() =>
    classes.map((c) => ({ label: c.label ?? localName(c.iri), value: c.iri, title: c.iri })),
    [classes],
  )

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

  const handleImport = async () => {
    setImporting(true)
    setImportResult(null)
    try {
      const res = await importDatasource(dataset, graph, dsIri)
      setImportResult(res)
      if (res.errors.length === 0) {
        message.success(`Import 완료: ${res.imported_individuals}개 Individual, ${res.inserted_triples}개 트리플`)
      } else {
        message.warning(`Import 완료 (오류 ${res.errors.length}건)`)
      }
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setImporting(false)
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
        label_field: vals.label_field || undefined,
        comment_field: vals.comment_field || undefined,
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

      {/* 미리보기 + Import */}
      <Space style={{ marginBottom: 8 }}>
        <Button size="small" icon={<EyeOutlined />} loading={previewLoading} onClick={handlePreview}>
          미리보기
        </Button>
        <Button
          size="small"
          type="primary"
          icon={<ImportOutlined />}
          loading={importing}
          onClick={handleImport}
        >
          Import 실행
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
      {importResult && (
        <Alert
          type={importResult.errors.length === 0 ? 'success' : 'warning'}
          message={
            <Space>
              <Text strong>Import 결과</Text>
              <Tag color="blue">{importResult.imported_individuals}개 Individual</Tag>
              <Tag color="green">{importResult.inserted_triples}개 트리플</Tag>
              {importResult.skipped_rows > 0 && (
                <Tag color="orange">{importResult.skipped_rows}행 스킵</Tag>
              )}
            </Space>
          }
          description={
            importResult.errors.length > 0 ? (
              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 11 }}>
                {importResult.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            ) : null
          }
          style={{ marginBottom: 8 }}
          closable
          onClose={() => setImportResult(null)}
        />
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
            classMap={classMap}
            propLabelMap={propLabelMap}
            objProps={objProps}
            dataProps={dataProps}
            onDeleted={reload}
            onPropAdded={reload}
          />
        ))
      )}

      {/* ClassMapping 추가 폼 */}
      <Card size="small" title="ClassMapping 추가" style={{ marginTop: 8 }}>
        <Form form={mappingForm} layout="vertical">
          <Space wrap>
            <Form.Item name="target_class" label="타겟 Class" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
              <Select
                placeholder="Class 선택"
                style={{ width: 200 }}
                options={classOptions}
                showSearch
                optionFilterProp="label"
                allowClear
              />
            </Form.Item>
            <Form.Item name="identifier_field" label="식별자 필드 (PK)" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
              <Input placeholder="예: isbn, id" style={{ width: 150 }} />
            </Form.Item>
            <Form.Item
              name="label_field"
              label={<span>Label 필드 <Text type="secondary" style={{ fontSize: 11 }}>→ rdfs:label</Text></span>}
              style={{ marginBottom: 8 }}
            >
              <Input placeholder="예: title, name" style={{ width: 150 }} />
            </Form.Item>
            <Form.Item
              name="comment_field"
              label={<span>Comment 필드 <Text type="secondary" style={{ fontSize: 11 }}>→ rdfs:comment</Text></span>}
              style={{ marginBottom: 8 }}
            >
              <Input placeholder="예: description" style={{ width: 150 }} />
            </Form.Item>
            <Form.Item name="label" label="매핑 이름 (선택)" style={{ marginBottom: 8 }}>
              <Input placeholder="이 매핑의 이름" style={{ width: 130 }} />
            </Form.Item>
          </Space>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              size="small" type="primary" loading={addingMapping}
              onClick={handleAddMapping} icon={<PlusOutlined />}
            >
              ClassMapping 추가
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}

// ── Main Panel ─────────────────────────────────────────────────────────────

const DatasourcesPanel: React.FC = () => {
  const { dataset, graph, graphs, namespace } = useOOI()

  const [datasources, setDatasources] = useState<DatasourceSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [createForm] = Form.useForm()
  const [creating, setCreating] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const res = await uploadDatasourceFile(file)
      createForm.setFieldValue('connection_info', res.path)
      message.success(`업로드 완료: ${res.filename}`)
    } catch (err: unknown) {
      message.error((err as Error).message)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // 온톨로지 데이터 (매핑 Select용)
  const [classes, setClasses] = useState<ClassSummary[]>([])
  const [objProps, setObjProps] = useState<ObjPropSummary[]>([])
  const [dataProps, setDataProps] = useState<DataPropSummary[]>([])

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
          <Form.Item>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.json"
              style={{ display: 'none' }}
              onChange={handleFileUpload}
            />
            <Button
              icon={<UploadOutlined />}
              loading={uploading}
              onClick={() => fileInputRef.current?.click()}
              title="CSV/JSON 파일 업로드 후 경로 자동 입력"
            >
              파일 업로드
            </Button>
          </Form.Item>
          <Form.Item name="description">
            <Input placeholder="설명 (선택)" style={{ width: 140 }} />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary" icon={<PlusOutlined />} loading={creating}
              onClick={handleCreate} disabled={!dataset || !graph}
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
                    size="small" danger icon={<DeleteOutlined />}
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
                classes={classes}
                objProps={objProps}
                dataProps={dataProps}
              />
            </Panel>
          ))}
        </Collapse>
      )}
    </div>
  )
}

export default DatasourcesPanel
