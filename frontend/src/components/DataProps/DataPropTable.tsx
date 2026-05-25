import React, { useCallback, useEffect, useState } from 'react'
import { Button, Popconfirm, Space, Table, Tag, message } from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import {
  createDataProp, deleteDataProp, getDataProp, listDataProps, updateDataProp,
} from '../../api/dataProps'
import { listClasses } from '../../api/classes'
import { useOOI } from '../../context/OOIContext'
import { xsdShortname } from '../../types/ontology'
import type { ClassSummary, DataPropDetail, DataPropSummary } from '../../types/ontology'
import DataPropDialog from './DataPropDialog'
import DataPropDetailDrawer from './DataPropDetail'


const DataPropTable: React.FC = () => {
  const { dataset, graph, graphs, namespace, pendingNavigation, clearNavigation } = useOOI()

  const [rows, setRows] = useState<DataPropSummary[]>([])
  const [classes, setClasses] = useState<ClassSummary[]>([])
  const [loading, setLoading] = useState(false)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create')
  const [dialogInitial, setDialogInitial] = useState<DataPropDetail | null>(null)
  const [dialogLoading, setDialogLoading] = useState(false)

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerDetail, setDrawerDetail] = useState<DataPropDetail | null>(null)
  const [drawerLoading, setDrawerLoading] = useState(false)

  const load = useCallback(async () => {
    if (!dataset || graphs.length === 0 || !namespace) return
    setLoading(true)
    try {
      const [props, cls] = await Promise.all([
        listDataProps(dataset, graphs, namespace),
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

  const openEdit = async (row: DataPropSummary) => {
    if (!dataset || !graph) return
    setDialogMode('edit')
    setDialogLoading(true)
    setDialogOpen(true)
    try {
      setDialogInitial(await getDataProp(dataset, graph, row.iri))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDialogLoading(false)
    }
  }

  const handleDialogOk = async (values: {
    label: string; domain: string; range: string; functional: boolean
  }) => {
    if (!dataset || !graph || !namespace) return
    setDialogLoading(true)
    try {
      if (dialogMode === 'create') {
        await createDataProp(dataset, graph, namespace, values)
        message.success('Data Property가 생성되었습니다.')
      } else if (dialogInitial) {
        await updateDataProp(dataset, graph, dialogInitial.iri, values)
        message.success('Data Property가 수정되었습니다.')
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
      await deleteDataProp(dataset, graph, iri)
      message.success('Data Property가 삭제되었습니다.')
      load()
    } catch (e: unknown) {
      message.error((e as Error).message)
    }
  }

  const openDetailByIri = async (iri: string) => {
    if (!dataset || !graph) return
    setDrawerDetail(null)
    setDrawerOpen(true)
    setDrawerLoading(true)
    try {
      setDrawerDetail(await getDataProp(dataset, graph, iri))
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDrawerLoading(false)
    }
  }
  const openDetail = async (row: DataPropSummary) => openDetailByIri(row.iri)

  // SPARQL 탭에서 DataProp IRI 클릭 시 자동으로 Drawer 열기
  useEffect(() => {
    if (pendingNavigation?.tab !== 'dataprops' || !pendingNavigation.iri) return
    const iri = pendingNavigation.iri
    clearNavigation()
    openDetailByIri(iri)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingNavigation])

  const shortIRI = (iri: string | null) => iri?.split(/[#/]/).pop() ?? '-'
  const classLabel = (iri: string | null) => {
    if (!iri) return '-'
    return classes.find((c) => c.iri === iri)?.label ?? shortIRI(iri)
  }

  const columns = [
    {
      title: 'Name',
      dataIndex: 'label',
      render: (v: string | null, row: DataPropSummary) => (
        <a
          onClick={(e) => { e.stopPropagation(); openDetail(row) }}
          style={{ fontWeight: 500 }}
        >
          {v ?? shortIRI(row.iri)}
        </a>
      ),
    },
    { title: 'Domain', dataIndex: 'domain', render: classLabel },
    {
      title: 'Range',
      dataIndex: 'range',
      render: (v: string | null) => v ? <Tag>{xsdShortname(v)}</Tag> : '-',
    },
    {
      title: '작업',
      width: 80,
      render: (_: unknown, row: DataPropSummary) => (
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
          새 Data Property
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
      <DataPropDialog
        open={dialogOpen}
        mode={dialogMode}
        initial={dialogInitial}
        classes={classes}
        loading={dialogLoading}
        onOk={handleDialogOk}
        onCancel={() => setDialogOpen(false)}
      />
      <DataPropDetailDrawer
        open={drawerOpen}
        detail={drawerDetail}
        loading={drawerLoading}
        onClose={() => setDrawerOpen(false)}
      />
    </>
  )
}

export default DataPropTable
