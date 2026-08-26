import { useEffect, useState } from 'react'
import { Clock, ListTodo, AlertCircle, Filter, Calendar, BarChart3 } from 'lucide-react'
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

export default function Aguardando() {
  const [tarefas, setTarefas] = useState<Tarefa[]>([])
  const [projetos, setProjetos] = useState<Projeto[]>([])
  const [filterProjeto, setFilterProjeto] = useState<string>('all')
  const [filterPrioridade, setFilterPrioridade] = useState<string>('all')
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
    if (filterPrioridade !== 'all' && t.prioridade !== filterPrioridade) return false
    return true
  })

  const bloqueadas = filtered.filter(t => t.agente && t.agente !== 'marketing' && t.agente !== 'social_media')
  const semResponsavel = filtered.filter(t => !t.responsavel)
  const semPrazo = filtered.filter(t => !t.prazo)
  const aguardandoConfirmacao = filtered.filter(t => t.status === 'pendente' && t.prazo)

  const totalBloqueadas = bloqueadas.length
  const totalSemResponsavel = semResponsavel.length
  const totalSemPrazo = semPrazo.length
  const totalAguardando = aguardandoConfirmacao.length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Aguardando</h1>
          <p className="text-sm text-zinc-500">
            Tarefas bloqueadas, sem responsável ou sem prazo
          </p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <div className="card">
          <p className="text-xs text-zinc-500">Bloqueadas</p>
          <p className="mt-1 text-2xl font-bold text-orange-400">{totalBloqueadas}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Sem responsável</p>
          <p className="mt-1 text-2xl font-bold text-yellow-400">{totalSemResponsavel}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Sem prazo</p>
          <p className="mt-1 text-2xl font-bold text-zinc-400">{totalSemPrazo}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Aguardando confirmação</p>
          <p className="mt-1 text-2xl font-bold text-blue-400">{totalAguardando}</p>
        </div>
      </div>

      <div className="flex gap-3">
        <select
          className="input w-40"
          value={filterProjeto}
          onChange={(e) => setFilterProjeto(e.target.value)}
        >
          <option value="all">Todos os projetos</option>
          {projetos.map(p => (
            <option key={p.id} value={String(p.id)}>{p.nome}</option>
          ))}
        </select>
        <select
          className="input w-32"
          value={filterPrioridade}
          onChange={(e) => setFilterPrioridade(e.target.value)}
        >
          <option value="all">Todas prioridades</option>
          <option value="alta">Alta</option>
          <option value="media">Média</option>
          <option value="baixa">Baixa</option>
        </select>
        <button
          className="btn-secondary"
          onClick={() => { setFilterProjeto('all'); setFilterPrioridade('all') }}
        >
          <Filter className="h-4 w-4" /> Limpar
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-zinc-600">Carregando...</p>
      ) : (
        <div className="space-y-6">
          {totalBloqueadas > 0 && (
            <div>
              <h2 className="text-sm font-medium text-orange-400 mb-2 flex items-center gap-2">
                <AlertCircle className="h-4 w-4" /> Bloqueadas
              </h2>
              <div className="card divide-y divide-zinc-800">
                {bloqueadas.map(t => (
                  <div key={t.id} className="flex items-center justify-between py-3">
                    <div className="flex items-center gap-3">
                      <AlertCircle className="h-4 w-4 text-orange-400" />
                      <div>
                        <p className="text-sm font-medium text-zinc-200">{t.titulo}</p>
                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                          {t.projeto_nome && <span>Projeto: {t.projeto_nome}</span>}
                          <AlertCircle className={`h-3 w-3 ${PRIORITY_COLORS[t.prioridade]}`} />
                          <span>{t.prioridade}</span>
                          {t.agente && <span>Agente: {t.agente}</span>}
                        </div>
                      </div>
                    </div>
                    <button
                      className="btn-ghost p-1"
                      onClick={() => concluir(t.id)}
                      title="Marcar como concluída"
                    >
                      <Clock className="h-4 w-4 text-zinc-500" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {totalSemResponsavel > 0 && (
            <div>
              <h2 className="text-sm font-medium text-yellow-400 mb-2 flex items-center gap-2">
                Sem responsável
              </h2>
              <div className="card divide-y divide-zinc-800">
                {semResponsavel.map(t => (
                  <div key={t.id} className="flex items-center justify-between py-3">
                    <div className="flex items-center gap-3">
                      <ListTodo className="h-4 w-4 text-yellow-400" />
                      <div>
                        <p className="text-sm font-medium text-zinc-200">{t.titulo}</p>
                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                          {t.projeto_nome && <span>{t.projeto_nome}</span>}
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
                      <Clock className="h-4 w-4 text-zinc-500" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {totalSemPrazo > 0 && (
            <div>
              <h2 className="text-sm font-medium text-zinc-500 mb-2 flex items-center gap-2">
                Sem prazo
              </h2>
              <div className="card divide-y divide-zinc-800">
                {semPrazo.map(t => (
                  <div key={t.id} className="flex items-center justify-between py-3">
                    <div className="flex items-center gap-3">
                      <Calendar className="h-4 w-4 text-zinc-500" />
                      <div>
                        <p className="text-sm font-medium text-zinc-200">{t.titulo}</p>
                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                          {t.projeto_nome && <span>{t.projeto_nome}</span>}
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
                      <Clock className="h-4 w-4 text-zinc-500" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {filtered.length === 0 && (
            <p className="text-center text-sm text-zinc-600 py-8">Nenhuma tarefa aguardando</p>
          )}
        </div>
      )}
    </div>
  )
}
