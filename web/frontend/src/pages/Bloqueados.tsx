import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle, ListTodo, Filter, Calendar, BarChart3, AlertCircle } from 'lucide-react'
import { api } from '../lib/api'

interface Tarefa {
  id: number
  titulo: string
  descricao?: string
  prioridade: string
  prazo?: string
  responsavel?: string
  status: string
  projeto_id?: number
  projeto_nome?: string
  agente?: string
  atualizado_em?: string
}

interface Projeto {
  id: number
  nome: string
}

const PRIORITY_COLORS: Record<string, string> = {
  alta: 'text-red-400',
  media: 'text-yellow-400',
  baixa: 'text-zinc-500',
}

export default function Bloqueados() {
  const [tarefas, setTarefas] = useState<Tarefa[]>([])
  const [projetos, setProjetos] = useState<Projeto[]>([])
  const [filterProjeto, setFilterProjeto] = useState<string>('all')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [t, p] = await Promise.all([
        api.tarefas(),
        api.projetos(),
      ])
      const projetosMap = new Map(p.map(proj => [proj.id, proj.nome]))
      const tarefasEnriquecidas = t.map(tarefa => ({
        ...tarefa,
        projeto_nome: tarefa.projeto_id ? projetosMap.get(tarefa.projeto_id) : undefined,
      }))
      setTarefas(tarefasEnriquecidas)
      setProjetos(p)
    } catch (e) {
      console.error('Erro:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const concluir = async (id: number) => {
    try {
      await api.concluirTarefa(id)
      load()
    } catch (e) {
      console.error('Erro:', e)
    }
  }

  const filtered = tarefas.filter(t => {
    if (t.status === 'concluida') return false
    if (filterProjeto !== 'all' && String(t.projeto_id || '') !== filterProjeto) return false
    return true
  })

  const hoje = new Date()
  const bloqueadas = filtered.filter(t => {
    if (t.prazo && new Date(t.prazo) < hoje) return true
    if (t.prioridade === 'alta' && !t.responsavel) return true
    if (t.prioridade === 'alta' && !t.prazo) return true
    return false
  })

  const atrasadas = filtered.filter(t => t.prazo && new Date(t.prazo) < hoje && t.status !== 'concluida')
  const criticas = filtered.filter(t => t.prioridade === 'alta')

  const totalBloqueadas = bloqueadas.length
  const totalAtrasadas = atrasadas.length
  const totalCriticas = criticas.length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Bloqueados</h1>
          <p className="text-sm text-zinc-500">
            Tarefas críticas, atrasadas ou sem prazo/responsável
          </p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card">
          <p className="text-xs text-zinc-500">Críticas</p>
          <p className="mt-1 text-2xl font-bold text-red-400">{totalCriticas}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Atrasadas</p>
          <p className="mt-1 text-2xl font-bold text-orange-400">{totalAtrasadas}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Bloqueadas</p>
          <p className="mt-1 text-2xl font-bold text-yellow-400">{totalBloqueadas}</p>
        </div>
      </div>

      <div className="flex gap-3">
        <select
          className="input w-48"
          value={filterProjeto}
          onChange={(e) => setFilterProjeto(e.target.value)}
        >
          <option value="all">Todos os projetos</option>
          {projetos.map(p => (
            <option key={p.id} value={String(p.id)}>{p.nome}</option>
          ))}
        </select>
        <button
          className="btn-secondary"
          onClick={() => setFilterProjeto('all')}
        >
          <Filter className="h-4 w-4" /> Limpar
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-zinc-600">Carregando...</p>
      ) : (
        <div className="space-y-6">
          {atrasadas.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-orange-400 mb-2 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" /> Atrasadas
              </h2>
              <div className="card divide-y divide-zinc-800">
                {atrasadas.map(t => (
                  <div key={t.id} className="flex items-center justify-between py-3">
                    <div className="flex items-center gap-3">
                      <AlertTriangle className="h-4 w-4 text-orange-400" />
                      <div>
                        <p className="text-sm font-medium text-zinc-200">{t.titulo}</p>
                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                          {t.projeto_nome && <span>{t.projeto_nome}</span>}
                          <Calendar className="h-3 w-3" />
                          <span className="text-orange-400">
                            Venceu: {new Date(t.prazo!).toLocaleDateString('pt-BR')}
                          </span>
                          <AlertCircle className={`h-3 w-3 ${PRIORITY_COLORS[t.prioridade]}`} />
                          <span>{t.prioridade}</span>
                        </div>
                      </div>
                    </div>
                    <button
                      className="btn-ghost p-1"
                      onClick={() => concluir(t.id)}
                      title="Marcar como concluída"
                    >
                      <CheckCircle className="h-4 w-4 text-zinc-500" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {bloqueadas.filter(t => !t.prazo || new Date(t.prazo) >= hoje).length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-yellow-400 mb-2 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" /> Críticas sem prazo
              </h2>
              <div className="card divide-y divide-zinc-800">
                {bloqueadas.filter(t => !t.prazo || new Date(t.prazo) >= hoje).map(t => (
                  <div key={t.id} className="flex items-center justify-between py-3">
                    <div className="flex items-center gap-3">
                      <AlertTriangle className="h-4 w-4 text-yellow-400" />
                      <div>
                        <p className="text-sm font-medium text-zinc-200">{t.titulo}</p>
                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                          {t.projeto_nome && <span>{t.projeto_nome}</span>}
                          <AlertCircle className={`h-3 w-3 ${PRIORITY_COLORS[t.prioridade]}`} />
                          <span>{t.prioridade}</span>
                          {!t.prazo && <span className="text-zinc-600">Sem prazo</span>}
                        </div>
                      </div>
                    </div>
                    <button
                      className="btn-ghost p-1"
                      onClick={() => concluir(t.id)}
                      title="Marcar como concluída"
                    >
                      <CheckCircle className="h-4 w-4 text-zinc-500" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {bloqueadas.length === 0 && (
            <p className="text-center text-sm text-zinc-600 py-8">Nenhuma tarefa bloqueada</p>
          )}
        </div>
      )}
    </div>
  )
}
