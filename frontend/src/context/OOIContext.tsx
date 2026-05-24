import React, { createContext, useContext, useState } from 'react'
import type { OOIState } from '../types/ontology'

const OOIContext = createContext<OOIState>({
  dataset: null,
  graph: null,
  namespace: null,
  namespaces: [],
  setOOI: () => {},
  clear: () => {},
})

export const OOIProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [dataset, setDataset] = useState<string | null>(null)
  const [graph, setGraph] = useState<string | null>(null)
  const [namespaces, setNamespaces] = useState<string[]>([])

  const setOOI = (ds: string, g: string, ns: string[]) => {
    setDataset(ds)
    setGraph(g)
    setNamespaces(ns)
  }

  const clear = () => {
    setDataset(null)
    setGraph(null)
    setNamespaces([])
  }

  return (
    <OOIContext.Provider value={{
      dataset,
      graph,
      namespace: namespaces[0] ?? null,  // 하위 호환
      namespaces,
      setOOI,
      clear,
    }}>
      {children}
    </OOIContext.Provider>
  )
}

export const useOOI = () => useContext(OOIContext)
