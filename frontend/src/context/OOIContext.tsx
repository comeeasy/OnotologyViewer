import React, { createContext, useContext, useState } from 'react'
import type { OOIState } from '../types/ontology'

const OOIContext = createContext<OOIState>({
  dataset: null,
  graphs: [],
  graph: null,
  namespace: null,
  namespaces: [],
  setOOI: () => {},
  clear: () => {},
})

export const OOIProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [dataset, setDataset] = useState<string | null>(null)
  const [graphs, setGraphs]   = useState<string[]>([])
  const [namespaces, setNamespaces] = useState<string[]>([])

  const setOOI = (ds: string, gs: string[], ns: string[]) => {
    setDataset(ds)
    setGraphs(gs)
    setNamespaces(ns)
  }

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
      setOOI,
      clear,
    }}>
      {children}
    </OOIContext.Provider>
  )
}

export const useOOI = () => useContext(OOIContext)
