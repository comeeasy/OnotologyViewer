import React, { useCallback, useEffect, useState } from 'react'
import { Button, Modal, Popconfirm, Space, Table, Typography, message } from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import { deleteClass, getClass, listClasses, createClass, updateClass } from '../../api/classes'
import { useOOI } from '../../context/OOIContext'
import type { ClassSummary, ClassDetail } from '../../types/ontology'
import ClassDialog from './ClassDialog'
import ClassDetailDrawer from './ClassDetail'

const { Text } = Typography

const ClassTable: React.FC = () => {
  const { dataset, graph, namespace } = useOOI()

  const [rows, setRows] = useState<ClassSummary[]>([])
  const [loading, setLoading] = useState(false)

  // Dialog 상태
  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create')
  const [dialogTarget, setDialogTarget] = useState<ClassSummary | null>(null)
  const [dialogLoading, setDialogLoading] = useState(false)

  // Detail Drawer 상태
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerDetail, setDrawerDetail] = useState<ClassDetail | null>(null)
  const [drawerLoading, setDrawerLoading] = useState(false)

  const load = useCallback(async () => {
    if (!dataset || !graph || !namespace) return
    setLoading(true)
    try {
      setRows(await listClasses(dataset, graph, namespace))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [dataset, graph, namespace])

  useEffect(() => { load() }, [load])

  // ── Create ──
  const openCreate = () => {
    setDialogMode('create')
    setDialogTarget(null)
    setDialogOpen(true)
  }

  // ── Edit ──
  const openEdit = (row: ClassSummary) => {
    setDialogMode('edit')
    setDialogTarget(row)
    setDialogOpen(true)
  }

  const handleDialogOk = async (values: { label: string; comment: string }) => {
    if (!dataset || !graph || !namespace) return
    setDialogLoading(true)
    try {
      if (dialogMode === 'create') {
        await createClass(dataset, graph, namespace, values.label, values.comment)
        message.success('Class가 생성되었습니다.')
      } else if (dialogTarget) {
        await updateClass(dataset, graph, dialogTarget.iri, values)
        message.success('Class가 수정되었습니다.')
      }
      setDialogOpen(false)
      load()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDialogLoading(false)
    }
  }

  // ── Delete ──
  const handleDelete = async (row: ClassSummary) => {
    if (!dataset || !graph) return
    // 삭제 전 individual_count 확인
    try {
      const detail = await getClass(dataset, graph, row.iri)
      if (detail.individual_count > 0) {
        Modal.confirm({
          title: 'Class 삭제',
          content: `소속 Individual이 ${detail.individual_count}개 있습니다. 함께 삭제됩니다. 계속하시겠습니까?`,
          okText: '삭제',
          okButtonProps: { danger: true },
          onOk: () => doDelete(row.iri),
        })
      } else {
        await doDelete(row.iri)
      }
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  const doDelete = async (iri: string) => {
    if (!dataset || !graph) return
    try {
      await deleteClass(dataset, graph, iri)
      message.success('Class가 삭제되었습니다.')
      load()
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  // ── Detail Drawer ──
  const openDetail = async (row: ClassSummary) => {
    if (!dataset || !graph) return
    setDrawerDetail(null)
    setDrawerOpen(true)
    setDrawerLoading(true)
    try {
      setDrawerDetail(await getClass(dataset, graph, row.iri))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDrawerLoading(false)
    }
  }

  const refreshDetail = async () => {
    if (!dataset || !graph || !drawerDetail) return
    try {
      setDrawerDetail(await getClass(dataset, graph, drawerDetail.iri))
    } catch { /* 무시 */ }
  }

  const shortIRI = (iri: string) => iri.split(/[#/]/).pop() ?? iri

  const columns = [
    {
      title: 'Name',
      dataIndex: 'label',
      render: (v: string | null, row: ClassSummary) => (
        <a
          onClick={(e) => { e.stopPropagation(); openDetail(row) }}
          style={{ fontWeight: 500 }}
        >
          {v ?? shortIRI(row.iri)}
        </a>
      ),
    },
    {
      title: 'Comment',
      dataIndex: 'comment',
      ellipsis: true,
      render: (v: string | null) => v
        ? <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text>
        : <Text type="secondary">-</Text>,
    },
    {
      title: '작업',
      width: 80,
      render: (_: unknown, row: ClassSummary) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={(e) => { e.stopPropagation(); openEdit(row) }}
          />
          <Popconfirm
            title="삭제하시겠습니까?"
            onConfirm={(e) => { e?.stopPropagation(); handleDelete(row) }}
            onCancel={(e) => e?.stopPropagation()}
            okText="삭제"
            okButtonProps={{ danger: true }}
          >
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={(e) => e.stopPropagation()}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <>
      <div style={{ marginBottom: 12 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          새 Class
        </Button>
      </div>

      <Table
        rowKey="iri"
        size="small"
        loading={loading}
        dataSource={rows}
        columns={columns}
        onRow={(row) => ({ onClick: () => openDetail(row), style: { cursor: 'pointer' } })}
        pagination={{ pageSize: 20, showSizeChanger: false }}
      />

      <ClassDialog
        open={dialogOpen}
        mode={dialogMode}
        initial={dialogTarget}
        loading={dialogLoading}
        onOk={handleDialogOk}
        onCancel={() => setDialogOpen(false)}
      />

      <ClassDetailDrawer
        open={drawerOpen}
        detail={drawerDetail}
        loading={drawerLoading}
        allClasses={rows}
        onClose={() => setDrawerOpen(false)}
        onRefresh={refreshDetail}
      />
    </>
  )
}

export default ClassTable
