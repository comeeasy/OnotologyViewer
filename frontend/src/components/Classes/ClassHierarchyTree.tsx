import React, { useMemo, useState } from 'react'
import { Tree, Button, Spin, Typography, message, Tooltip } from 'antd'
import {
  EditOutlined, DeleteOutlined, PlusCircleOutlined,
} from '@ant-design/icons'
import type { DataNode, EventDataNode } from 'antd/es/tree'
import type { ClassHierarchyItem } from '../../api/classes'
import type { ClassSummary } from '../../types/ontology'
import { addSuperClass, removeSuperClass } from '../../api/classes'
import { useOOI } from '../../context/OOIContext'

const { Text } = Typography

interface Props {
  items: ClassHierarchyItem[]       // 계층 데이터 (iri + super_classes)
  classMap: Map<string, ClassSummary> // iri → label 매핑 (label 표시용)
  loading: boolean
  onClassSelect: (iri: string) => void   // 클래스 상세 열기
  onEdit: (iri: string) => void
  onDelete: (iri: string) => void
  onAddChild: (parentIri: string) => void  // 새 자식 클래스 생성
  onRefresh: () => void
}

const ClassHierarchyTree: React.FC<Props> = ({
  items, classMap, loading, onClassSelect, onEdit, onDelete, onAddChild, onRefresh,
}) => {
  const { dataset, graph } = useOOI()
  const [dragging, setDragging] = useState(false)

  const shortIRI = (iri: string) => iri.split(/[#/]/).pop() ?? iri
  const labelOf = (iri: string) => classMap.get(iri)?.label ?? shortIRI(iri)

  // 네임스페이스 내 IRI Set (부모-자식 관계 필터링용)
  const iriSet = useMemo(() => new Set(items.map((i) => i.iri)), [items])

  // 트리 데이터 빌드
  const treeData = useMemo(() => {
    // 루트 노드: 네임스페이스 내 부모가 없는 클래스
    const roots = items.filter(
      (item) => item.super_classes.filter((p) => iriSet.has(p)).length === 0,
    )

    const visited = new Set<string>()

    const buildNode = (iri: string): DataNode => {
      // 순환 방지
      if (visited.has(iri)) {
        return {
          key: `${iri}__cycle`,
          title: <Text type="secondary" style={{ fontSize: 11 }}>[순환참조] {labelOf(iri)}</Text>,
          isLeaf: true,
        }
      }
      visited.add(iri)

      const children = items.filter((i) =>
        i.super_classes.filter((p) => iriSet.has(p))[0] === iri,
      )

      const node: DataNode = {
        key: iri,
        title: (
          <span
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              paddingRight: 4,
            }}
          >
            {/* 클래스 이름 — 클릭 시 상세 열기 */}
            <span
              onClick={(e) => { e.stopPropagation(); onClassSelect(iri) }}
              style={{ flex: 1, cursor: 'pointer', fontWeight: 450 }}
              title={iri}
            >
              {labelOf(iri)}
            </span>
            {/* 액션 버튼 */}
            <Tooltip title="자식 Class 추가">
              <Button
                size="small" type="text" icon={<PlusCircleOutlined />}
                style={{ opacity: 0.55 }}
                onClick={(e) => { e.stopPropagation(); onAddChild(iri) }}
              />
            </Tooltip>
            <Tooltip title="편집">
              <Button
                size="small" type="text" icon={<EditOutlined />}
                style={{ opacity: 0.55 }}
                onClick={(e) => { e.stopPropagation(); onEdit(iri) }}
              />
            </Tooltip>
            <Tooltip title="삭제">
              <Button
                size="small" type="text" danger icon={<DeleteOutlined />}
                style={{ opacity: 0.55 }}
                onClick={(e) => { e.stopPropagation(); onDelete(iri) }}
              />
            </Tooltip>
          </span>
        ),
        children: children.length > 0 ? children.map((c) => buildNode(c.iri)) : undefined,
        isLeaf: children.length === 0,
      }

      visited.delete(iri)
      return node
    }

    return roots.map((r) => buildNode(r.iri))
  }, [items, iriSet, classMap, onClassSelect, onEdit, onDelete, onAddChild])

  // ── Drag & Drop 처리 ─────────────────────────────────────────────────────
  const handleDrop = async (info: {
    dragNode: EventDataNode<DataNode>
    node: EventDataNode<DataNode>
    dropToGap: boolean
    dropPosition: number
  }) => {
    if (!dataset || !graph) return

    const dragIri = info.dragNode.key as string
    const dropIri = info.node.key as string

    // cycle key 무시
    if (dragIri.endsWith('__cycle') || dropIri.endsWith('__cycle')) return
    // 자기 자신 무시
    if (dragIri === dropIri) return

    const dragItem = items.find((i) => i.iri === dragIri)
    if (!dragItem) return

    setDragging(true)
    try {
      const oldNsParents = dragItem.super_classes.filter((p) => iriSet.has(p))

      if (!info.dropToGap) {
        // ── Case 1: 노드 위에 드롭 → dropIri 의 자식이 됨 ──────────────────
        for (const oldParent of oldNsParents) {
          await removeSuperClass(dataset, graph, dragIri, oldParent)
        }
        await addSuperClass(dataset, graph, dragIri, dropIri)
        message.success(`${labelOf(dragIri)} → ${labelOf(dropIri)} 하위로 이동`)
      } else {
        // ── Case 2: 노드 사이 갭에 드롭 → dropIri 와 같은 레벨 ─────────────
        const dropItem = items.find((i) => i.iri === dropIri)
        const dropNsParents = (dropItem?.super_classes ?? []).filter((p) => iriSet.has(p))

        if (dropNsParents.length === 0) {
          // 루트 레벨 갭 → 루트로 이동 (부모 제거)
          for (const oldParent of oldNsParents) {
            await removeSuperClass(dataset, graph, dragIri, oldParent)
          }
          if (oldNsParents.length > 0) message.success(`${labelOf(dragIri)} → 최상위로 이동`)
        } else {
          // 서브트리 갭 → dropIri 의 부모를 공유
          const newParent = dropNsParents[0]
          for (const oldParent of oldNsParents) {
            await removeSuperClass(dataset, graph, dragIri, oldParent)
          }
          await addSuperClass(dataset, graph, dragIri, newParent)
          message.success(`${labelOf(dragIri)} → ${labelOf(newParent)} 하위로 이동`)
        }
      }
      onRefresh()
    } catch (e: unknown) {
      message.error((e as Error).message)
    } finally {
      setDragging(false)
    }
  }

  if (loading || dragging) {
    return (
      <div style={{ textAlign: 'center', padding: 24 }}>
        <Spin tip={dragging ? '계층 변경 중...' : '로딩 중...'} />
      </div>
    )
  }

  if (items.length === 0) {
    return <Text type="secondary">Class 없음</Text>
  }

  return (
    <Tree
      treeData={treeData}
      draggable={{ icon: false }}
      blockNode
      defaultExpandAll
      showLine={{ showLeafIcon: false }}
      onDrop={handleDrop}
      style={{
        background: 'transparent',
        userSelect: 'none',
      }}
    />
  )
}

export default ClassHierarchyTree
