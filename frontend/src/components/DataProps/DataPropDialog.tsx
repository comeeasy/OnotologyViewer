import React, { useEffect } from 'react'
import { Form, Input, Modal, Select, Switch } from 'antd'
import { XSD_SHORTTYPES, xsdShortname } from '../../types/ontology'
import type { ClassSummary, DataPropDetail } from '../../types/ontology'

interface Props {
  open: boolean
  mode: 'create' | 'edit'
  initial?: DataPropDetail | null
  classes: ClassSummary[]
  loading: boolean
  onOk: (values: { label: string; domain: string; range: string; functional: boolean }) => void
  onCancel: () => void
}

const DataPropDialog: React.FC<Props> = ({
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
              range: initial.range ? xsdShortname(initial.range) : undefined,
              functional: initial.functional,
            }
          : { label: '', domain: undefined, range: undefined, functional: false },
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
      title={mode === 'create' ? 'Data Property 생성' : 'Data Property 수정'}
      open={open}
      onOk={() => form.validateFields().then(onOk)}
      onCancel={onCancel}
      okText={mode === 'create' ? '생성' : '저장'}
      confirmLoading={loading}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item name="label" label="Label" rules={[{ required: true }]}>
          <Input placeholder="예: hasAge" />
        </Form.Item>
        <Form.Item name="domain" label="Domain (Class)" rules={[{ required: true }]}>
          <Select placeholder="선택" options={classOptions} showSearch />
        </Form.Item>
        <Form.Item name="range" label="Range (XSD)" rules={[{ required: true }]}>
          <Select
            placeholder="선택"
            options={XSD_SHORTTYPES.map((t) => ({ label: t, value: t }))}
          />
        </Form.Item>
        <Form.Item name="functional" label="Functional" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export default DataPropDialog
