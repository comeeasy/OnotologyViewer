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
import type { ClassSummary, ClassDetail as IClassDetail, DataPropSummary, IndividualDetail as IIndividualDetail, ObjPropSummary } from '../../types/ontology'
import { getIndividual } from '../../api/individuals'
import { getClass } from '../../api/classes'
import { validateIndividual } from '../../api/shacl'
import type { ViolationItem } from '../../api/shacl'
import ClassMigrateModal from './ClassMigrateModal'
import ClassDetailDrawer from '../Classes/ClassDetail'

const { Text } = Typography

interface Props {
  open: boolean
  detail: IIndividualDetail | null
  loading: boolean
  dataset: string
  graph: string
  namespaces: string[]
  allClasses?: ClassSummary[]         // 클래스 label 조회용
  allDataProps?: DataPropSummary[]    // Data Property label 조회용
  allObjProps?: ObjPropSummary[]      // Object Property label 조회용
  onClose: () => void
  onRefresh?: () => void
}

const IndividualDetail: React.FC<Props> = ({
  open, detail: initialDetail, loading, dataset, graph, namespaces,
  allClasses = [], allDataProps = [], allObjProps = [], onClose, onRefresh,
}) => {
  const shortIRI = (iri: string) => iri.split(/[#/]/).pop() ?? iri
  const classLabel = (iri: string) => allClasses.find((c) => c.iri === iri)?.label ?? shortIRI(iri)
  const dpLabel = (iri: string) => allDataProps.find((p) => p.iri === iri)?.label ?? shortIRI(iri)
  const opLabel = (iri: string) => allObjProps.find((p) => p.iri === iri)?.label ?? shortIRI(iri)

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

  // ── 내부 Class 상세 드로어 ─────────────────────────────────────────────
  const [classDrawerOpen, setClassDrawerOpen]   = useState(false)
  const [classDetail, setClassDetail]           = useState<IClassDetail | null>(null)
  const [classDetailLoading, setClassDetailLoading] = useState(false)

  const handleClassClick = async (classIri: string) => {
    if (!dataset || !graph) return
    setClassDrawerOpen(true)
    setClassDetailLoading(true)
    setClassDetail(null)
    try {
      setClassDetail(await getClass(dataset, graph, classIri))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setClassDetailLoading(false)
    }
  }

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

  // ── 관계 분류 ──────────────────────────────────────────
  const SKIP_DP_PROPS = new Set([
    'http://www.w3.org/2000/01/rdf-schema#label',
    'http://www.w3.org/2000/01/rdf-schema#comment',
  ])
  const dataProps = (detail?.outgoing ?? []).filter(
    (o) => o.value_type === 'literal' && !SKIP_DP_PROPS.has(o.property),
  )
  const objPropsOut = (detail?.outgoing ?? []).filter((o) => o.value_type === 'iri')

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
    <>
    <Drawer title={drawerTitle} width={520} open={open} onClose={handleClose}>
      {isLoading && <Spin />}
      {!isLoading && detail && (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="Label">{detail.label ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="Comment">{detail.comment ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="Class">
              <Space>
                <a
                  title={detail.class_iri}
                  onClick={() => handleClassClick(detail.class_iri)}
                  style={{ cursor: 'pointer' }}
                >
                  {classLabel(detail.class_iri)}
                </a>
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

          {/* Data Properties */}
          {dataProps.length > 0 && (
            <div>
              <Text strong>Data Properties</Text>
              <Table
                size="small"
                rowKey={(r) => r.property}
                style={{ marginTop: 4 }}
                pagination={false}
                dataSource={dataProps}
                columns={[
                  {
                    title: 'Property',
                    dataIndex: 'property',
                    width: '40%',
                    ellipsis: true,
                    render: (v: string) => <span title={v}>{dpLabel(v)}</span>,
                  },
                  {
                    title: 'Value',
                    dataIndex: 'value',
                    ellipsis: true,
                    render: (v: string, row) => (
                      <Tag color="default" style={{ fontFamily: 'monospace', fontSize: 11 }}>
                        {v}{row.datatype && row.datatype !== 'string'
                          ? <Text type="secondary" style={{ fontSize: 10 }}> ({row.datatype})</Text>
                          : null}
                      </Tag>
                    ),
                  },
                ]}
              />
            </div>
          )}

          {/* Object Properties (Outgoing IRI) */}
          <div>
            <Text strong>Object Properties (이 Individual → 대상)</Text>
            <Table
              size="small"
              rowKey={(r) => r.property + r.value}
              style={{ marginTop: 4 }}
              pagination={false}
              dataSource={objPropsOut}
              locale={{ emptyText: '연결된 Object Property 없음' }}
              columns={[
                {
                  title: 'Property',
                  dataIndex: 'property',
                  width: '40%',
                  ellipsis: true,
                  render: (v: string) => <span title={v}>{opLabel(v)}</span>,
                },
                {
                  title: 'Value (Individual)',
                  dataIndex: 'value',
                  ellipsis: true,
                  render: (v: string, row) => {
                    const displayLabel = row.value_label ?? shortIRI(v)
                    return (
                      <a title={v} onClick={() => handleNavigate(v)} style={{ cursor: 'pointer' }}>
                        {displayLabel}
                      </a>
                    )
                  },
                },
              ]}
            />
          </div>

          {/* Incoming Object Properties */}
          <div>
            <Text strong>Incoming (다른 Individual → 이 Individual)</Text>
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
                  render: (v: string) => <span title={v}>{opLabel(v)}</span>,
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
            allClasses={allClasses}
            allDataProps={allDataProps}
            allObjProps={allObjProps}
            onClose={() => setMigrateOpen(false)}
            onMigrated={() => {
              setMigrateOpen(false)
              onRefresh?.()
            }}
          />
        </Space>
      )}
    </Drawer>

    {/* ── 내부 Class 상세 드로어 (개별 클래스 클릭 시) ─────────────────── */}
    <ClassDetailDrawer
      open={classDrawerOpen}
      detail={classDetail}
      loading={classDetailLoading}
      allClasses={allClasses}
      onClose={() => setClassDrawerOpen(false)}
      onRefresh={() => {}}
    />
    </>
  )
}

export default IndividualDetail
