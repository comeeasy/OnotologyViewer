import React, { useEffect, useState } from 'react'
import {
  Alert, Badge, Button, Descriptions, Divider, Form, Input,
  Modal, Popconfirm, Select, Space, Tooltip, Typography, message,
} from 'antd'
import {
  CheckCircleOutlined, CloseCircleOutlined,
  DeleteOutlined, LoadingOutlined, PlusOutlined,
} from '@ant-design/icons'
import {
  checkHealth, createGraph, deleteGraph,
  getDatasets, getGraphs, getNamespacesInGraph,
} from '../../api/navigator'
import { useOOI } from '../../context/OOIContext'
import type { Dataset, Namespace } from '../../types/ontology'

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
  const [selNs, setSelNs] = useState<string | null>(null)

  // Graph 생성 Modal
  const [graphModalOpen, setGraphModalOpen] = useState(false)
  const [graphForm] = Form.useForm()
  const [graphCreating, setGraphCreating] = useState(false)

  // ── 초기 health + datasets ──
  useEffect(() => {
    checkHealth()
      .then(() => setHealth('ok'))
      .catch(() => setHealth('error'))
    getDatasets().then(setDatasets).catch(() => {})
  }, [])

  // ── dataset 선택 시 graphs 로드 ──
  const loadGraphs = (ds: string) => {
    getGraphs(ds).then(setGraphs).catch(() => setGraphs([]))
  }

  useEffect(() => {
    if (!selDataset) { setGraphs([]); setSelGraph(null); return }
    loadGraphs(selDataset)
  }, [selDataset])

  // ── graph 선택 시 namespaces 로드 ──
  useEffect(() => {
    if (!selDataset || !selGraph) { setNamespaces([]); setSelNs(null); return }
    getNamespacesInGraph(selDataset, selGraph)
      .then(setNamespaces)
      .catch(() => setNamespaces([]))
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

  // ── Graph 삭제 ──
  const handleDeleteGraph = async () => {
    if (!selDataset || !selGraph) return
    try {
      await deleteGraph(selDataset, selGraph)
      message.success('Named Graph이 삭제되었습니다.')
      setSelGraph(null)
      setSelNs(null)
      loadGraphs(selDataset)
      // 현재 OOI가 이 graph를 쓰고 있었다면 초기화
      if (graph === selGraph) clear()
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  const canApply = !!(selDataset && selGraph && selNs)

  return (
    <Space direction="vertical" style={{ width: '100%', padding: '12px 16px' }}>
      {/* 연결 상태 */}
      <Space>
        {health === 'checking' && <><LoadingOutlined /><Text type="secondary"> 연결 확인 중…</Text></>}
        {health === 'ok'       && <><CheckCircleOutlined style={{ color: '#52c41a' }} /><Text style={{ color: '#52c41a' }}> Fuseki 연결됨</Text></>}
        {health === 'error'    && <><CloseCircleOutlined style={{ color: '#ff4d4f' }} /><Text type="danger"> 연결 실패</Text></>}
      </Space>

      <Divider style={{ margin: '8px 0' }} />

      {/* Dataset */}
      <div>
        <Text type="secondary" style={{ fontSize: 12 }}>Dataset</Text>
        <Select
          style={{ width: '100%', marginTop: 4 }}
          placeholder="선택"
          value={selDataset}
          onChange={(v) => { setSelDataset(v); setSelGraph(null); setSelNs(null) }}
          options={datasets.map((d) => ({
            label: <span>{d.name} <Badge status={d.state === 'active' ? 'success' : 'default'} /></span>,
            value: d.name,
          }))}
        />
      </div>

      {/* Graph + 생성/삭제 버튼 */}
      <div>
        <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 4 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>Named Graph</Text>
          <Space size={4}>
            <Tooltip title="Named Graph 생성">
              <Button
                size="small"
                type="text"
                icon={<PlusOutlined />}
                disabled={!selDataset}
                onClick={() => { graphForm.resetFields(); setGraphModalOpen(true) }}
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
                  size="small"
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
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
          onChange={(v) => { setSelGraph(v); setSelNs(null) }}
          options={graphs.map((g) => ({ label: shortIRI(g), value: g, title: g }))}
        />
      </div>

      {/* Namespace */}
      <div>
        <Text type="secondary" style={{ fontSize: 12 }}>Namespace (Custom)</Text>
        <Select
          style={{ width: '100%', marginTop: 4 }}
          placeholder={selGraph && customNamespaces.length === 0 ? '없음 — Class 생성 시 자동 등록' : '선택'}
          disabled={!selGraph || customNamespaces.length === 0}
          value={selNs}
          onChange={setSelNs}
          options={customNamespaces.map((n) => ({
            label: n.prefix ? `${n.prefix}: ${shortIRI(n.base_iri, 20)}` : shortIRI(n.base_iri),
            value: n.base_iri,
            title: n.base_iri,
          }))}
        />
        {selGraph && customNamespaces.length === 0 && (
          <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
            💡 Class/Property를 생성하면 Namespace가 등록됩니다.
          </Text>
        )}
        {universalNamespaces.length > 0 && (
          <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
            Universal: {universalNamespaces.map((n) => n.prefix ?? '?').join(', ')}
          </Text>
        )}
      </div>

      <Button type="primary" block disabled={!canApply} onClick={() => {
        if (canApply) setOOI(selDataset!, selGraph!, selNs!)
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
          description="백엔드 서버 및 Fuseki 컨테이너 상태를 확인하세요."
          showIcon
        />
      )}

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
    </Space>
  )
}

export default OOINavigator
