import React from 'react'
import { Descriptions, Drawer, Space, Spin, Table, Tag, Typography } from 'antd'
import type { IndividualDetail as IIndividualDetail } from '../../types/ontology'

const { Text } = Typography

interface Props {
  open: boolean
  detail: IIndividualDetail | null
  loading: boolean
  onClose: () => void
}

const IndividualDetail: React.FC<Props> = ({ open, detail, loading, onClose }) => {
  const shortIRI = (iri: string) => iri.split(/[#/]/).pop() ?? iri

  return (
    <Drawer title="Individual 상세" width={520} open={open} onClose={onClose}>
      {loading && <Spin />}
      {!loading && detail && (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="Label">{detail.label ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="Comment">{detail.comment ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="Class">
              <span title={detail.class_iri}>{shortIRI(detail.class_iri)}</span>
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
        </Space>
      )}
    </Drawer>
  )
}

export default IndividualDetail
