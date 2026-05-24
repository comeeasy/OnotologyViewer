import React from 'react'
import { Descriptions, Divider, Drawer, Space, Spin, Table, Tag, Typography } from 'antd'
import type { ClassDetail as IClassDetail } from '../../types/ontology'

const { Text } = Typography

interface Props {
  open: boolean
  detail: IClassDetail | null
  loading: boolean
  onClose: () => void
}

const ClassDetail: React.FC<Props> = ({ open, detail, loading, onClose }) => (
  <Drawer title="Class 상세" width={480} open={open} onClose={onClose}>
    {loading && <Spin />}
    {!loading && detail && (
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
                  <Tag key={iri} title={iri}>{iri.split(/[#/]/).pop()}</Tag>
                ))}
          </div>
        </div>

        <div>
          <Text strong>하위 Class</Text>
          <div style={{ marginTop: 4 }}>
            {detail.sub_classes.length === 0
              ? <Text type="secondary">없음</Text>
              : detail.sub_classes.map((iri) => (
                  <Tag key={iri} title={iri}>{iri.split(/[#/]/).pop()}</Tag>
                ))}
          </div>
        </div>

        <Divider style={{ margin: '4px 0' }} />

        <div>
          <Text strong>Object Properties</Text>
          <Table
            size="small"
            rowKey="iri"
            style={{ marginTop: 4 }}
            pagination={false}
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
            size="small"
            rowKey="iri"
            style={{ marginTop: 4 }}
            pagination={false}
            dataSource={detail.data_properties}
            columns={[
              { title: 'Label', dataIndex: 'label', render: (v) => v ?? '-' },
              { title: 'Range', dataIndex: 'range', render: (v) => v ? v.split('#').pop() : '-' },
            ]}
          />
        </div>
      </Space>
    )}
  </Drawer>
)

export default ClassDetail
