import React from 'react'
import { Descriptions, Drawer, Space, Spin, Tag, Typography } from 'antd'
import type { ObjPropDetail as IObjPropDetail } from '../../types/ontology'

const { Text } = Typography

interface Props {
  open: boolean
  detail: IObjPropDetail | null
  loading: boolean
  onClose: () => void
}

const ObjPropDetail: React.FC<Props> = ({ open, detail, loading, onClose }) => (
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
        <div>
          <Text strong>Characteristics</Text>
          <div style={{ marginTop: 6 }}>
            {detail.characteristics.length === 0
              ? <Text type="secondary">없음</Text>
              : detail.characteristics.map((c) => <Tag key={c} color="blue">{c}</Tag>)}
          </div>
        </div>
      </Space>
    )}
  </Drawer>
)

export default ObjPropDetail
