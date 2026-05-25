import React, { useState } from 'react'
import {
  Alert, Button, Descriptions, Divider, Drawer,
  Space, Spin, Table, Tag, Typography, message,
} from 'antd'
import {
  ArrowLeftOutlined,
  CheckCircleOutlined, CloseCircleOutlined,
  SafetyCertificateOutlined, SwapOutlined,
} from '@ant-design/icons'
import type { IndividualDetail as IIndividualDetail } from '../../types/ontology'
import { getIndividual } from '../../api/individuals'
import { validateIndividual } from '../../api/shacl'
import type { ViolationItem } from '../../api/shacl'
import ClassMigrateModal from './ClassMigrateModal'

const { Text } = Typography

interface Props {
  open: boolean
  detail: IIndividualDetail | null
  loading: boolean
  dataset: string
  graph: string
  namespaces: string[]
  onClose: () => void
  onRefresh?: () => void
}

const IndividualDetail: React.FC<Props> = ({
  open, detail: initialDetail, loading, dataset, graph, namespaces, onClose, onRefresh,
}) => {
  const shortIRI = (iri: string) => iri.split(/[#/]/).pop() ?? iri

  // ── 내부 네비게이션 ──────────────────────────────────
  const [navHistory, setNavHistory] = useState<IIndividualDetail[]>([])
  const [navDetail, setNavDetail] = useState<IIndividualDetail | null>(null)
  const [navLoading, setNavLoading] = useState(false)

  // 실제로 표시할 detail: 네비게이션 중이면 navDetail, 아니면 initialDetail
  const detail = navDetail ?? initialDetail

  const handleNavigate = async (iri: string) => {
    if (!dataset || !graph) return
    setNavLoading(true)
    try {
      const d = await getIndividual(dataset, graph, iri)
      setNavHistory((prev) => [...prev, detail!])
      setNavDetail(d)
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setNavLoading(false)
    }
  }

  const handleBack = () => {
    const prev = navHistory[navHistory.length - 1]
    setNavHistory((h) => h.slice(0, -1))
    setNavDetail(prev ?? null)
  }

  const handleClose = () => {
    setNavHistory([])
    setNavDetail(null)
    onClose()
  }

  const [migrateOpen, setMigrateOpen] = useState(false)

  // SHACL 검증
  const [shaclLoading, setShaclLoading] = useState(false)
  const [shaclResult, setShaclResult] = useState<{
    conforms: boolean
    violations: ViolationItem[]
  } | null>(null)

  const handleShaclValidate = async () => {
    if (!detail) return
    setShaclLoading(true)
    setShaclResult(null)
    try {
      const res = await validateIndividual(dataset, graph, detail.iri)
      setShaclResult({ conforms: res.conforms, violations: res.violations ?? [] })
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setShaclLoading(false)
    }
  }

  const isLoading = loading || navLoading

  const drawerTitle = (
    <Space>
      {navHistory.length > 0 && (
        <Button
          size="small"
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={handleBack}
          title="이전 Individual로 돌아가기"
        />
      )}
      <span>Individual 상세</span>
      {navHistory.length > 0 && (
        <Text type="secondary" style={{ fontSize: 11 }}>
          (탐색 depth: {navHistory.length})
        </Text>
      )}
    </Space>
  )

  return (
    <Drawer title={drawerTitle} width={520} open={open} onClose={handleClose}>
      {isLoading && <Spin />}
      {!isLoading && detail && (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="Label">{detail.label ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="Comment">{detail.comment ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="Class">
              <Space>
                <span title={detail.class_iri}>{shortIRI(detail.class_iri)}</span>
                <Button
                  size="small"
                  type="link"
                  icon={<SwapOutlined />}
                  onClick={() => setMigrateOpen(true)}
                  style={{ padding: 0 }}
                >
                  변경
                </Button>
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="IRI">
              <Text copyable style={{ fontSize: 11, wordBreak: 'break-all' }}>{detail.iri}</Text>
            </Descriptions.Item>
          </Descriptions>

          {/* Outgoing 관계 */}
          <div>
            <Text strong>Outgoing 관계 (이 Individual → 대상)</Text>
            <Table
              size="small"
              rowKey={(r) => r.property + r.value}
              style={{ marginTop: 4 }}
              pagination={false}
              dataSource={detail.outgoing}
              columns={[
                {
                  title: 'Property',
                  dataIndex: 'property',
                  ellipsis: true,
                  render: (v: string) => <span title={v}>{shortIRI(v)}</span>,
                },
                {
                  title: 'Value',
                  dataIndex: 'value',
                  ellipsis: true,
                  render: (v: string, row) => {
                    if (row.value_type === 'iri') {
                      const displayLabel = row.value_label ?? shortIRI(v)
                      return (
                        <a
                          title={v}
                          onClick={() => handleNavigate(v)}
                          style={{ cursor: 'pointer' }}
                        >
                          {displayLabel}
                        </a>
                      )
                    }
                    return <Tag>{v}</Tag>
                  },
                },
              ]}
            />
          </div>

          {/* Incoming 관계 */}
          <div>
            <Text strong>Incoming 관계 (다른 Individual → 이 Individual)</Text>
            <Table
              size="small"
              rowKey={(r) => r.subject + r.property}
              style={{ marginTop: 4 }}
              pagination={false}
              dataSource={detail.incoming}
              columns={[
                {
                  title: 'Subject',
                  dataIndex: 'subject',
                  ellipsis: true,
                  render: (v: string, row) => {
                    const displayLabel = row.subject_label ?? shortIRI(v)
                    return (
                      <a
                        title={v}
                        onClick={() => handleNavigate(v)}
                        style={{ cursor: 'pointer' }}
                      >
                        {displayLabel}
                      </a>
                    )
                  },
                },
                {
                  title: 'Property',
                  dataIndex: 'property',
                  ellipsis: true,
                  render: (v: string) => <span title={v}>{shortIRI(v)}</span>,
                },
              ]}
            />
          </div>

          {/* SHACL 검증 */}
          <Divider style={{ margin: '8px 0' }} />
          <div>
            <Space style={{ marginBottom: 8 }}>
              <Text strong>SHACL 검증</Text>
              <Button
                size="small"
                icon={<SafetyCertificateOutlined />}
                loading={shaclLoading}
                onClick={handleShaclValidate}
              >
                검증 실행
              </Button>
            </Space>
            {shaclResult && (
              shaclResult.conforms ? (
                <Alert
                  type="success"
                  showIcon
                  icon={<CheckCircleOutlined />}
                  message="SHACL 검증 통과 — 위반 없음"
                />
              ) : (
                <>
                  <Alert
                    type="error"
                    showIcon
                    icon={<CloseCircleOutlined />}
                    message={`위반 ${shaclResult.violations.length}건 발견`}
                    style={{ marginBottom: 6 }}
                  />
                  {shaclResult.violations.map((v, i) => (
                    <Alert
                      key={i}
                      type="warning"
                      style={{ marginBottom: 4, fontSize: 11 }}
                      message={v.message || '위반'}
                      description={
                        v.result_path
                          ? <Text style={{ fontSize: 11 }} type="secondary">
                              path: {shortIRI(v.result_path)}
                            </Text>
                          : undefined
                      }
                    />
                  ))}
                </>
              )
            )}
          </div>

          {/* v02-E: Class 마이그레이션 Modal */}
          <ClassMigrateModal
            open={migrateOpen}
            dataset={dataset}
            graph={graph}
            namespaces={namespaces}
            individualIri={detail.iri}
            currentClassIri={detail.class_iri}
            onClose={() => setMigrateOpen(false)}
            onMigrated={() => {
              setMigrateOpen(false)
              onRefresh?.()
            }}
          />
        </Space>
      )}
    </Drawer>
  )
}

export default IndividualDetail
