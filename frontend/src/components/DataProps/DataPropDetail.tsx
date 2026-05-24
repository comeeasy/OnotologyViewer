import React from 'react'
import { Descriptions, Drawer, Space, Spin, Tag, Typography } from 'antd'
import type { DataPropDetail as IDataPropDetail } from '../../types/ontology'
import { xsdShortname } from '../../types/ontology'

const { Text } = Typography

interface Props {
  open: boolean
  detail: IDataPropDetail | null
  loading: boolean
  onClose: () => void
}

const DataPropDetail: React.FC<Props> = ({ open, detail, loading, onClose }) => (
  <Drawer title="Data Property 상세" width={440} open={open} onClose={onClose}>
    {loading && <Spin />}
    {!loading && detail && (
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="Label">{detail.label ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="Domain">
            {detail.domain?.split(/[#/]/).pop() ?? '-'}
          </Descriptions.Item>
          <Descriptions.Item label="Range">
            {detail.range ? xsdShortname(detail.range) : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="Functional">
            <Tag color={detail.functional ? 'blue' : 'default'}>
              {detail.functional ? 'Functional' : 'Non-Functional'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="IRI">
            <Text copyable style={{ fontSize: 11, wordBreak: 'break-all' }}>{detail.iri}</Text>
          </Descriptions.Item>
        </Descriptions>
      </Space>
    )}
  </Drawer>
)

export default DataPropDetail
