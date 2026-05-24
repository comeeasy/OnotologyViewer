import React, { useEffect } from 'react'
import { Form, Input, Modal } from 'antd'
import type { ClassSummary } from '../../types/ontology'

interface Props {
  open: boolean
  mode: 'create' | 'edit'
  initial?: ClassSummary | null
  loading: boolean
  onOk: (values: { label: string; comment: string }) => void
  onCancel: () => void
}

const ClassDialog: React.FC<Props> = ({ open, mode, initial, loading, onOk, onCancel }) => {
  const [form] = Form.useForm()

  useEffect(() => {
    if (open) {
      form.setFieldsValue(
        mode === 'edit' && initial
          ? { label: initial.label ?? '', comment: initial.comment ?? '' }
          : { label: '', comment: '' },
      )
    }
  }, [open, mode, initial, form])

  const handleOk = () => {
    form.validateFields().then((values) => onOk(values))
  }

  return (
    <Modal
      title={mode === 'create' ? 'Class 생성' : 'Class 수정'}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      okText={mode === 'create' ? '생성' : '저장'}
      confirmLoading={loading}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item
          name="label"
          label="Label"
          rules={[{ required: true, message: 'Label을 입력하세요' }]}
        >
          <Input placeholder="예: Person" />
        </Form.Item>
        <Form.Item
          name="comment"
          label="Comment"
          rules={[{ required: true, message: 'Comment를 입력하세요' }]}
        >
          <Input.TextArea rows={3} placeholder="클래스 설명" />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export default ClassDialog
