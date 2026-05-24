import React, { useState } from 'react'
import { Button, Descriptions, Drawer, Space, Spin, Table, Tag, Typography } from 'antd'
import { SwapOutlined } from '@ant-design/icons'
import type { IndividualDetail as IIndividualDetail } from '../../types/ontology'
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
  open, detail, loading, dataset, graph, namespaces, onClose, onRefresh,
}) => {
  const shortIRI = (iri: string) => iri.split(/[#/]/).pop() ?? iri

  const [migrateOpen, setMigrateOpen] = useState(false)

  return (
    <Drawer title="Individual 상세" width={520} open={open} onClose={onClose}>
      {loading && <Spin />}
      {!loading && detail && (
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
                  render: (v: string, row) =>
                    row.value_type === 'iri'
                      ? <span title={v}>{shortIRI(v)}</span>
                      : <Tag>{v}</Tag>,
                },
              ]}
            />
          </div>

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
                  render: (v: string) => <span title={v}>{shortIRI(v)}</span>,
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
