import React, { useEffect, useRef, useState } from 'react'
import {
  Alert, Badge, Button, Descriptions, Divider, Form, Input,
  Modal, Popconfirm, Radio, Select, Space, Tooltip, Typography, message,
} from 'antd'
import {
  CheckCircleOutlined, CloseCircleOutlined,
  DeleteOutlined, EditOutlined, LoadingOutlined, PlusOutlined, SettingOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import {
  checkHealth, createDataset, createGraph, deleteDataset, deleteGraph,
  getGraphDetail, patchGraph, getDatasets, getGraphs, getNamespacesInGraph,
  declareNamespace, listUniversalNamespaces, importUniversalNs, uploadTTL,
} from '../../api/navigator'
import type { GraphDetail, UniversalNsItem, UploadTTLResponse } from '../../api/navigator'
import { useOOI } from '../../context/OOIContext'
import type { Dataset, Namespace } from '../../types/ontology'
import FusekiConfigModal from './FusekiConfigModal'
import NamespaceEditModal from './NamespaceEditModal'

const { Text } = Typography

type HealthStatus = 'checking' | 'ok' | 'error'

const OOINavigator: React.FC = () => {
  const { dataset, graph, namespace, setOOI, clear } = useOOI()

  const [health, setHealth] = useState<HealthStatus>('checking')
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [graphs, setGraphs] = useState<string[]>([])
  const [namespaces, setNamespaces] = useState<Namespace[]>([])

  const [selDataset, setSelDataset] = useState<string | null>(null)
  const [selGraph, setSelGraph] = useState<string | null>(null)
  const [selNs, setSelNs] = useState<string[]>([])

  // Dataset 생성/삭제
  const [dsModalOpen, setDsModalOpen] = useState(false)
  const [dsForm] = Form.useForm()
  const [dsCreating, setDsCreating] = useState(false)

  const handleCreateDataset = async () => {
    const { name } = await dsForm.validateFields()
    setDsCreating(true)
    try {
      await createDataset(name.trim())
      message.success(`Dataset '${name}'이(가) 생성되었습니다.`)
      setDsModalOpen(false)
      dsForm.resetFields()
      const updated = await getDatasets()
      setDatasets(updated)
      setSelDataset(name.trim())
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDsCreating(false)
    }
  }

  const handleDeleteDataset = async () => {
    if (!selDataset) return
    try {
      await deleteDataset(selDataset)
      message.success(`Dataset '${selDataset}'이(가) 삭제되었습니다.`)
      setSelDataset(null); setSelGraph(null); setSelNs([])
      const updated = await getDatasets()
      setDatasets(updated)
      if (dataset === selDataset) clear()
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  // Graph 생성 Modal
  const [graphModalOpen, setGraphModalOpen] = useState(false)
  const [graphForm] = Form.useForm()
  const [graphCreating, setGraphCreating] = useState(false)

  // Graph 상세 / 수정
  const [graphDetail, setGraphDetail] = useState<GraphDetail | null>(null)
  const [editGraphOpen, setEditGraphOpen] = useState(false)
  const [editGraphForm] = Form.useForm()

  // Fuseki 연결 설정 Modal
  const [configModalOpen, setConfigModalOpen] = useState(false)

  // v02-C: Namespace 편집 Modal
  const [nsEditTarget, setNsEditTarget] = useState<Namespace | null>(null)

  // v02-C: Namespace 선언 Modal
  const [nsDeclOpen, setNsDeclOpen] = useState(false)
  const [nsDeclForm] = Form.useForm()
  const [nsDeclaring, setNsDeclaring] = useState(false)

  // v03-D: Universal NS import Modal
  const [universalNsModalOpen, setUniversalNsModalOpen] = useState(false)
  const [universalNsList, setUniversalNsList] = useState<UniversalNsItem[]>([])
  const [importingNs, setImportingNs] = useState<string | null>(null)

  // TTL 업로드
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [uploadMode, setUploadMode] = useState<'append' | 'replace'>('append')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadResult, setUploadResult] = useState<UploadTTLResponse | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDeclareNamespace = async () => {
    if (!selDataset || !selGraph) return
    const { ns_iri, prefix } = await nsDeclForm.validateFields()
    setNsDeclaring(true)
    try {
      await declareNamespace(selDataset, selGraph, ns_iri.trim(), prefix.trim())
      message.success('Namespace가 선언되었습니다.')
      setNsDeclOpen(false)
      nsDeclForm.resetFields()
      reloadNamespaces()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setNsDeclaring(false)
    }
  }

  const handleOpenUniversalNsModal = async () => {
    if (universalNsList.length === 0) {
      const list = await listUniversalNamespaces()
      setUniversalNsList(list)
    }
    setUniversalNsModalOpen(true)
  }

  const handleUploadTTL = async () => {
    if (!selDataset || !selGraph || !uploadFile) return
    setUploadLoading(true)
    setUploadResult(null)
    try {
      const res = await uploadTTL(selDataset, selGraph, uploadFile, uploadMode)
      setUploadResult(res)
      message.success(res.message)
      // 그래프 detail 갱신
      getGraphDetail(selDataset, selGraph).then(setGraphDetail).catch(() => {})
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setUploadLoading(false)
    }
  }

  const handleImportUniversalNs = async (prefix: string) => {
    if (!selDataset || !selGraph) return
    setImportingNs(prefix)
    try {
      await importUniversalNs(selDataset, selGraph, prefix)
      message.success(`${prefix}: NS가 추가되었습니다.`)
      reloadNamespaces()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setImportingNs(null)
    }
  }

  const reloadNamespaces = () => {
    if (selDataset && selGraph) {
      getNamespacesInGraph(selDataset, selGraph)
        .then(setNamespaces)
        .catch(() => setNamespaces([]))
    }
  }

  const recheckHealth = () => {
    setHealth('checking')
    checkHealth()
      .then(() => { setHealth('ok'); getDatasets().then(setDatasets).catch(() => {}) })
      .catch(() => setHealth('error'))
  }

  // ── 초기 health + datasets ──
  useEffect(() => {
    recheckHealth()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── dataset 선택 시 graphs 로드 ──
  const loadGraphs = (ds: string) => {
    getGraphs(ds).then(setGraphs).catch(() => setGraphs([]))
  }

  useEffect(() => {
    if (!selDataset) { setGraphs([]); setSelGraph(null); return }
    loadGraphs(selDataset)
  }, [selDataset])

  // ── graph 선택 시 namespaces + detail 로드 ──
  useEffect(() => {
    if (!selDataset || !selGraph) {
      setNamespaces([]); setSelNs([]); setGraphDetail(null); return
    }
    getNamespacesInGraph(selDataset, selGraph).then(setNamespaces).catch(() => setNamespaces([]))
    getGraphDetail(selDataset, selGraph).then(setGraphDetail).catch(() => setGraphDetail(null))
    setSelNs([])  // graph 변경 시 namespace 선택 초기화
  }, [selDataset, selGraph])

  const customNamespaces = namespaces.filter((n) => n.type === 'custom')
  const universalNamespaces = namespaces.filter((n) => n.type === 'universal')

  const shortIRI = (iri: string, max = 30) =>
    iri.length > max ? '…' + iri.slice(-(max - 1)) : iri

  // ── Graph 생성 ──
  const handleCreateGraph = async () => {
    if (!selDataset) return
    try {
      const { iri, label } = await graphForm.validateFields()
      setGraphCreating(true)
      await createGraph(selDataset, iri, label || undefined)
      message.success('Named Graph이 생성되었습니다.')
      setGraphModalOpen(false)
      graphForm.resetFields()
      loadGraphs(selDataset)
      setSelGraph(iri)
    } catch (e: unknown) {
      if ((e as { errorFields?: unknown }).errorFields) return // form validation
      message.error((e as Error).message)
    } finally {
      setGraphCreating(false)
    }
  }

  // ── Graph 수정 ──
  const openEditGraph = () => {
    editGraphForm.setFieldsValue({
      label: graphDetail?.label ?? '',
      comment: graphDetail?.comment ?? '',
    })
    setEditGraphOpen(true)
  }

  const handleEditGraph = async () => {
    if (!selDataset || !selGraph) return
    const values = await editGraphForm.validateFields()
    try {
      const updated = await patchGraph(selDataset, selGraph, {
        label: values.label || undefined,
        comment: values.comment || undefined,
      })
      setGraphDetail(updated)
      setEditGraphOpen(false)
      message.success('Named Graph 정보가 수정되었습니다.')
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  // ── Graph 삭제 ──
  const handleDeleteGraph = async () => {
    if (!selDataset || !selGraph) return
    try {
      await deleteGraph(selDataset, selGraph)
      message.success('Named Graph이 삭제되었습니다.')
      setSelGraph(null)
      setSelNs([])
      loadGraphs(selDataset)
      // 현재 OOI가 이 graph를 쓰고 있었다면 초기화
      if (graph === selGraph) clear()
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  const canApply = !!(selDataset && selGraph && selNs.length > 0)

  return (
    <Space direction="vertical" style={{ width: '100%', padding: '12px 16px' }}>
      {/* 연결 상태 */}
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Space>
          {health === 'checking' && <><LoadingOutlined /><Text type="secondary"> 연결 확인 중…</Text></>}
          {health === 'ok'       && <><CheckCircleOutlined style={{ color: '#52c41a' }} /><Text style={{ color: '#52c41a' }}> Fuseki 연결됨</Text></>}
          {health === 'error'    && <><CloseCircleOutlined style={{ color: '#ff4d4f' }} /><Text type="danger"> 연결 실패</Text></>}
        </Space>
        <Tooltip title="Fuseki 연결 설정">
          <Button
            size="small"
            type="text"
            icon={<SettingOutlined />}
            onClick={() => setConfigModalOpen(true)}
          />
        </Tooltip>
      </Space>

      <Divider style={{ margin: '8px 0' }} />

      {/* Dataset */}
      <div>
        <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 4 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>Dataset</Text>
          <Space size={4}>
            <Tooltip title="Dataset 생성">
              <Button size="small" type="text" icon={<PlusOutlined />}
                onClick={() => { dsForm.resetFields(); setDsModalOpen(true) }} />
            </Tooltip>
            <Tooltip title="선택한 Dataset 삭제">
              <Popconfirm
                title={`Dataset '${selDataset}'과 모든 데이터를 삭제합니다.`}
                onConfirm={handleDeleteDataset}
                okText="삭제" okButtonProps={{ danger: true }}
                disabled={!selDataset}
              >
                <Button size="small" type="text" danger icon={<DeleteOutlined />} disabled={!selDataset} />
              </Popconfirm>
            </Tooltip>
          </Space>
        </Space>
        <Select
          style={{ width: '100%' }}
          placeholder="선택"
          value={selDataset}
          onChange={(v) => { setSelDataset(v); setSelGraph(null); setSelNs([]) }}
          options={datasets.map((d) => ({
            label: <span>{d.name} <Badge status={d.state === 'active' ? 'success' : 'default'} /></span>,
            value: d.name,
          }))}
        />
      </div>

      {/* Graph + 생성/수정/삭제 버튼 */}
      <div>
        <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 4 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>Named Graph</Text>
          <Space size={4}>
            <Tooltip title="Named Graph 생성">
              <Button
                size="small" type="text" icon={<PlusOutlined />}
                disabled={!selDataset}
                onClick={() => { graphForm.resetFields(); setGraphModalOpen(true) }}
              />
            </Tooltip>
            <Tooltip title="Graph 정보 수정">
              <Button
                size="small" type="text" icon={<SettingOutlined />}
                disabled={!selGraph}
                onClick={openEditGraph}
              />
            </Tooltip>
            <Tooltip title="TTL 파일 업로드">
              <Button
                size="small" type="text" icon={<UploadOutlined />}
                disabled={!selGraph}
                onClick={() => {
                  setUploadFile(null)
                  setUploadResult(null)
                  setUploadMode('append')
                  setUploadModalOpen(true)
                }}
              />
            </Tooltip>
            <Tooltip title="선택한 Graph 삭제">
              <Popconfirm
                title="이 Named Graph과 안의 모든 트리플을 삭제합니다."
                onConfirm={handleDeleteGraph}
                okText="삭제" okButtonProps={{ danger: true }}
                disabled={!selGraph}
              >
                <Button
                  size="small" type="text" danger icon={<DeleteOutlined />}
                  disabled={!selGraph}
                />
              </Popconfirm>
            </Tooltip>
          </Space>
        </Space>
        <Select
          style={{ width: '100%' }}
          placeholder={selDataset && graphs.length === 0 ? '없음 — + 로 생성' : '선택'}
          disabled={!selDataset}
          value={selGraph}
          onChange={(v) => { setSelGraph(v); setSelNs([]) }}
          options={graphs.map((g) => ({ label: shortIRI(g), value: g, title: g }))}
        />
        {graphDetail && (
          <div style={{ marginTop: 4 }}>
            {graphDetail.label && (
              <Text type="secondary" style={{ fontSize: 11 }}>
                📌 {graphDetail.label}
              </Text>
            )}
            <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
              트리플 수: {graphDetail.triple_count.toLocaleString()}개
            </Text>
          </div>
        )}
      </div>

      {/* Namespace (복수 선택 + CRUD) */}
      <div>
        <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 4 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>Namespace</Text>
          <Space size={4}>
            {customNamespaces.length > 0 && (
              <Button
                size="small" type="link" style={{ padding: 0, fontSize: 11 }}
                onClick={() => setSelNs(customNamespaces.map((n) => n.base_iri))}
              >
                전체 선택
              </Button>
            )}
            <Tooltip title="Namespace 선언">
              <Button
                size="small" type="text" icon={<PlusOutlined />}
                disabled={!selGraph}
                onClick={() => { nsDeclForm.resetFields(); setNsDeclOpen(true) }}
              />
            </Tooltip>
            <Tooltip title="Universal Namespace import">
              <Button
                size="small" type="text"
                style={{ fontSize: 13 }}
                disabled={!selGraph}
                onClick={handleOpenUniversalNsModal}
              >🌐</Button>
            </Tooltip>
          </Space>
        </Space>
        {selGraph && customNamespaces.length === 0 && (
          <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
            💡 Class/Property를 생성하거나 + 로 직접 선언하세요.
          </Text>
        )}
        {customNamespaces.length > 0 && (
          <div style={{ border: '1px solid #d9d9d9', borderRadius: 4, padding: '6px 8px', maxHeight: 140, overflowY: 'auto' }}>
            {customNamespaces.map((n) => (
              <div key={n.base_iri} style={{ marginBottom: 2, display: 'flex', alignItems: 'center' }}>
                <input
                  type="checkbox"
                  id={`ns-${n.base_iri}`}
                  checked={selNs.includes(n.base_iri)}
                  onChange={(e) => {
                    if (e.target.checked) setSelNs((prev) => [...prev, n.base_iri])
                    else setSelNs((prev) => prev.filter((x) => x !== n.base_iri))
                  }}
                  style={{ marginRight: 6 }}
                />
                <label
                  htmlFor={`ns-${n.base_iri}`}
                  style={{ fontSize: 11, cursor: 'pointer', flex: 1 }}
                  title={n.base_iri}
                >
                  {n.prefix ? `${n.prefix}:` : ''} {shortIRI(n.base_iri, 20)}
                </label>
                <Tooltip title="Namespace 편집">
                  <Button
                    size="small" type="text" icon={<EditOutlined />}
                    style={{ padding: '0 2px', height: 18, fontSize: 10 }}
                    onClick={() => setNsEditTarget(n)}
                  />
                </Tooltip>
              </div>
            ))}
          </div>
        )}
        {universalNamespaces.length > 0 && (
          <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
            Universal: {universalNamespaces.map((n) => n.prefix ?? '?').join(', ')}
          </Text>
        )}
      </div>

      <Button type="primary" block disabled={!canApply} onClick={() => {
        if (canApply) setOOI(selDataset!, selGraph!, selNs)
      }}>
        OOI 설정
      </Button>

      {/* 현재 OOI */}
      {dataset && graph && namespace && (
        <>
          <Divider style={{ margin: '8px 0' }} />
          <Text strong style={{ fontSize: 12 }}>현재 OOI</Text>
          <Descriptions column={1} size="small" style={{ marginTop: 4 }}>
            <Descriptions.Item label="DS">{dataset}</Descriptions.Item>
            <Descriptions.Item label="Graph">
              <span title={graph}>{shortIRI(graph)}</span>
            </Descriptions.Item>
            <Descriptions.Item label="NS">
              <span title={namespace}>{shortIRI(namespace)}</span>
            </Descriptions.Item>
          </Descriptions>
          <Button size="small" danger block onClick={clear}>OOI 초기화</Button>
        </>
      )}

      {health === 'error' && (
        <Alert
          type="error"
          message="Fuseki에 연결할 수 없습니다."
          description={
            <Space direction="vertical" size={4}>
              <span>백엔드 서버 및 Fuseki 컨테이너 상태를 확인하세요.</span>
              <Button size="small" icon={<SettingOutlined />} onClick={() => setConfigModalOpen(true)}>
                연결 설정 변경
              </Button>
            </Space>
          }
          showIcon
        />
      )}

      {/* Named Graph 수정 Modal */}
      <Modal
        title="Named Graph 정보 수정"
        open={editGraphOpen}
        onOk={handleEditGraph}
        onCancel={() => setEditGraphOpen(false)}
        okText="저장"
        destroyOnClose
      >
        <Form form={editGraphForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="label"
            label="Label"
            rules={[{ required: true, message: 'Label을 입력하세요.' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="comment" label="Comment">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      <FusekiConfigModal
        open={configModalOpen}
        onClose={() => setConfigModalOpen(false)}
        onSaved={recheckHealth}
      />

      {/* Dataset 생성 Modal */}
      <Modal
        title="Dataset 생성"
        open={dsModalOpen}
        onOk={handleCreateDataset}
        onCancel={() => setDsModalOpen(false)}
        okText="생성"
        confirmLoading={dsCreating}
        destroyOnClose
      >
        <Form form={dsForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label="Dataset 이름"
            rules={[
              { required: true, message: '이름을 입력하세요.' },
              { pattern: /^[A-Za-z0-9_\-]+$/, message: '영문·숫자·하이픈·밑줄만 허용됩니다.' },
            ]}
          >
            <Input placeholder="예: my-ontology" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Named Graph 생성 Modal */}
      <Modal
        title="Named Graph 생성"
        open={graphModalOpen}
        onOk={handleCreateGraph}
        onCancel={() => setGraphModalOpen(false)}
        okText="생성"
        confirmLoading={graphCreating}
        destroyOnClose
      >
        <Form form={graphForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="iri"
            label="Graph IRI"
            rules={[
              { required: true, message: 'IRI를 입력하세요' },
              { pattern: /^https?:\/\//, message: 'http:// 또는 https:// 로 시작해야 합니다' },
            ]}
          >
            <Input placeholder="예: http://myorg.com/ontology/v1" />
          </Form.Item>
          <Form.Item name="label" label="Label (선택)">
            <Input placeholder="예: My Ontology v1" />
          </Form.Item>
        </Form>
      </Modal>

      {/* v02-C: Namespace 선언 Modal */}
      <Modal
        title="Namespace 선언"
        open={nsDeclOpen}
        onOk={handleDeclareNamespace}
        onCancel={() => setNsDeclOpen(false)}
        okText="선언"
        confirmLoading={nsDeclaring}
        destroyOnClose
      >
        <Form form={nsDeclForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="ns_iri"
            label="Namespace IRI"
            rules={[
              { required: true, message: 'IRI를 입력하세요.' },
              { pattern: /^https?:\/\//, message: 'http:// 또는 https:// 로 시작해야 합니다.' },
            ]}
          >
            <Input placeholder="예: http://myorg.com/ontology/v1#" />
          </Form.Item>
          <Form.Item
            name="prefix"
            label="Prefix"
            rules={[{ required: true, message: 'Prefix를 입력하세요.' }]}
          >
            <Input placeholder="예: myont" />
          </Form.Item>
        </Form>
      </Modal>

      {/* v02-C: Namespace 편집 Modal */}
      {nsEditTarget && selDataset && selGraph && (
        <NamespaceEditModal
          open={!!nsEditTarget}
          dataset={selDataset}
          graph={selGraph}
          ns={nsEditTarget}
          onClose={() => setNsEditTarget(null)}
          onChanged={() => {
            reloadNamespaces()
            setSelNs([])
          }}
        />
      )}

      {/* v03-D: Universal Namespace import Modal */}
      <Modal
        title="🌐 Universal Namespace import"
        open={universalNsModalOpen}
        onCancel={() => setUniversalNsModalOpen(false)}
        footer={null}
        width={480}
        destroyOnClose
      >
        {universalNsList.map((ns) => (
          <div
            key={ns.prefix}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '4px 0',
              borderBottom: '1px solid #f0f0f0',
            }}
          >
            <div>
              <span style={{ fontWeight: 600, minWidth: 70, display: 'inline-block' }}>{ns.prefix}:</span>
              <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#888' }}>{ns.ns_iri}</span>
            </div>
            <Button
              size="small"
              type="primary"
              loading={importingNs === ns.prefix}
              disabled={!selDataset || !selGraph}
              onClick={() => handleImportUniversalNs(ns.prefix)}
            >
              Import
            </Button>
          </div>
        ))}
      </Modal>
      {/* TTL 업로드 Modal */}
      <Modal
        title="📥 TTL 파일 업로드"
        open={uploadModalOpen}
        onCancel={() => setUploadModalOpen(false)}
        onOk={handleUploadTTL}
        okText="업로드"
        okButtonProps={{
          disabled: !uploadFile,
          loading: uploadLoading,
        }}
        cancelText="닫기"
        destroyOnClose
      >
        <Space direction="vertical" style={{ width: '100%', marginTop: 12 }} size="middle">
          {/* 대상 그래프 정보 */}
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>대상 Named Graph</Text>
            <div style={{ marginTop: 4 }}>
              <Text code style={{ fontSize: 11, wordBreak: 'break-all' }}>{selGraph}</Text>
            </div>
          </div>

          {/* 업로드 모드 */}
          <div>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
              업로드 방식
            </Text>
            <Radio.Group
              value={uploadMode}
              onChange={(e) => setUploadMode(e.target.value)}
            >
              <Space direction="vertical" size={4}>
                <Radio value="append">
                  <Text>추가 (Append)</Text>
                  <Text type="secondary" style={{ fontSize: 11, marginLeft: 6 }}>
                    기존 트리플에 새 트리플을 추가합니다
                  </Text>
                </Radio>
                <Radio value="replace">
                  <Text>교체 (Replace)</Text>
                  <Text type="secondary" style={{ fontSize: 11, marginLeft: 6 }}>
                    기존 그래프를 완전히 대체합니다 (주의!)
                  </Text>
                </Radio>
              </Space>
            </Radio.Group>
          </div>

          {/* 파일 선택 */}
          <div>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
              파일 선택 (.ttl, .nt, .n3)
            </Text>
            <input
              ref={fileInputRef}
              type="file"
              accept=".ttl,.nt,.n3,text/turtle,application/n-triples,text/n3"
              style={{ display: 'none' }}
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null
                setUploadFile(f)
                setUploadResult(null)
              }}
            />
            <Space>
              <Button
                icon={<UploadOutlined />}
                onClick={() => fileInputRef.current?.click()}
              >
                파일 선택
              </Button>
              {uploadFile && (
                <Text style={{ fontSize: 12 }}>
                  {uploadFile.name} ({(uploadFile.size / 1024).toFixed(1)} KB)
                </Text>
              )}
            </Space>
          </div>

          {/* 업로드 결과 */}
          {uploadResult && (
            <Alert
              type="success"
              showIcon
              message={uploadResult.message}
              description={
                <Text style={{ fontSize: 11 }}>
                  그래프 총 트리플: {uploadResult.triple_count.toLocaleString()}개
                </Text>
              }
            />
          )}
        </Space>
      </Modal>
    </Space>
  )
}

export default OOINavigator
