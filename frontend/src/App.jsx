import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useCallback } from 'react'
import Sidebar from './components/common/Sidebar'
import Overview from './pages/Overview'
import PRIntelligence from './pages/PRIntelligence'
import PRDetail from './pages/PRDetail'
import Insights from './pages/Insights'
import Events from './pages/Events'
import Settings from './pages/Settings'
import { useWebSocket } from './hooks/useWebSocket'
import ErrorBoundary from './components/common/ErrorBoundary'

function AppShell() {
  // Top-level WS connection just for sidebar indicator
  const onMsg = useCallback(() => {}, [])
  const { connected } = useWebSocket(onMsg)

  return (
    <div className="flex min-h-screen">
      <Sidebar wsConnected={connected} />
      <main className="flex-1 min-w-0 overflow-auto">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/prs" element={<PRIntelligence />} />
          <Route path="/pr/:id" element={<PRDetail />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/events" element={<Events />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}
