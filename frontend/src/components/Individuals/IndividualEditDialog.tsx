import React, { useEffect, useState } from 'react'
import {
  Button, Divider, Form, Input, Modal, Select, Space, Tag, Typography,
} from 'antd'
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { XSD_SHORTTYPES } from '../../types/ontology'
import type {
  DataPropSummary, IndividualDetail, IndividualSummary, ObjPropSummary,
} from '../../types/ontology'

const { Text } = Typography

interface OPUpdate {
  property_iri: string
  target_iri: string
  action: 'add' | 'remove'
}

interface EditValues {
  label: string
  comment?: string
  data_property_updates: { property_iri: string; value: string; datatype: string }[]
  object_property_updates: OPUpdate[]
}

interface Props {
  open: boolean
  detail: IndividualDetail | null
  dataProps: DataPropSummary[]
  objProps: ObjPropSummary[]
  individuals: IndividualSummary[]
  loading: boolean
  onOk: (values: EditValues) => void
  onCancel: () => void
}

const IndividualEditDialog: React.FC<Props> = ({
  open, detail, dataProps, objProps, individuals, loading, onOk, onCancel,
}) => {
  const [form] = Form.useForm()

  // Data Property 수정 행
  const [dpUpdates, setDpUpdates] = useState<
    { property_iri: string; value: string; datatype: string }[]
  >([])

  // Object Property 관계 — 현재 상태 (기존 + 추가 예정 - 삭제 예정)
  const [opCurrent, setOpCurrent] = useState<
    { property_iri: string; target_iri: string; isNew: boolean }[]
  >([])

  // 새로 추가할 OP 입력 행
  const [opAdd, setOpAdd] = useState<{ property_iri: string; target_iri: string }[]>([])

  useEffect(() => {
    if (open && detail) {
      form.setFieldsValue({ label: detail.label ?? '', comment: detail.comment ?? '' })

      // 기존 DP 값 로드 (literal outgoing)
      const existingDp = detail.outgoing
        .filter((o) => o.value_type === 'literal')
        .map((o) => ({ property_iri: o.property, value: o.value, datatype: 'string' }))
      setDpUpdates(existingDp)

      // 기존 OP 관계 로드 (iri outgoing, rdfs/rdf 제외)
      const existingOp = detail.outgoing
        .filter((o) =>
          o.value_type === 'iri' &&
          !o.property.startsWith('http://www.w3.org/2000/01/rdf-schema#') &&
          !o.property.startsWith('http://www.w3.org/2002/07/owl#')
        )
        .map((o) => ({ property_iri: o.property, target_iri: o.value, isNew: false }))
      setOpCurrent(existingOp)
      setOpAdd([])
    }
  }, [open, detail, form])

  const handleOk = () => {
    form.validateFields().then((values) => {
      // 삭제된 기존 관계 (isNew=false인 것 중 현재 목록에 없는 것)
      const originalOps = detail?.outgoing
        .filter((o) =>
          o.value_type === 'iri' &&
          !o.property.startsWith('http://www.w3.org/2000/01/rdf-schema#') &&
          !o.property.startsWith('http://www.w3.org/2002/07/owl#')
        )
        .map((o) => ({ property_iri: o.property, target_iri: o.value })) ?? []

      const currentKeys = new Set(
        opCurrent.filter((x) => !x.isNew).map((x) => `${x.property_iri}::${x.target_iri}`)
      )
      const removes: OPUpdate[] = originalOps
        .filter((o) => !currentKeys.has(`${o.property_iri}::${o.target_iri}`))
        .map((o) => ({ ...o, action: 'remove' as const }))

      const adds: OPUpdate[] = opAdd
        .filter((r) => r.property_iri && r.target_iri)
        .map((r) => ({ ...r, action: 'add' as const }))

      onOk({
        label: values.label,
        comment: values.comment || undefined,
        data_property_updates: dpUpdates.filter((r) => r.property_iri && r.value),
        object_property_updates: [...removes, ...adds],
      })
    })
  }

  const shortIRI = (iri: string) => iri.split(/[#/]/).pop() ?? iri

  const dpOptions = dataProps.map((p) => ({
    label: p.label ?? shortIRI(p.iri), value: p.iri, title: p.iri,
  }))
  const opOptions = objProps.map((p) => ({
    label: p.label ?? shortIRI(p.iri), value: p.iri, title: p.iri,
  }))
  const indOptions = individuals
    .filter((i) => i.iri !== detail?.iri)
    .map((i) => ({
      label: i.label ?? shortIRI(i.iri), value: i.iri, title: i.iri,
    }))

  return (
    <Modal
      title="Individual 수정"
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      okText="저장"
      confirmLoading={loading}
      width={560}
      destroyOnClose
    >
      {/* 기본 정보 */}
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item name="label" label="Label" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="comment" label="Comment">
          <Input.TextArea rows={2} />
        </Form.Item>
      </Form>

      {/* Data Property 수정 */}
      <Divider style={{ margin: '8px 0' }} />
      <Text strong>Data Property 값</Text>
      <Space direction="vertical" style={{ width: '100%', marginTop: 8 }} size={4}>
        {dpUpdates.map((row, i) => (
          <Space key={i} align="start">
            <Select
              style={{ width: 160 }}
              placeholder="Property"
              options={dpOptions}
              value={row.property_iri || undefined}
              onChange={(v) => setDpUpdates((r) => r.map((x, j) => j === i ? { ...x, property_iri: v } : x))}
              showSearch
            />
            <Input
              style={{ width: 110 }}
              placeholder="값"
              value={row.value}
              onChange={(e) => setDpUpdates((r) => r.map((x, j) => j === i ? { ...x, value: e.target.value } : x))}
            />
            <Select
              style={{ width: 95 }}
              options={XSD_SHORTTYPES.map((t) => ({ label: t, value: t }))}
              value={row.datatype || undefined}
              onChange={(v) => setDpUpdates((r) => r.map((x, j) => j === i ? { ...x, datatype: v } : x))}
            />
            <Button type="text" danger icon={<MinusCircleOutlined />}
              onClick={() => setDpUpdates((r) => r.filter((_, j) => j !== i))} />
          </Space>
        ))}
        <Button type="dashed" size="small" icon={<PlusOutlined />}
          onClick={() => setDpUpdates((r) => [...r, { property_iri: '', value: '', datatype: 'string' }])}>
          추가
        </Button>
      </Space>

      {/* Object Property 관계 수정 */}
      <Divider style={{ margin: '8px 0' }} />
      <Text strong>Object Property 관계</Text>

      {/* 기존 관계 목록 (삭제 가능) */}
      <div style={{ marginTop: 8 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>기존 관계 (✕ 클릭 시 삭제)</Text>
        <div style={{ marginTop: 4, minHeight: 24 }}>
          {opCurrent.length === 0
            ? <Text type="secondary" style={{ fontSize: 12 }}>없음</Text>
            : opCurrent.map((row, i) => (
                <Tag
                  key={i}
                  closable
                  onClose={() => setOpCurrent((r) => r.filter((_, j) => j !== i))}
                  style={{ marginBottom: 4 }}
                  title={`${row.property_iri} → ${row.target_iri}`}
                >
                  {shortIRI(row.property_iri)} → {shortIRI(row.target_iri)}
                </Tag>
              ))
          }
        </div>
      </div>

      {/* 새 관계 추가 행 */}
      <div style={{ marginTop: 8 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>관계 추가</Text>
        <Space direction="vertical" style={{ width: '100%', marginTop: 4 }} size={4}>
          {opAdd.map((row, i) => (
            <Space key={i} align="start">
              <Select
                style={{ width: 160 }}
                placeholder="Property"
                options={opOptions}
                value={row.property_iri || undefined}
                onChange={(v) => setOpAdd((r) => r.map((x, j) => j === i ? { ...x, property_iri: v } : x))}
                showSearch
              />
              <Select
                style={{ width: 190 }}
                placeholder="대상 Individual"
                options={indOptions}
                value={row.target_iri || undefined}
                onChange={(v) => setOpAdd((r) => r.map((x, j) => j === i ? { ...x, target_iri: v } : x))}
                showSearch
              />
              <Button type="text" danger icon={<MinusCircleOutlined />}
                onClick={() => setOpAdd((r) => r.filter((_, j) => j !== i))} />
            </Space>
          ))}
          <Button type="dashed" size="small" icon={<PlusOutlined />}
            onClick={() => setOpAdd((r) => [...r, { property_iri: '', target_iri: '' }])}>
            추가
          </Button>
        </Space>
      </div>
    </Modal>
  )
}

export default IndividualEditDialog
