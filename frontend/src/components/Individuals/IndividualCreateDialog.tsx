import React, { useEffect, useState } from 'react'
import {
  Button, Divider, Form, Input, Modal, Select, Space, Typography,
} from 'antd'
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { XSD_SHORTTYPES, xsdShortname } from '../../types/ontology'
import type {
  ClassSummary, DataPropSummary, IndividualSummary, ObjPropSummary,
} from '../../types/ontology'

const { Text } = Typography

interface CreateValues {
  class_iri: string
  label: string
  comment?: string
  data_properties: { property_iri: string; value: string; datatype: string }[]
  object_properties: { property_iri: string; target_iri: string }[]
}

interface Props {
  open: boolean
  classes: ClassSummary[]
  dataProps: DataPropSummary[]
  objProps: ObjPropSummary[]
  individuals: IndividualSummary[]
  loading: boolean
  onOk: (values: CreateValues) => void
  onCancel: () => void
}

const IndividualCreateDialog: React.FC<Props> = ({
  open, classes, dataProps, objProps, individuals, loading, onOk, onCancel,
}) => {
  const [form] = Form.useForm()
  const selectedClassIri = Form.useWatch('class_iri', form)  // 선택된 Class IRI 실시간 감지
  const [dpRows, setDpRows] = useState<{ property_iri: string; value: string; datatype: string }[]>([])
  const [opRows, setOpRows] = useState<{ property_iri: string; target_iri: string }[]>([])

  useEffect(() => {
    if (open) {
      form.resetFields()
      setDpRows([])
      setOpRows([])
    }
  }, [open, form])

  const handleOk = () => {
    form.validateFields().then((values) => {
      onOk({
        class_iri: values.class_iri,
        label: values.label,
        comment: values.comment || undefined,
        data_properties: dpRows.filter((r) => r.property_iri && r.value),
        object_properties: opRows.filter((r) => r.property_iri && r.target_iri),
      })
    })
  }

  const shortIRI = (iri: string) => iri.split(/[#/]/).pop() ?? iri

  const classOptions = classes.map((c) => ({
    label: c.label ?? shortIRI(c.iri), value: c.iri, title: c.iri,
  }))

  /** 선택된 Class를 domain으로 갖는 DataProp만 (domain 없으면 포함, Class 미선택 시 전체) */
  const dpOptions = dataProps
    .filter((p) => !p.domain || !selectedClassIri || p.domain === selectedClassIri)
    .map((p) => ({ label: p.label ?? shortIRI(p.iri), value: p.iri, title: p.iri }))

  /** 선택된 Class를 domain으로 갖는 ObjProp만 (domain 없으면 포함, Class 미선택 시 전체) */
  const opOptions = objProps
    .filter((p) => !p.domain || !selectedClassIri || p.domain === selectedClassIri)
    .map((p) => ({ label: p.label ?? shortIRI(p.iri), value: p.iri, title: p.iri }))
  /** 선택된 Property의 range 클래스에 속한 Individual만 반환 */
  const getIndOptions = (propIri: string) => {
    const range = objProps.find((p) => p.iri === propIri)?.range
    return individuals
      .filter((i) => !range || i.class_iri === range)
      .map((i) => ({ label: i.label ?? shortIRI(i.iri), value: i.iri, title: i.iri }))
  }

  return (
    <Modal
      title="Individual 생성"
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      okText="생성"
      confirmLoading={loading}
      width={560}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item name="class_iri" label="Class" rules={[{ required: true }]}>
          <Select placeholder="선택" options={classOptions} showSearch />
        </Form.Item>
        <Form.Item name="label" label="Label" rules={[{ required: true }]}>
          <Input placeholder="예: Alice" />
        </Form.Item>
        <Form.Item name="comment" label="Comment">
          <Input.TextArea rows={2} />
        </Form.Item>
      </Form>

      {/* Data Properties */}
      <Divider style={{ margin: '8px 0' }} />
      <Text strong>Data Property 값</Text>
      <Space direction="vertical" style={{ width: '100%', marginTop: 8 }} size={4}>
        {dpRows.map((row, i) => (
          <Space key={i} align="start">
            <Select
              style={{ width: 160 }}
              placeholder="Property"
              options={dpOptions}
              value={row.property_iri || undefined}
              onChange={(v) => {
                const range = dataProps.find((p) => p.iri === v)?.range
                const datatype = range
                  ? (XSD_SHORTTYPES.includes(xsdShortname(range) as typeof XSD_SHORTTYPES[number])
                      ? xsdShortname(range) : 'string')
                  : 'string'
                setDpRows((r) => r.map((x, j) => j === i ? { ...x, property_iri: v, datatype } : x))
              }}
              showSearch
            />
            <Input
              style={{ width: 120 }}
              placeholder="값"
              value={row.value}
              onChange={(e) => setDpRows((r) => r.map((x, j) => j === i ? { ...x, value: e.target.value } : x))}
            />
            <Select
              style={{ width: 100 }}
              placeholder="타입"
              options={XSD_SHORTTYPES.map((t) => ({ label: t, value: t }))}
              value={row.datatype || undefined}
              onChange={(v) => setDpRows((r) => r.map((x, j) => j === i ? { ...x, datatype: v } : x))}
            />
            <Button
              type="text"
              danger
              icon={<MinusCircleOutlined />}
              onClick={() => setDpRows((r) => r.filter((_, j) => j !== i))}
            />
          </Space>
        ))}
        <Button
          type="dashed"
          size="small"
          icon={<PlusOutlined />}
          onClick={() => setDpRows((r) => [...r, { property_iri: '', value: '', datatype: 'string' }])}
        >
          추가
        </Button>
      </Space>

      {/* Object Properties */}
      <Divider style={{ margin: '8px 0' }} />
      <Text strong>Object Property 관계</Text>
      <Space direction="vertical" style={{ width: '100%', marginTop: 8 }} size={4}>
        {opRows.map((row, i) => (
          <Space key={i} align="start">
            <Select
              style={{ width: 160 }}
              placeholder="Property"
              options={opOptions}
              value={row.property_iri || undefined}
              onChange={(v) => setOpRows((r) => r.map((x, j) => j === i ? { ...x, property_iri: v } : x))}
              showSearch
            />
            <Select
              style={{ width: 200 }}
              placeholder="대상 Individual"
              options={getIndOptions(row.property_iri)}
              value={row.target_iri || undefined}
              onChange={(v) => setOpRows((r) => r.map((x, j) => j === i ? { ...x, target_iri: v } : x))}
              showSearch
            />
            <Button
              type="text"
              danger
              icon={<MinusCircleOutlined />}
              onClick={() => setOpRows((r) => r.filter((_, j) => j !== i))}
            />
          </Space>
        ))}
        <Button
          type="dashed"
          size="small"
          icon={<PlusOutlined />}
          onClick={() => setOpRows((r) => [...r, { property_iri: '', target_iri: '' }])}
        >
          추가
        </Button>
      </Space>
    </Modal>
  )
}

export default IndividualCreateDialog
