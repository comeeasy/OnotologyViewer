import React, { useEffect } from 'react'
import { Checkbox, Form, Input, Modal, Select } from 'antd'
import { OBJ_PROP_CHARACTERISTICS } from '../../types/ontology'
import type { ClassSummary, ObjPropDetail } from '../../types/ontology'

interface Props {
  open: boolean
  mode: 'create' | 'edit'
  initial?: ObjPropDetail | null
  classes: ClassSummary[]
  loading: boolean
  onOk: (values: {
    label: string
    domain: string | undefined
    range: string | undefined
    characteristics: string[]
  }) => void
  onCancel: () => void
}

const ObjPropDialog: React.FC<Props> = ({
  open, mode, initial, classes, loading, onOk, onCancel,
}) => {
  const [form] = Form.useForm()

  useEffect(() => {
    if (open) {
      form.setFieldsValue(
        mode === 'edit' && initial
          ? {
              label: initial.label ?? '',
              domain: initial.domain ?? undefined,
              range: initial.range ?? undefined,
              characteristics: initial.characteristics,
            }
          : { label: '', domain: undefined, range: undefined, characteristics: [] },
      )
    }
  }, [open, mode, initial, form])

  const classOptions = classes.map((c) => ({
    label: c.label ?? c.iri.split(/[#/]/).pop(),
    value: c.iri,
    title: c.iri,
  }))

  return (
    <Modal
      title={mode === 'create' ? 'Object Property 생성' : 'Object Property 수정'}
      open={open}
      onOk={() => form.validateFields().then(onOk)}
      onCancel={onCancel}
      okText={mode === 'create' ? '생성' : '저장'}
      confirmLoading={loading}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item name="label" label="Label" rules={[{ required: true }]}>
          <Input placeholder="예: knows" />
        </Form.Item>
        <Form.Item name="domain" label="Domain (Class)" extra="미설정 시 모든 Individual에 적용">
          <Select placeholder="선택 (optional)" options={classOptions} showSearch allowClear />
        </Form.Item>
        <Form.Item name="range" label="Range (Class)" extra="미설정 시 모든 Individual에 적용">
          <Select placeholder="선택 (optional)" options={classOptions} showSearch allowClear />
        </Form.Item>
        <Form.Item name="characteristics" label="Characteristics">
          <Checkbox.Group options={OBJ_PROP_CHARACTERISTICS.map((c) => ({ label: c, value: c }))} />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export default ObjPropDialog
