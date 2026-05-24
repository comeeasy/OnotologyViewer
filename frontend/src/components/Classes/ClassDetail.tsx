import React, { useState } from 'react'
import {
  Button, Descriptions, Divider, Drawer, Popconfirm, Select,
  Space, Spin, Table, Tabs, Tag, Typography, message,
} from 'antd'
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import type { ClassDetail as IClassDetail, ClassSummary } from '../../types/ontology'
import { addSuperClass, removeSuperClass } from '../../api/classes'
import { useOOI } from '../../context/OOIContext'

const { Text } = Typography

interface Props {
  open: boolean
  detail: IClassDetail | null
  loading: boolean
  allClasses: ClassSummary[]   // 같은 graph의 전체 Class 목록 (상위 class 선택용)
  onClose: () => void
  onRefresh: () => void        // 계층 편집 후 부모에게 reload 요청
}

const ClassDetailDrawer: React.FC<Props> = ({
  open, detail, loading, allClasses, onClose, onRefresh,
}) => {
  const { dataset, graph } = useOOI()
  const [selParent, setSelParent] = useState<string | undefined>(undefined)
  const [adding, setAdding] = useState(false)

  const shortIRI = (iri: string) => iri.split(/[#/]/).pop() ?? iri

  const handleAddSuper = async () => {
    if (!dataset || !graph || !detail || !selParent) return
    setAdding(true)
    try {
      await addSuperClass(dataset, graph, detail.iri, selParent)
      message.success('상위 Class가 추가되었습니다.')
      setSelParent(undefined)
      onRefresh()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setAdding(false)
    }
  }

  const handleRemoveSuper = async (parentIri: string) => {
    if (!dataset || !graph || !detail) return
    try {
      await removeSuperClass(dataset, graph, detail.iri, parentIri)
      message.success('상위 Class 관계가 삭제되었습니다.')
      onRefresh()
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  const parentOptions = allClasses
    .filter((c) => c.iri !== detail?.iri && !(detail?.super_classes ?? []).includes(c.iri))
    .map((c) => ({ label: c.label ?? shortIRI(c.iri), value: c.iri, title: c.iri }))

  const infoTab = detail && (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="Label">{detail.label ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="Comment">{detail.comment ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="IRI">
          <Text copyable style={{ fontSize: 11, wordBreak: 'break-all' }}>{detail.iri}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Individuals">{detail.individual_count}</Descriptions.Item>
      </Descriptions>

      <div>
        <Text strong>상위 Class</Text>
        <div style={{ marginTop: 4 }}>
          {detail.super_classes.length === 0
            ? <Text type="secondary">없음</Text>
            : detail.super_classes.map((iri) => (
                <Tag key={iri} title={iri}>{shortIRI(iri)}</Tag>
              ))}
        </div>
      </div>

      <div>
        <Text strong>하위 Class</Text>
        <div style={{ marginTop: 4 }}>
          {detail.sub_classes.length === 0
            ? <Text type="secondary">없음</Text>
            : detail.sub_classes.map((iri) => (
                <Tag key={iri} title={iri}>{shortIRI(iri)}</Tag>
              ))}
        </div>
      </div>

      <Divider style={{ margin: '4px 0' }} />

      <div>
        <Text strong>Object Properties</Text>
        <Table
          size="small" rowKey="iri" style={{ marginTop: 4 }} pagination={false}
          dataSource={detail.object_properties}
          columns={[
            { title: 'Label', dataIndex: 'label', render: (v) => v ?? '-' },
            { title: 'Role', dataIndex: 'role', render: (v) => <Tag>{v}</Tag> },
          ]}
        />
      </div>

      <div>
        <Text strong>Data Properties</Text>
        <Table
          size="small" rowKey="iri" style={{ marginTop: 4 }} pagination={false}
          dataSource={detail.data_properties}
          columns={[
            { title: 'Label', dataIndex: 'label', render: (v) => v ?? '-' },
            { title: 'Range', dataIndex: 'range', render: (v) => v ? v.split('#').pop() : '-' },
          ]}
        />
      </div>
    </Space>
  )

  const hierarchyTab = detail && (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {/* 현재 상위 Class (삭제 가능) */}
      <div>
        <Text strong>현재 상위 Class</Text>
        <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
          (클릭하면 관계 삭제)
        </Text>
        <div style={{ marginTop: 8, minHeight: 24 }}>
          {detail.super_classes.length === 0
            ? <Text type="secondary" style={{ fontSize: 12 }}>설정된 상위 Class 없음</Text>
            : detail.super_classes.map((iri) => (
                <Popconfirm
                  key={iri}
                  title={`상위 Class 관계를 삭제합니까?\n${shortIRI(iri)}`}
                  onConfirm={() => handleRemoveSuper(iri)}
                  okText="삭제" okButtonProps={{ danger: true }}
                >
                  <Tag
                    icon={<MinusCircleOutlined />}
                    color="geekblue"
                    style={{ cursor: 'pointer', marginBottom: 4 }}
                    title={iri}
                  >
                    {shortIRI(iri)}
                  </Tag>
                </Popconfirm>
              ))
          }
        </div>
      </div>

      {/* 상위 Class 추가 */}
      <div>
        <Text strong>상위 Class 추가</Text>
        <Space style={{ marginTop: 8 }}>
          <Select
            style={{ width: 220 }}
            placeholder="상위 Class 선택"
            options={parentOptions}
            value={selParent}
            onChange={setSelParent}
            showSearch
            size="small"
          />
          <Button
            size="small" type="dashed" icon={<PlusOutlined />}
            loading={adding} disabled={!selParent}
            onClick={handleAddSuper}
          >
            추가
          </Button>
        </Space>
        {parentOptions.length === 0 && (
          <div style={{ marginTop: 4 }}>
            <Text type="secondary" style={{ fontSize: 11 }}>
              추가 가능한 상위 Class 없음 (모두 연결됨 또는 없음)
            </Text>
          </div>
        )}
      </div>

      <Divider style={{ margin: '4px 0' }} />

      {/* 현재 하위 Class (읽기 전용 — 하위에서 관리) */}
      <div>
        <Text strong>하위 Class</Text>
        <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
          (하위 Class에서 직접 편집)
        </Text>
        <div style={{ marginTop: 8 }}>
          {detail.sub_classes.length === 0
            ? <Text type="secondary" style={{ fontSize: 12 }}>없음</Text>
            : detail.sub_classes.map((iri) => (
                <Tag key={iri} color="cyan" title={iri} style={{ marginBottom: 4 }}>
                  {shortIRI(iri)}
                </Tag>
              ))
          }
        </div>
      </div>
    </Space>
  )

  return (
    <Drawer title="Class 상세" width={500} open={open} onClose={onClose}>
      {loading && <Spin />}
      {!loading && detail && (
        <Tabs
          items={[
            { key: 'info', label: '정보', children: infoTab },
            { key: 'hierarchy', label: '계층 편집', children: hierarchyTab },
          ]}
        />
      )}
    </Drawer>
  )
}

export default ClassDetailDrawer
