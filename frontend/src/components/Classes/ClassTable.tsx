import React, { useCallback, useEffect, useState } from 'react'
import { Button, Modal, Radio, Select, Space, Table, Typography, message } from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import { deleteClass, getClass, listClasses, createClass, updateClass } from '../../api/classes'
import { useOOI } from '../../context/OOIContext'
import type { ClassSummary, ClassDetail } from '../../types/ontology'
import ClassDialog from './ClassDialog'
import ClassDetailDrawer from './ClassDetail'

const { Text } = Typography

const ClassTable: React.FC = () => {
  const { dataset, graph, graphs, namespace } = useOOI()

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

  // Delete Modal 상태 (individual 처리 옵션)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ClassSummary | null>(null)
  const [deleteIndividualCount, setDeleteIndividualCount] = useState(0)
  const [onIndividual, setOnIndividual] = useState<'delete' | 'migrate'>('delete')
  const [migrateTarget, setMigrateTarget] = useState<string | undefined>(undefined)
  const [deleteLoading, setDeleteLoading] = useState(false)

  const load = useCallback(async () => {
    if (!dataset || graphs.length === 0 || !namespace) return
    setLoading(true)
    try {
      // 복수 그래프에서 Class 목록 조회
      setRows(await listClasses(dataset, graphs, namespace))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [dataset, graphs, namespace])

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
    const targetGraph = row.source_graph ?? graph
    try {
      const detail = await getClass(dataset, targetGraph, row.iri)
      if (detail.individual_count > 0) {
        // Individual 처리 방법 선택 모달 표시
        setDeleteTarget(row)
        setDeleteIndividualCount(detail.individual_count)
        setOnIndividual('delete')
        setMigrateTarget(undefined)
        setDeleteModalOpen(true)
      } else {
        await doDelete(row.iri, 'delete', undefined)
      }
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  const doDelete = async (iri: string, how: 'delete' | 'migrate', target?: string) => {
    if (!dataset || !graph) return
    setDeleteLoading(true)
    try {
      await deleteClass(dataset, graph, iri, how, target)
      message.success('Class가 삭제되었습니다.')
      setDeleteModalOpen(false)
      load()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDeleteLoading(false)
    }
  }

  // ── Detail Drawer ──
  const openDetail = async (row: ClassSummary) => {
    if (!dataset || !graph) return
    const targetGraph = row.source_graph ?? graph  // 출처 그래프 우선
    setDrawerDetail(null)
    setDrawerOpen(true)
    setDrawerLoading(true)
    try {
      setDrawerDetail(await getClass(dataset, targetGraph, row.iri))
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
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={(e) => { e.stopPropagation(); handleDelete(row) }}
          />
        </Space>
      ),
    },
  ]

  const migrateOptions = rows
    .filter((r) => r.iri !== deleteTarget?.iri)
    .map((r) => ({ label: r.label ?? shortIRI(r.iri), value: r.iri }))

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

      {/* Individual 처리 방법 선택 Modal */}
      <Modal
        title="Class 삭제"
        open={deleteModalOpen}
        onCancel={() => setDeleteModalOpen(false)}
        onOk={() => doDelete(deleteTarget!.iri, onIndividual, migrateTarget)}
        okText="삭제"
        okButtonProps={{ danger: true, disabled: onIndividual === 'migrate' && !migrateTarget, loading: deleteLoading }}
        cancelText="취소"
      >
        <Text>
          소속 Individual이 <Text strong>{deleteIndividualCount}개</Text> 있습니다.
          삭제 전에 처리 방법을 선택하세요.
        </Text>
        <div style={{ marginTop: 16 }}>
          <Radio.Group
            value={onIndividual}
            onChange={(e) => { setOnIndividual(e.target.value); setMigrateTarget(undefined) }}
          >
            <Space direction="vertical">
              <Radio value="delete">Individual 함께 삭제</Radio>
              <Radio value="migrate">다른 Class로 이동</Radio>
            </Space>
          </Radio.Group>
          {onIndividual === 'migrate' && (
            <Select
              style={{ width: '100%', marginTop: 8 }}
              placeholder="이동할 Class 선택"
              options={migrateOptions}
              value={migrateTarget}
              onChange={setMigrateTarget}
              showSearch
              filterOption={(input, opt) =>
                (opt?.label as string ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          )}
        </div>
      </Modal>

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
