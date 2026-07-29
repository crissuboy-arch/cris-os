import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bot, Plus, FileCheck, FileEdit, Archive, Activity } from 'lucide-react'
import { studioApi, type StudioAgent } from '../../lib/api'
import CreateAgentModal from './CreateAgentModal'
import StatusBadge from '../../components/StatusBadge'

export default function StudioDashboard() {
  const [agents, setAgents] = useState<StudioAgent[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    setLoading(true)
    studioApi.list()
      .then(setAgents)
      .catch(() => setAgents([]))
      .finally(() => setLoading(false))
  }, [])

  const drafts = agents.filter(a => a.status === 'draft')
  const published = agents.filter(a => a.status === 'published')

  const stats = [
    { label: 'Total', value: agents.length, icon: Bot, color: 'text-blue-400' },
    { label: 'Rascunhos', value: drafts.length, icon: FileEdit, color: 'text-yellow-400' },
    { label: 'Publicados', value: published.length, icon: FileCheck, color: 'text-cris-400' },
    { label: 'Arquivados', value: agents.filter(a => a.status === 'archived').length, icon: Archive, color: 'text-zinc-400' },
  ]

  const recent = agents.slice(0, 6)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">CRIS Studio</h1>
          <p className="text-sm text-zinc-500">Crie e gerencie seus agentes visuais</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> Novo Agente
        </button>
      </div>

      {loading ? (
        <div className="flex h-48 items-center justify-center">
          <Activity className="h-8 w-8 animate-pulse text-cris-500" />
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {stats.map(s => (
              <div key={s.label} className="card">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs text-zinc-500">{s.label}</p>
                    <p className="mt-1 text-2xl font-bold">{s.value}</p>
                  </div>
                  <s.icon className={`h-5 w-5 ${s.color}`} />
                </div>
              </div>
            ))}
          </div>

          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-medium text-zinc-400">Agentes Recentes</h2>
              <button
                onClick={() => navigate('/studio/agentes')}
                className="btn-ghost text-xs"
                aria-label="Ver todos os agentes"
              >
                Ver todos
              </button>
            </div>
            {recent.length === 0 ? (
              <div className="card flex flex-col items-center justify-center py-12">
                <Bot className="mb-3 h-10 w-10 text-zinc-600" aria-hidden="true" />
                <p className="text-sm text-zinc-500">Nenhum agente ainda</p>
                <p className="mb-4 text-xs text-zinc-600">Crie seu primeiro agente visual</p>
                <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
                  <Plus className="h-4 w-4" /> Criar Agente
                </button>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {recent.map(a => (
                  <div
                    key={a.agent_id}
                    onClick={() => navigate(`/studio/agentes/${a.agent_id}`)}
                    className="card-hover cursor-pointer"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <Bot className="h-5 w-5 text-cris-400" aria-hidden="true" />
                        <div>
                          <p className="font-medium">{a.name}</p>
                          <p className="text-xs text-zinc-500">{a.description || 'Sem descrição'}</p>
                        </div>
                      </div>
                      <StatusBadge status={a.status} />
                    </div>
                    <div className="mt-3 flex items-center gap-3 text-xs text-zinc-600">
                      <span>v{a.version}</span>
                      <span>{a.bindings?.length || 0} bindings</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {showCreate && (
        <CreateAgentModal
          onClose={() => setShowCreate(false)}
          onCreated={(id) => {
            setShowCreate(false)
            navigate(`/studio/agentes/${id}`)
          }}
        />
      )}
    </div>
  )
}