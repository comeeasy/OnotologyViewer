/**
 * v02-C: Namespace 편집 Modal
 * - Prefix 수정
 * - Base IRI 치환 (with 미리보기)
 * - Namespace 삭제
 */

import React, { useState } from 'react'
import {
  Alert, Button, Divider, Form, Input, Modal, Popconfirm, Space, Typography, message,
} from 'antd'
import {
  updateNsPrefix, previewRenameNs, renameNamespace, deleteNamespace,
} from '../../api/navigator'
import type { Namespace } from '../../types/ontology'

const { Text } = Typography

interface Props {
  open: boolean
  dataset: string
  graph: string
  ns: Namespace
  onClose: () => void
  onChanged: () => void  // 변경 후 namespace 목록 새로고침 요청
}

const NamespaceEditModal: React.FC<Props> = ({
  open, dataset, graph, ns, onClose, onChanged,
}) => {
  const [prefixForm] = Form.useForm()
  const [savingPrefix, setSavingPrefix] = useState(false)

  const [newNsIri, setNewNsIri] = useState('')
  const [previewCount, setPreviewCount] = useState<number | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [renaming, setRenaming] = useState(false)

  const [deleting, setDeleting] = useState(false)

  const handleSavePrefix = async () => {
    const { prefix } = await prefixForm.validateFields()
    setSavingPrefix(true)
    try {
      await updateNsPrefix(dataset, graph, ns.base_iri, prefix.trim())
      message.success('Prefix가 수정되었습니다.')
      onChanged()
      onClose()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setSavingPrefix(false)
    }
  }

  const handlePreview = async () => {
    if (!newNsIri.trim()) { message.warning('새 IRI를 입력하세요.'); return }
    setPreviewing(true)
    try {
      const res = await previewRenameNs(dataset, graph, ns.base_iri, newNsIri.trim())
      setPreviewCount(res.affected_triples)
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setPreviewing(false)
    }
  }

  const handleRename = async () => {
    if (!newNsIri.trim()) return
    setRenaming(true)
    try {
      const res = await renameNamespace(dataset, graph, ns.base_iri, newNsIri.trim())
      message.success(`IRI 치환 완료 — ${res.affected_triples}개 트리플 갱신`)
      onChanged()
      onClose()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setRenaming(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await deleteNamespace(dataset, graph, ns.base_iri)
      message.success('Namespace가 삭제되었습니다.')
      onChanged()
      onClose()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Modal
      title={`Namespace 편집`}
      open={open}
      onCancel={onClose}
      footer={null}
      destroyOnClose
      width={520}
    >
      <Text type="secondary" style={{ fontSize: 11, wordBreak: 'break-all' }}>
        {ns.base_iri}
      </Text>

      {/* ── Prefix 수정 ── */}
      <Divider style={{ fontSize: 12 }}>Prefix 수정</Divider>
      <Form
        form={prefixForm}
        layout="inline"
        initialValues={{ prefix: ns.prefix ?? '' }}
        onFinish={handleSavePrefix}
      >
        <Form.Item
          name="prefix"
          rules={[{ required: true, message: 'Prefix를 입력하세요.' }]}
          style={{ flex: 1 }}
        >
          <Input placeholder="새 prefix (예: myont)" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={savingPrefix}>저장</Button>
        </Form.Item>
      </Form>

      {/* ── IRI 치환 ── */}
      <Divider style={{ fontSize: 12 }}>Base IRI 치환</Divider>
      <Alert
        type="warning"
        showIcon
        message="되돌릴 수 없습니다. 실행 전 그래프 Export(TTL)를 권장합니다."
        style={{ marginBottom: 12 }}
      />
      <Space direction="vertical" style={{ width: '100%' }} size={8}>
        <Input
          placeholder="새 Base IRI (예: http://newdomain.org/onto#)"
          value={newNsIri}
          onChange={(e) => { setNewNsIri(e.target.value); setPreviewCount(null) }}
        />
        <Space>
          <Button
            onClick={handlePreview}
            loading={previewing}
            disabled={!newNsIri.trim()}
          >
            미리보기
          </Button>
          {previewCount !== null && (
            <Text type="secondary">
              {previewCount}개 트리플이 영향받습니다.
            </Text>
          )}
        </Space>
        {previewCount !== null && (
          <Popconfirm
            title={`${previewCount}개 트리플의 IRI를 치환합니다. 계속하시겠습니까?`}
            onConfirm={handleRename}
            okText="치환" okButtonProps={{ danger: true }}
          >
            <Button danger loading={renaming} disabled={!newNsIri.trim()}>
              IRI 치환 실행
            </Button>
          </Popconfirm>
        )}
      </Space>

      {/* ── Namespace 삭제 ── */}
      <Divider style={{ fontSize: 12 }}>Namespace 삭제</Divider>
      <Popconfirm
        title="이 Namespace 선언과 해당 namespace의 모든 트리플을 삭제합니다."
        onConfirm={handleDelete}
        okText="삭제" okButtonProps={{ danger: true }}
      >
        <Button danger loading={deleting} block>
          Namespace 삭제
        </Button>
      </Popconfirm>
    </Modal>
  )
}

export default NamespaceEditModal
