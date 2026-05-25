import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  Button, Modal, Radio, Select, Space, Table, Typography,
  Segmented, message,
} from 'antd'
import {
  DeleteOutlined, EditOutlined, PlusOutlined,
  UnorderedListOutlined, ApartmentOutlined,
} from '@ant-design/icons'
import {
  deleteClass, getClass, listClasses, createClass, updateClass,
  listClassHierarchy,
} from '../../api/classes'
import type { ClassHierarchyItem } from '../../api/classes'
import { useOOI } from '../../context/OOIContext'
import type { ClassSummary, ClassDetail } from '../../types/ontology'
import ClassDialog from './ClassDialog'
import ClassDetailDrawer from './ClassDetail'
import ClassHierarchyTree from './ClassHierarchyTree'

const { Text } = Typography

const ClassTable: React.FC = () => {
  const { dataset, graph, graphs, namespace } = useOOI()

  const [rows, setRows] = useState<ClassSummary[]>([])
  const [loading, setLoading] = useState(false)

  // ── 뷰 모드 ─────────────────────────────────────────────────────────────
  const [viewMode, setViewMode] = useState<'table' | 'tree'>('table')
  const [hierarchyItems, setHierarchyItems] = useState<ClassHierarchyItem[]>([])
  const [hierarchyLoading, setHierarchyLoading] = useState(false)

  // Dialog 상태
  const [dialogOpen, setDialogOpen]   = useState(false)
  const [dialogMode, setDialogMode]   = useState<'create' | 'edit'>('create')
  const [dialogTarget, setDialogTarget] = useState<ClassSummary | null>(null)
  const [dialogLoading, setDialogLoading] = useState(false)
  // 트리에서 "자식 추가" 클릭 시 미리 지정할 부모 IRI
  const pendingParentRef = useRef<string | null>(null)

  // Detail Drawer 상태
  const [drawerOpen, setDrawerOpen]     = useState(false)
  const [drawerDetail, setDrawerDetail] = useState<ClassDetail | null>(null)
  const [drawerLoading, setDrawerLoading] = useState(false)

  // Delete Modal 상태
  const [deleteModalOpen, setDeleteModalOpen]       = useState(false)
  const [deleteTarget, setDeleteTarget]             = useState<ClassSummary | null>(null)
  const [deleteIndividualCount, setDeleteIndividualCount] = useState(0)
  const [onIndividual, setOnIndividual]             = useState<'delete' | 'migrate'>('delete')
  const [migrateTarget, setMigrateTarget]           = useState<string | undefined>(undefined)
  const [deleteLoading, setDeleteLoading]           = useState(false)

  // ── 데이터 로드 ─────────────────────────────────────────────────────────
  const load = useCallback(async () => {
    if (!dataset || graphs.length === 0 || !namespace) return
    setLoading(true)
    try {
      setRows(await listClasses(dataset, graphs, namespace))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [dataset, graphs, namespace])

  const loadHierarchy = useCallback(async () => {
    if (!dataset || graphs.length === 0 || !namespace) return
    setHierarchyLoading(true)
    try {
      setHierarchyItems(await listClassHierarchy(dataset, graphs, namespace))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setHierarchyLoading(false)
    }
  }, [dataset, graphs, namespace])

  useEffect(() => { load() }, [load])

  // 트리 뷰로 전환할 때 계층 데이터 로드
  useEffect(() => {
    if (viewMode === 'tree') loadHierarchy()
  }, [viewMode, loadHierarchy])

  const refreshAll = () => {
    load()
    if (viewMode === 'tree') loadHierarchy()
  }

  // ── label 조회용 Map (트리에서 IRI → label 변환) ─────────────────────────
  const classMap = React.useMemo(
    () => new Map(rows.map((r) => [r.iri, r])),
    [rows],
  )

  // ── Create ──────────────────────────────────────────────────────────────
  const openCreate = (parentIri?: string) => {
    pendingParentRef.current = parentIri ?? null
    setDialogMode('create')
    setDialogTarget(null)
    setDialogOpen(true)
  }

  // ── Edit ────────────────────────────────────────────────────────────────
  const openEdit = (iri: string) => {
    const row = rows.find((r) => r.iri === iri)
    if (!row) return
    setDialogMode('edit')
    setDialogTarget(row)
    setDialogOpen(true)
  }

  const handleDialogOk = async (values: { label: string; comment: string }) => {
    if (!dataset || !graph || !namespace) return
    setDialogLoading(true)
    try {
      if (dialogMode === 'create') {
        const newIri = await createClass(dataset, graph, namespace, values.label, values.comment)
        // 자식 추가 모드: 새 클래스를 부모 아래 연결
        if (pendingParentRef.current) {
          const { addSuperClass } = await import('../../api/classes')
          await addSuperClass(dataset, graph, newIri, pendingParentRef.current)
        }
        pendingParentRef.current = null
        message.success('Class가 생성되었습니다.')
      } else if (dialogTarget) {
        await updateClass(dataset, graph, dialogTarget.iri, values)
        message.success('Class가 수정되었습니다.')
      }
      setDialogOpen(false)
      refreshAll()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDialogLoading(false)
    }
  }

  // ── Delete ──────────────────────────────────────────────────────────────
  const handleDelete = async (iri: string) => {
    if (!dataset || !graph) return
    const row = rows.find((r) => r.iri === iri)
    if (!row) return
    const targetGraph = row.source_graph ?? graph
    try {
      const detail = await getClass(dataset, targetGraph, iri)
      if (detail.individual_count > 0) {
        setDeleteTarget(row)
        setDeleteIndividualCount(detail.individual_count)
        setOnIndividual('delete')
        setMigrateTarget(undefined)
        setDeleteModalOpen(true)
      } else {
        await doDelete(iri, 'delete', undefined)
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
      // 삭제된 클래스가 상세 창에 열려있으면 닫기
      if (drawerDetail?.iri === iri) setDrawerOpen(false)
      refreshAll()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDeleteLoading(false)
    }
  }

  // ── Detail Drawer ────────────────────────────────────────────────────────
  const openDetailByIri = async (iri: string) => {
    if (!dataset || !graph) return
    const row = rows.find((r) => r.iri === iri)
    const targetGraph = row?.source_graph ?? graph
    setDrawerDetail(null)
    setDrawerOpen(true)
    setDrawerLoading(true)
    try {
      setDrawerDetail(await getClass(dataset, targetGraph, iri))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDrawerLoading(false)
    }
  }

  const openDetail = (row: ClassSummary) => openDetailByIri(row.iri)

  const refreshDetail = async () => {
    if (!dataset || !graph || !drawerDetail) return
    try {
      const targetGraph = rows.find((r) => r.iri === drawerDetail.iri)?.source_graph ?? graph
      setDrawerDetail(await getClass(dataset, targetGraph, drawerDetail.iri))
    } catch { /* 무시 */ }
    refreshAll()
  }

  const shortIRI = (iri: string) => iri.split(/[#/]/).pop() ?? iri

  // ── 테이블 컬럼 ─────────────────────────────────────────────────────────
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
            onClick={(e) => { e.stopPropagation(); openEdit(row.iri) }}
          />
          <Button
            size="small" danger
            icon={<DeleteOutlined />}
            onClick={(e) => { e.stopPropagation(); handleDelete(row.iri) }}
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
      {/* ── 툴바 ────────────────────────────────────────────────────────── */}
      <div style={{ marginBottom: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openCreate()}>
          새 Class
        </Button>
        <Segmented
          value={viewMode}
          onChange={(v) => setViewMode(v as 'table' | 'tree')}
          options={[
            { value: 'table', icon: <UnorderedListOutlined />, label: '목록' },
            { value: 'tree',  icon: <ApartmentOutlined />,     label: '계층 트리' },
          ]}
        />
      </div>

      {/* ── 뷰 ─────────────────────────────────────────────────────────── */}
      {viewMode === 'table' ? (
        <Table
          rowKey="iri"
          size="small"
          loading={loading}
          dataSource={rows}
          columns={columns}
          onRow={(row) => ({ onClick: () => openDetail(row), style: { cursor: 'pointer' } })}
          pagination={{ pageSize: 20, showSizeChanger: false }}
        />
      ) : (
        <ClassHierarchyTree
          items={hierarchyItems}
          classMap={classMap}
          loading={hierarchyLoading}
          onClassSelect={openDetailByIri}
          onEdit={openEdit}
          onDelete={handleDelete}
          onAddChild={(parentIri) => openCreate(parentIri)}
          onRefresh={refreshAll}
        />
      )}

      {/* ── Individual 처리 방법 선택 Modal ─────────────────────────────── */}
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
        onCancel={() => { setDialogOpen(false); pendingParentRef.current = null }}
      />

      <ClassDetailDrawer
        open={drawerOpen}
        detail={drawerDetail}
        loading={drawerLoading}
        allClasses={rows}
        onClose={() => setDrawerOpen(false)}
        onRefresh={refreshDetail}
        onClassSelect={openDetailByIri}
      />
    </>
  )
}

export default ClassTable
