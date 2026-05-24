import React, { useState } from 'react'
import { Button, Form, Input, Modal, Space, Tag, message } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { getFusekiConfig, patchFusekiConfig, testFusekiConnection } from '../../api/config'

interface Props {
  open: boolean
  onClose: () => void
  onSaved: () => void
}

const FusekiConfigModal: React.FC<Props> = ({ open, onClose, onSaved }) => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [testResult, setTestResult] = useState<boolean | null>(null)
  const [testing, setTesting] = useState(false)

  const handleOpen = async () => {
    try {
      const cfg = await getFusekiConfig()
      form.setFieldsValue({
        url: cfg.fuseki_base_url,
        user: cfg.fuseki_admin_user,
        password: '',
      })
    } catch {
      form.setFieldsValue({ url: 'http://localhost:3030', user: 'admin', password: '' })
    }
    setTestResult(null)
  }

  const handleTest = async () => {
    const url = form.getFieldValue('url')?.trim()
    if (!url) { message.warning('URL을 입력하세요.'); return }
    setTesting(true)
    setTestResult(null)
    try {
      const res = await testFusekiConnection(url)
      setTestResult(res.reachable)
    } catch {
      setTestResult(false)
    } finally {
      setTesting(false)
    }
  }

  const handleOk = async () => {
    const values = await form.validateFields()
    setLoading(true)
    try {
      await patchFusekiConfig({
        fuseki_base_url: values.url,
        fuseki_admin_user: values.user || undefined,
        fuseki_admin_password: values.password || undefined,
      })
      message.success('Fuseki 연결 설정이 저장되었습니다.')
      onSaved()
      onClose()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title="Fuseki 연결 설정"
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      okText="저장"
      confirmLoading={loading}
      afterOpenChange={(v) => v && handleOpen()}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item
          name="url"
          label="Fuseki URL"
          rules={[
            { required: true, message: 'URL을 입력하세요.' },
            { pattern: /^https?:\/\//, message: 'http:// 또는 https://로 시작해야 합니다.' },
          ]}
        >
          <Input placeholder="http://localhost:3030" />
        </Form.Item>
        <Form.Item name="user" label="사용자명">
          <Input placeholder="admin" />
        </Form.Item>
        <Form.Item name="password" label="비밀번호">
          <Input.Password placeholder="변경하지 않으려면 비워두세요" />
        </Form.Item>
      </Form>

      <Space>
        <Button loading={testing} onClick={handleTest}>연결 테스트</Button>
        {testResult === true && (
          <Tag icon={<CheckCircleOutlined />} color="success">연결 성공</Tag>
        )}
        {testResult === false && (
          <Tag icon={<CloseCircleOutlined />} color="error">연결 실패</Tag>
        )}
      </Space>
    </Modal>
  )
}

export default FusekiConfigModal
