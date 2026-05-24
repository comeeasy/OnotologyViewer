import React, { createContext, useContext, useState } from 'react'
import type { OOIState } from '../types/ontology'

const OOIContext = createContext<OOIState>({
  dataset: null,
  graph: null,
  namespace: null,
  setOOI: () => {},
  clear: () => {},
})

export const OOIProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [dataset, setDataset] = useState<string | null>(null)
  const [graph, setGraph] = useState<string | null>(null)
  const [namespace, setNamespace] = useState<string | null>(null)

  const setOOI = (ds: string, g: string, ns: string) => {
    setDataset(ds)
    setGraph(g)
    setNamespace(ns)
  }

  const clear = () => {
    setDataset(null)
    setGraph(null)
    setNamespace(null)
  }

  return (
    <OOIContext.Provider value={{ dataset, graph, namespace, setOOI, clear }}>
      {children}
    </OOIContext.Provider>
  )
}

export const useOOI = () => useContext(OOIContext)
