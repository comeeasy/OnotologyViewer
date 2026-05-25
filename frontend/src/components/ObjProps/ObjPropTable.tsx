import React, { useCallback, useEffect, useState } from 'react'
import { Button, Popconfirm, Space, Table, message } from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import {
  createObjProp, deleteObjProp, getObjProp, listObjProps, updateObjProp,
} from '../../api/objProps'
import { listClasses } from '../../api/classes'
import { useOOI } from '../../context/OOIContext'
import type { ClassSummary, ObjPropDetail, ObjPropSummary } from '../../types/ontology'
import ObjPropDialog from './ObjPropDialog'
import ObjPropDetailDrawer from './ObjPropDetail'


const ObjPropTable: React.FC = () => {
  const { dataset, graph, graphs, namespace } = useOOI()

  const [rows, setRows] = useState<ObjPropSummary[]>([])
  const [classes, setClasses] = useState<ClassSummary[]>([])
  const [loading, setLoading] = useState(false)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create')
  const [dialogInitial, setDialogInitial] = useState<ObjPropDetail | null>(null)
  const [dialogLoading, setDialogLoading] = useState(false)

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerDetail, setDrawerDetail] = useState<ObjPropDetail | null>(null)
  const [drawerLoading, setDrawerLoading] = useState(false)

  const load = useCallback(async () => {
    if (!dataset || graphs.length === 0 || !namespace) return
    setLoading(true)
    try {
      const [props, cls] = await Promise.all([
        listObjProps(dataset, graphs, namespace),
        listClasses(dataset, graphs, namespace),
      ])
      setRows(props)
      setClasses(cls)
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [dataset, graphs, namespace])

  useEffect(() => { load() }, [load])

  const openCreate = () => {
    setDialogMode('create')
    setDialogInitial(null)
    setDialogOpen(true)
  }

  const openEdit = async (row: ObjPropSummary) => {
    if (!dataset || !graph) return
    setDialogMode('edit')
    setDialogLoading(true)
    setDialogOpen(true)
    try {
      setDialogInitial(await getObjProp(dataset, graph, row.iri))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDialogLoading(false)
    }
  }

  const handleDialogOk = async (values: {
    label: string; domain: string | undefined; range: string | undefined; characteristics: string[]
  }) => {
    if (!dataset || !graph || !namespace) return
    setDialogLoading(true)
    try {
      if (dialogMode === 'create') {
        await createObjProp(dataset, graph, namespace, values)
        message.success('Object Property가 생성되었습니다.')
      } else if (dialogInitial) {
        await updateObjProp(dataset, graph, dialogInitial.iri, values)
        message.success('Object Property가 수정되었습니다.')
      }
      setDialogOpen(false)
      load()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDialogLoading(false)
    }
  }

  const handleDelete = async (iri: string) => {
    if (!dataset || !graph) return
    try {
      await deleteObjProp(dataset, graph, iri)
      message.success('Object Property가 삭제되었습니다.')
      load()
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  const openDetail = async (row: ObjPropSummary) => openDetailByIri(row.iri)

  const openDetailByIri = async (iri: string) => {
    if (!dataset || !graph) return
    setDrawerDetail(null)
    setDrawerOpen(true)
    setDrawerLoading(true)
    try {
      setDrawerDetail(await getObjProp(dataset, graph, iri))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDrawerLoading(false)
    }
  }

  const refreshDetail = async () => {
    if (!dataset || !graph || !drawerDetail) return
    try {
      setDrawerDetail(await getObjProp(dataset, graph, drawerDetail.iri))
    } catch { /* 무시 */ }
  }

  const shortIRI = (iri: string | null) => iri?.split(/[#/]/).pop() ?? '-'
  const classLabel = (iri: string | null) => {
    if (!iri) return '-'
    return classes.find((c) => c.iri === iri)?.label ?? shortIRI(iri)
  }

  const columns = [
    {
      title: 'Name',
      dataIndex: 'label',
      render: (v: string | null, row: ObjPropSummary) => (
        <a
          onClick={(e) => { e.stopPropagation(); openDetail(row) }}
          style={{ fontWeight: 500 }}
        >
          {v ?? shortIRI(row.iri)}
        </a>
      ),
    },
    { title: 'Domain', dataIndex: 'domain', render: classLabel },
    { title: 'Range', dataIndex: 'range', render: classLabel },
    {
      title: '작업',
      width: 80,
      render: (_: unknown, row: ObjPropSummary) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={(e) => { e.stopPropagation(); openEdit(row) }}
          />
          <Popconfirm
            title="삭제하시겠습니까?"
            onConfirm={(e) => { e?.stopPropagation(); handleDelete(row.iri) }}
            onCancel={(e) => e?.stopPropagation()}
            okText="삭제" okButtonProps={{ danger: true }}
          >
            <Button size="small" danger icon={<DeleteOutlined />} onClick={(e) => e.stopPropagation()} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <>
      <div style={{ marginBottom: 12 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          새 Object Property
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
      <ObjPropDialog
        open={dialogOpen}
        mode={dialogMode}
        initial={dialogInitial}
        classes={classes}
        loading={dialogLoading}
        onOk={handleDialogOk}
        onCancel={() => setDialogOpen(false)}
      />
      <ObjPropDetailDrawer
        open={drawerOpen}
        detail={drawerDetail}
        loading={drawerLoading}
        allProps={rows}
        onClose={() => setDrawerOpen(false)}
        onRefresh={refreshDetail}
        onPropSelect={openDetailByIri}
      />
    </>
  )
}

export default ObjPropTable
