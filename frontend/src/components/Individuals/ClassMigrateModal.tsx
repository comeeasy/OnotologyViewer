/**
 * v02-E: Individual Class 마이그레이션 Modal
 * - 새 Class 선택
 * - 비호환 property 미리보기
 * - keep / delete 옵션 선택 후 실행
 */

import React, { useState } from 'react'
import {
  Alert, Button, Form, Modal, Radio, Select, Space, Tag, Typography, message,
} from 'antd'
import { previewClassMigrate, migrateIndividualClass } from '../../api/individuals'
import { listClasses } from '../../api/classes'
import type { ClassSummary, DataPropSummary, ObjPropSummary } from '../../types/ontology'

const { Text } = Typography

interface Props {
  open: boolean
  dataset: string
  graph: string
  namespaces: string[]
  individualIri: string
  currentClassIri: string
  allClasses?: ClassSummary[]       // label 조회용 (외부 제공)
  allDataProps?: DataPropSummary[]  // 비호환 property label 조회용
  allObjProps?: ObjPropSummary[]    // 비호환 property label 조회용
  onClose: () => void
  onMigrated: () => void
}

const ClassMigrateModal: React.FC<Props> = ({
  open, dataset, graph, namespaces, individualIri, currentClassIri,
  allClasses: externalClasses = [], allDataProps = [], allObjProps = [],
  onClose, onMigrated,
}) => {
  const [classes, setClasses] = useState<ClassSummary[]>([])
  const [classLoading, setClassLoading] = useState(false)

  const [newClassIri, setNewClassIri] = useState<string | null>(null)
  const [incompatOption, setIncompatOption] = useState<'keep' | 'delete'>('keep')
  const [incompatProps, setIncompatProps] = useState<string[] | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [migrating, setMigrating] = useState(false)

  const shortIRI = (iri: string) => iri.split(/[#/]/).pop() ?? iri

  // 외부 목록 우선, 없으면 내부 로드된 목록 사용
  const mergedClasses = externalClasses.length > 0 ? externalClasses : classes
  const classLabel = (iri: string) => mergedClasses.find((c) => c.iri === iri)?.label ?? shortIRI(iri)
  const propLabel  = (iri: string) => {
    const dp = allDataProps.find((p) => p.iri === iri)
    if (dp) return dp.label ?? shortIRI(iri)
    const op = allObjProps.find((p) => p.iri === iri)
    if (op) return op.label ?? shortIRI(iri)
    return shortIRI(iri)
  }

  const loadClasses = async () => {
    if (classes.length > 0) return
    setClassLoading(true)
    try {
      const ns = namespaces.length > 0 ? namespaces : ['http://']
      const list = await listClasses(dataset, graph, ns)
      setClasses(list)
    } catch {
      // ignore
    } finally {
      setClassLoading(false)
    }
  }

  const handlePreview = async () => {
    if (!newClassIri) return
    setPreviewing(true)
    try {
      const res = await previewClassMigrate(dataset, graph, individualIri, newClassIri)
      setIncompatProps(res.incompatible_properties)
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setPreviewing(false)
    }
  }

  const handleMigrate = async () => {
    if (!newClassIri) return
    setMigrating(true)
    try {
      const res = await migrateIndividualClass(dataset, graph, individualIri, newClassIri, incompatOption)
      if (res.deleted_properties.length > 0) {
        message.success(`마이그레이션 완료 — ${res.deleted_properties.length}개 property 삭제됨`)
      } else {
        message.success('마이그레이션 완료')
      }
      onMigrated()
      onClose()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setMigrating(false)
    }
  }

  const handleCancel = () => {
    setNewClassIri(null)
    setIncompatProps(null)
    setIncompatOption('keep')
    onClose()
  }

  const classOptions = mergedClasses
    .filter((c) => c.iri !== currentClassIri)
    .map((c) => ({
      value: c.iri,
      label: c.label ?? shortIRI(c.iri),
      title: c.iri,
    }))

  return (
    <Modal
      title="Individual Class 마이그레이션"
      open={open}
      onCancel={handleCancel}
      footer={[
        <Button key="cancel" onClick={handleCancel}>취소</Button>,
        <Button
          key="preview"
          onClick={handlePreview}
          loading={previewing}
          disabled={!newClassIri}
        >
          비호환 확인
        </Button>,
        <Button
          key="migrate"
          type="primary"
          onClick={handleMigrate}
          loading={migrating}
          disabled={!newClassIri || incompatProps === null}
        >
          마이그레이션 실행
        </Button>,
      ]}
      destroyOnClose
      width={520}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <div>
          <Text type="secondary" style={{ fontSize: 11 }}>현재 Class:</Text>
          <br />
          <Text code style={{ fontSize: 12 }}>{classLabel(currentClassIri)}</Text>
          <Text type="secondary" style={{ fontSize: 10, marginLeft: 6 }}>{shortIRI(currentClassIri)}</Text>
        </div>

        <Form layout="vertical">
          <Form.Item label="새 Class 선택" required>
            <Select
              showSearch
              placeholder="새 Class를 선택하세요"
              style={{ width: '100%' }}
              value={newClassIri}
              loading={classLoading}
              onFocus={loadClasses}
              onChange={(v) => { setNewClassIri(v); setIncompatProps(null) }}
              options={classOptions}
              filterOption={(input, opt) =>
                (opt?.label as string ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </Form.Item>

          {incompatProps !== null && (
            <Form.Item label="비호환 Property 처리">
              {incompatProps.length === 0 ? (
                <Alert type="success" message="비호환 property가 없습니다. 바로 마이그레이션할 수 있습니다." showIcon />
              ) : (
                <>
                  <div style={{ marginBottom: 8 }}>
                    <Text type="warning">아래 property는 새 Class에 도메인이 없습니다:</Text>
                    <div style={{ marginTop: 4 }}>
                      {incompatProps.map((p) => (
                        <Tag key={p} color="orange" style={{ marginBottom: 4, fontSize: 11 }} title={p}>
                          {propLabel(p)}
                        </Tag>
                      ))}
                    </div>
                  </div>
                  <Radio.Group
                    value={incompatOption}
                    onChange={(e) => setIncompatOption(e.target.value)}
                  >
                    <Space direction="vertical">
                      <Radio value="keep">유지 (값 보존, OWL 비준수 가능)</Radio>
                      <Radio value="delete">삭제 (해당 property 트리플 제거)</Radio>
                    </Space>
                  </Radio.Group>
                </>
              )}
            </Form.Item>
          )}
        </Form>

        {incompatProps === null && newClassIri && (
          <Alert
            type="info"
            message="'비호환 확인' 버튼을 눌러 마이그레이션 가능 여부를 확인하세요."
            showIcon
          />
        )}
      </Space>
    </Modal>
  )
}

export default ClassMigrateModal
