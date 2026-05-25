import React, { useCallback, useEffect, useState } from 'react'
import { Button, Popconfirm, Select, Space, Table, message } from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import {
  createIndividual, deleteIndividual, getIndividual, listIndividuals, updateIndividual,
} from '../../api/individuals'
import { listClasses } from '../../api/classes'
import { listObjProps } from '../../api/objProps'
import { listDataProps } from '../../api/dataProps'
import { useOOI } from '../../context/OOIContext'
import type {
  ClassSummary, DataPropSummary, IndividualDetail,
  IndividualSummary, ObjPropSummary,
} from '../../types/ontology'
import IndividualCreateDialog from './IndividualCreateDialog'
import IndividualEditDialog from './IndividualEditDialog'
import IndividualDetailDrawer from './IndividualDetail'


const IndividualTable: React.FC = () => {
  const { dataset, graph, graphs, namespace } = useOOI()

  const [rows, setRows] = useState<IndividualSummary[]>([])
  const [classes, setClasses] = useState<ClassSummary[]>([])
  const [dataProps, setDataProps] = useState<DataPropSummary[]>([])
  const [objProps, setObjProps] = useState<ObjPropSummary[]>([])
  const [loading, setLoading] = useState(false)

  const [classFilter, setClassFilter] = useState<string | undefined>(undefined)

  // Create Dialog
  const [createOpen, setCreateOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)

  // Edit Dialog
  const [editOpen, setEditOpen] = useState(false)
  const [editDetail, setEditDetail] = useState<IndividualDetail | null>(null)
  const [editLoading, setEditLoading] = useState(false)

  // Detail Drawer
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerDetail, setDrawerDetail] = useState<IndividualDetail | null>(null)
  const [drawerLoading, setDrawerLoading] = useState(false)

  const loadMeta = useCallback(async () => {
    if (!dataset || graphs.length === 0 || !namespace) return
    try {
      const [cls, dp, op] = await Promise.all([
        listClasses(dataset, graphs, namespace),
        listDataProps(dataset, graphs, namespace),
        listObjProps(dataset, graphs, namespace),
      ])
      setClasses(cls)
      setDataProps(dp)
      setObjProps(op)
    } catch { /* 무시 */ }
  }, [dataset, graphs, namespace])

  const loadRows = useCallback(async () => {
    if (!dataset || graphs.length === 0 || !namespace) return
    setLoading(true)
    try {
      setRows(await listIndividuals(dataset, graphs, namespace, classFilter))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [dataset, graphs, namespace, classFilter])

  useEffect(() => { loadMeta(); loadRows() }, [loadMeta, loadRows])

  // ── Create ──
  const handleCreate = async (values: {
    class_iri: string; label: string; comment?: string
    data_properties: { property_iri: string; value: string; datatype: string }[]
    object_properties: { property_iri: string; target_iri: string }[]
  }) => {
    if (!dataset || !graph || !namespace) return
    setCreateLoading(true)
    try {
      await createIndividual(dataset, graph, namespace, values)
      message.success('Individual이 생성되었습니다.')
      setCreateOpen(false)
      loadRows()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setCreateLoading(false)
    }
  }

  // ── Edit ──
  const openEdit = async (row: IndividualSummary) => {
    if (!dataset || !graph) return
    const targetGraph = row.source_graph ?? graph
    setEditDetail(null)
    setEditOpen(true)
    setEditLoading(true)
    try {
      setEditDetail(await getIndividual(dataset, targetGraph, row.iri))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setEditLoading(false)
    }
  }

  const handleEdit = async (values: {
    label: string; comment?: string
    data_property_updates: { property_iri: string; value: string; datatype: string }[]
    object_property_updates: { property_iri: string; target_iri: string; action: 'add' | 'remove' }[]
  }) => {
    if (!dataset || !graph || !editDetail) return
    setEditLoading(true)
    try {
      await updateIndividual(dataset, graph, editDetail.iri, values)
      message.success('Individual이 수정되었습니다.')
      setEditOpen(false)
      loadRows()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setEditLoading(false)
    }
  }

  // ── Delete ──
  const handleDelete = async (iri: string) => {
    if (!dataset || !graph) return
    try {
      await deleteIndividual(dataset, graph, iri)
      message.success('Individual이 삭제되었습니다.')
      loadRows()
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  // ── Detail ──
  const openDetail = async (row: IndividualSummary) => {
    if (!dataset || !graph) return
    setDrawerDetail(null)
    setDrawerOpen(true)
    setDrawerLoading(true)
    try {
      setDrawerDetail(await getIndividual(dataset, graph, row.iri))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDrawerLoading(false)
    }
  }

  const shortIRI = (iri: string) => iri.split(/[#/]/).pop() ?? iri
  const classLabel = (iri: string) =>
    classes.find((c) => c.iri === iri)?.label ?? shortIRI(iri)

  const columns = [
    {
      title: 'Name',
      dataIndex: 'label',
      render: (v: string | null, row: IndividualSummary) => (
        <a
          onClick={(e) => { e.stopPropagation(); openDetail(row) }}
          style={{ fontWeight: 500 }}
        >
          {v ?? shortIRI(row.iri)}
        </a>
      ),
    },
    {
      title: 'Class',
      dataIndex: 'class_iri',
      render: (v: string) => (
        <span title={v} style={{ color: '#555' }}>{classLabel(v)}</span>
      ),
    },
    {
      title: '작업',
      width: 80,
      render: (_: unknown, row: IndividualSummary) => (
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

  const classOptions = [
    { label: '전체', value: '' },
    ...classes.map((c) => ({
      label: c.label ?? shortIRI(c.iri), value: c.iri, title: c.iri,
    })),
  ]

  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          새 Individual
        </Button>
        <Select
          style={{ width: 200 }}
          placeholder="Class 필터"
          allowClear
          options={classOptions}
          value={classFilter}
          onChange={(v) => setClassFilter(v || undefined)}
        />
      </Space>

      <Table
        rowKey="iri"
        size="small"
        loading={loading}
        dataSource={rows}
        columns={columns}
        onRow={(row) => ({ onClick: () => openDetail(row), style: { cursor: 'pointer' } })}
        pagination={{ pageSize: 20, showSizeChanger: false }}
      />

      <IndividualCreateDialog
        open={createOpen}
        classes={classes}
        dataProps={dataProps}
        objProps={objProps}
        individuals={rows}
        loading={createLoading}
        onOk={handleCreate}
        onCancel={() => setCreateOpen(false)}
      />

      <IndividualEditDialog
        open={editOpen}
        detail={editDetail}
        dataProps={dataProps}
        objProps={objProps}
        individuals={rows}
        loading={editLoading}
        onOk={handleEdit}
        onCancel={() => setEditOpen(false)}
      />

      <IndividualDetailDrawer
        open={drawerOpen}
        detail={drawerDetail}
        loading={drawerLoading}
        dataset={dataset ?? ''}
        graph={graph ?? ''}
        namespaces={namespace ? [namespace] : []}
        allClasses={classes}
        allDataProps={dataProps}
        allObjProps={objProps}
        onClose={() => setDrawerOpen(false)}
        onRefresh={loadRows}
      />
    </>
  )
}

export default IndividualTable
