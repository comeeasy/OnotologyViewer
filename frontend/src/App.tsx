import React from 'react'
import { Alert, Layout, Tabs, Typography } from 'antd'
import { OOIProvider, useOOI } from './context/OOIContext'
import OOINavigator from './components/Navigator/OOINavigator'
import ClassTable from './components/Classes/ClassTable'
import ObjPropTable from './components/ObjProps/ObjPropTable'
import DataPropTable from './components/DataProps/DataPropTable'
import IndividualTable from './components/Individuals/IndividualTable'

const { Header, Sider, Content } = Layout
const { Title } = Typography

const OOIGuard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { dataset, graph, namespace } = useOOI()
  if (!dataset || !graph || !namespace) {
    return (
      <Alert
        type="info"
        showIcon
        message="OOI를 먼저 설정하세요"
        description="왼쪽 패널에서 Dataset → Named Graph → Namespace 순서로 선택 후 [OOI 설정] 버튼을 눌러주세요."
        style={{ margin: 24 }}
      />
    )
  }
  return <>{children}</>
}

const tabItems = [
  {
    key: 'classes',
    label: 'Class',
    children: <OOIGuard><ClassTable /></OOIGuard>,
  },
  {
    key: 'objprops',
    label: 'Object Property',
    children: <OOIGuard><ObjPropTable /></OOIGuard>,
  },
  {
    key: 'dataprops',
    label: 'Data Property',
    children: <OOIGuard><DataPropTable /></OOIGuard>,
  },
  {
    key: 'individuals',
    label: 'Individual',
    children: <OOIGuard><IndividualTable /></OOIGuard>,
  },
]

const AppInner: React.FC = () => (
  <Layout style={{ minHeight: '100vh' }}>
    <Header
      style={{ display: 'flex', alignItems: 'center', padding: '0 24px', background: '#001529' }}
    >
      <Title level={4} style={{ color: '#fff', margin: 0 }}>🔷 OntologyViewer</Title>
    </Header>

    <Layout>
      <Sider
        width={260}
        style={{ background: '#fff', borderRight: '1px solid #f0f0f0', overflowY: 'auto' }}
      >
        <OOINavigator />
      </Sider>

      <Content style={{ padding: '16px 24px', background: '#fafafa' }}>
        <Tabs items={tabItems} size="large" />
      </Content>
    </Layout>
  </Layout>
)

const App: React.FC = () => (
  <OOIProvider>
    <AppInner />
  </OOIProvider>
)

export default App
