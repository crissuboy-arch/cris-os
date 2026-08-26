import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './lib/auth'
import Layout from './components/Layout'
import LoginPage from './pages/studio/LoginPage'
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
import StudioExecutiveDashboard from './pages/studio/StudioExecutiveDashboard'
import StudioMcp from './pages/studio/StudioMcp'
import StudioVersioning from './pages/studio/StudioVersioning'
import StudioExportImport from './pages/studio/StudioExportImport'
import StudioNotifications from './pages/studio/StudioNotifications'
import Hoje from './pages/Hoje'
import Tarefas from './pages/Tarefas'
import Projetos from './pages/Projetos'
import Agenda from './pages/Agenda'
import Aguardando from './pages/Aguardando'
import Bloqueados from './pages/Bloqueados'
import RevisaoSemanal from './pages/RevisaoSemanal'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-zinc-500">Carregando...</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
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
          <Route path="/studio/executivo" element={<StudioExecutiveDashboard />} />
          <Route path="/studio/mcp" element={<StudioMcp />} />
          <Route path="/studio/versioning" element={<StudioVersioning />} />
          <Route path="/studio/export" element={<StudioExportImport />} />
          <Route path="/studio/notifications" element={<StudioNotifications />} />
          <Route path="/hoje" element={<Hoje />} />
          <Route path="/tarefas" element={<Tarefas />} />
          <Route path="/projetos" element={<Projetos />} />
          <Route path="/agenda" element={<Agenda />} />
          <Route path="/aguardando" element={<Aguardando />} />
          <Route path="/bloqueados" element={<Bloqueados />} />
          <Route path="/revisao-semanal" element={<RevisaoSemanal />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}
