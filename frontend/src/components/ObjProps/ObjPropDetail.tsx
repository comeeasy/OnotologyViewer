import React, { useState } from 'react'
import {
  Button, Descriptions, Drawer, Popconfirm, Select, Space, Spin, Tag, Typography, message,
} from 'antd'
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import type { ObjPropDetail as IObjPropDetail, ObjPropSummary } from '../../types/ontology'
import { addInverseOf, removeInverseOf } from '../../api/objProps'
import { useOOI } from '../../context/OOIContext'

const { Text } = Typography

interface Props {
  open: boolean
  detail: IObjPropDetail | null
  loading: boolean
  allProps: ObjPropSummary[]      // 같은 graph의 전체 ObjProp 목록 (역관계 선택용)
  onClose: () => void
  onRefresh: () => void           // inverseOf 추가/삭제 후 부모에게 reload 요청
}

const ObjPropDetail: React.FC<Props> = ({
  open, detail, loading, allProps, onClose, onRefresh,
}) => {
  const { dataset, graph } = useOOI()
  const [selInv, setSelInv] = useState<string | undefined>(undefined)
  const [addingInv, setAddingInv] = useState(false)

  const shortIRI = (iri: string) => iri.split(/[#/]/).pop() ?? iri

  const handleAddInverse = async () => {
    if (!dataset || !graph || !detail || !selInv) return
    setAddingInv(true)
    try {
      await addInverseOf(dataset, graph, detail.iri, selInv)
      message.success('inverseOf 관계가 추가되었습니다.')
      setSelInv(undefined)
      onRefresh()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setAddingInv(false)
    }
  }

  const handleRemoveInverse = async (invIri: string) => {
    if (!dataset || !graph || !detail) return
    try {
      await removeInverseOf(dataset, graph, detail.iri, invIri)
      message.success('inverseOf 관계가 삭제되었습니다.')
      onRefresh()
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  const candidateOptions = allProps
    .filter((p) => p.iri !== detail?.iri && !(detail?.inverse_of ?? []).includes(p.iri))
    .map((p) => ({ label: p.label ?? shortIRI(p.iri), value: p.iri, title: p.iri }))

  return (
    <Drawer title="Object Property 상세" width={440} open={open} onClose={onClose}>
      {loading && <Spin />}
      {!loading && detail && (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="Label">{detail.label ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="Domain">
              <span title={detail.domain ?? ''}>{detail.domain?.split(/[#/]/).pop() ?? '-'}</span>
            </Descriptions.Item>
            <Descriptions.Item label="Range">
              <span title={detail.range ?? ''}>{detail.range?.split(/[#/]/).pop() ?? '-'}</span>
            </Descriptions.Item>
            <Descriptions.Item label="IRI">
              <Text copyable style={{ fontSize: 11, wordBreak: 'break-all' }}>{detail.iri}</Text>
            </Descriptions.Item>
          </Descriptions>

          {/* Characteristics */}
          <div>
            <Text strong>Characteristics</Text>
            <div style={{ marginTop: 6 }}>
              {detail.characteristics.length === 0
                ? <Text type="secondary">없음</Text>
                : detail.characteristics.map((c) => <Tag key={c} color="blue">{c}</Tag>)}
            </div>
          </div>

          {/* inverseOf */}
          <div>
            <Text strong>inverseOf</Text>
            <div style={{ marginTop: 6, marginBottom: 8 }}>
              {(detail.inverse_of ?? []).length === 0
                ? <Text type="secondary" style={{ fontSize: 12 }}>설정된 역관계 없음</Text>
                : (detail.inverse_of ?? []).map((iri) => (
                    <Popconfirm
                      key={iri}
                      title="이 inverseOf 관계를 삭제합니까?"
                      onConfirm={() => handleRemoveInverse(iri)}
                      okText="삭제" okButtonProps={{ danger: true }}
                    >
                      <Tag
                        icon={<MinusCircleOutlined />}
                        color="purple"
                        style={{ cursor: 'pointer', marginBottom: 4 }}
                        title={iri}
                      >
                        {shortIRI(iri)}
                      </Tag>
                    </Popconfirm>
                  ))
              }
            </div>
            {candidateOptions.length > 0 && (
              <Space>
                <Select
                  style={{ width: 200 }}
                  placeholder="역관계 Property 선택"
                  options={candidateOptions}
                  value={selInv}
                  onChange={setSelInv}
                  showSearch
                  size="small"
                />
                <Button
                  size="small"
                  type="dashed"
                  icon={<PlusOutlined />}
                  loading={addingInv}
                  disabled={!selInv}
                  onClick={handleAddInverse}
                >
                  추가
                </Button>
              </Space>
            )}
          </div>
        </Space>
      )}
    </Drawer>
  )
}

export default ObjPropDetail
