import React, { createContext, useContext, useState } from 'react'
import type { OOIState, PendingNavigation } from '../types/ontology'

const OOIContext = createContext<OOIState>({
  dataset: null,
  graphs: [],
  graph: null,
  namespace: null,
  namespaces: [],
  pendingNavigation: null,
  navigate: () => {},
  clearNavigation: () => {},
  setOOI: () => {},
  clear: () => {},
})

export const OOIProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [dataset, setDataset] = useState<string | null>(null)
  const [graphs, setGraphs]   = useState<string[]>([])
  const [namespaces, setNamespaces] = useState<string[]>([])
  const [pendingNavigation, setPendingNavigation] = useState<PendingNavigation | null>(null)

  const setOOI = (ds: string, gs: string[], ns: string[]) => {
    setDataset(ds)
    setGraphs(gs)
    setNamespaces(ns)
  }

  const navigate = (tab: string, iri: string) => {
    setPendingNavigation({ tab, iri })
  }

  const clearNavigation = () => setPendingNavigation(null)

  const clear = () => {
    setDataset(null)
    setGraphs([])
    setNamespaces([])
  }

  return (
    <OOIContext.Provider value={{
      dataset,
      graphs,
      graph:     graphs[0] ?? null,  // 하위 호환: 첫 번째 그래프
      namespace: namespaces[0] ?? null,
      namespaces,
      pendingNavigation,
      navigate,
      clearNavigation,
      setOOI,
      clear,
    }}>
      {children}
    </OOIContext.Provider>
  )
}

export const useOOI = () => useContext(OOIContext)
