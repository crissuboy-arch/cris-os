import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Agents from './pages/Agents'
import Chat from './pages/Chat'
import Memory from './pages/Memory'
import Projects from './pages/Projects'
import Clients from './pages/Clients'
import Tasks from './pages/Tasks'
import Prompts from './pages/Prompts'
import Logs from './pages/Logs'
import Settings from './pages/Settings'
import StudioDashboard from './pages/studio/StudioDashboard'
import StudioAgentList from './pages/studio/StudioAgentList'
import StudioAgentEditor from './pages/studio/StudioAgentEditor'
import StudioObservability from './pages/studio/StudioObservability'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/agentes" element={<Agents />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/memoria" element={<Memory />} />
        <Route path="/projetos" element={<Projects />} />
        <Route path="/clientes" element={<Clients />} />
        <Route path="/tarefas" element={<Tasks />} />
        <Route path="/prompts" element={<Prompts />} />
        <Route path="/logs" element={<Logs />} />
        <Route path="/configuracoes" element={<Settings />} />
        <Route path="/studio" element={<StudioDashboard />} />
        <Route path="/studio/agentes" element={<StudioAgentList />} />
        <Route path="/studio/agentes/:id" element={<StudioAgentEditor />} />
        <Route path="/studio/observabilidade" element={<StudioObservability />} />
      </Route>
    </Routes>
  )
}
