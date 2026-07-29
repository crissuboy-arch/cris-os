import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bot, Plus, Search, Trash2, FileEdit, Activity,
} from 'lucide-react'
import { studioApi, type StudioAgent } from '../../lib/api'
import CreateAgentModal from './CreateAgentModal'
import StatusBadge from '../../components/StatusBadge'

export default function StudioAgentList() {
  const [agents, setAgents] = useState<StudioAgent[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    setLoading(true)
    studioApi.list()
      .then(setAgents)
      .catch(() => setAgents([]))
      .finally(() => setLoading(false))
  }, [])

  const filtered = agents.filter(a =>
    a.name.toLowerCase().includes(search.toLowerCase()) ||
    a.description?.toLowerCase().includes(search.toLowerCase())
  )

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Remover "${name}"? Esta ação é irreversível.`)) return
    setDeleting(id)
    try {
      await studioApi.delete(id)
      setAgents(prev => prev.filter(a => a.agent_id !== id))
    } catch {
      alert('Erro ao remover agente')
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Meus Agentes</h1>
          <p className="text-sm text-zinc-500">{agents.length} agentes criados</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> Novo Agente
        </button>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" aria-hidden="true" />
        <input
          className="input pl-9"
          placeholder="Buscar agentes..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {loading ? (
        <div className="flex h-48 items-center justify-center">
          <Activity className="h-8 w-8 animate-pulse text-cris-500" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-16">
          {search ? (
            <>
              <Search className="mb-3 h-10 w-10 text-zinc-600" aria-hidden="true" />
              <p className="text-sm text-zinc-500">Nenhum agente encontrado para "{search}"</p>
            </>
          ) : (
            <>
              <Bot className="mb-3 h-10 w-10 text-zinc-600" aria-hidden="true" />
              <p className="text-sm text-zinc-500">Nenhum agente ainda</p>
              <p className="mb-4 text-xs text-zinc-600">Crie seu primeiro agente visual</p>
              <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
                <Plus className="h-4 w-4" /> Criar Agente
              </button>
            </>
          )}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map(a => (
            <div key={a.agent_id} className="card group relative">
              <div
                onClick={() => navigate(`/studio/agentes/${a.agent_id}`)}
                className="cursor-pointer"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <Bot className="h-5 w-5 text-cris-400" aria-hidden="true" />
                    <div>
                      <p className="font-medium">{a.name}</p>
                      <p className="text-xs text-zinc-500 line-clamp-2">
                        {a.description || 'Sem descrição'}
                      </p>
                    </div>
                  </div>
                  <StatusBadge status={a.status} />
                </div>
                <div className="mt-3 flex items-center gap-3 text-xs text-zinc-600">
                  <span>v{a.version}</span>
                  <span>{a.bindings?.length || 0} bindings</span>
                  <span>{new Date(a.updated_at).toLocaleDateString('pt-BR')}</span>
                </div>
              </div>

              <div className="absolute right-3 top-3 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                <button
                  onClick={(e) => { e.stopPropagation(); navigate(`/studio/agentes/${a.agent_id}`) }}
                  className="rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-100"
                  aria-label={`Editar ${a.name}`}
                >
                  <FileEdit className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(a.agent_id, a.name) }}
                  className="rounded p-1 text-zinc-500 hover:bg-red-500/20 hover:text-red-400 disabled:opacity-50"
                  aria-label={`Remover ${a.name}`}
                  disabled={deleting === a.agent_id}
                >
                  {deleting === a.agent_id
                    ? <Activity className="h-3.5 w-3.5 animate-spin" />
                    : <Trash2 className="h-3.5 w-3.5" />
                  }
                </button>
              </div>
            </div>
          ))}
        </div>
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