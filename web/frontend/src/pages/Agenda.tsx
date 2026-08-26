import { useEffect, useState } from 'react'
import { CalendarDays, Clock, ListTodo, Filter, CheckCircle, AlertCircle } from 'lucide-react'
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

export default function Agenda() {
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

  const hoje = new Date()
  const hojeStr = hoje.toISOString().split('T')[0]
  const fimSemana = new Date(hoje)
  fimSemana.setDate(hoje.getDate() + 7)

  const tarefasHoje = filtered.filter(t => t.prazo && t.prazo.split('T')[0] === hojeStr)
  const tarefasSemana = filtered.filter(t => {
    if (!t.prazo) return true
    const d = new Date(t.prazo)
    return d >= hoje && d <= fimSemana
  })
  const tarefasSemPrazo = filtered.filter(t => !t.prazo)
  const tarefasAtrasadas = filtered.filter(t => t.prazo && new Date(t.prazo) < hoje)

  const totalHoje = tarefasHoje.length
  const totalSemana = tarefasSemana.length
  const totalAtrasadas = tarefasAtrasadas.length
  const totalSemPrazo = tarefasSemPrazo.length

  const agruparPorData = (tarefas: Tarefa[]) => {
    const grupos: Record<string, Tarefa[]> = {}
    tarefas.forEach(t => {
      const data = t.prazo ? new Date(t.prazo).toISOString().split('T')[0] : 'sem-prazo'
      if (!grupos[data]) grupos[data] = []
      grupos[data].push(t)
    })
    return grupos
  }

  const grupos = agruparPorData(filtered)
  const datasOrdenadas = Object.keys(grupos).sort()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Agenda</h1>
          <p className="text-sm text-zinc-500">
            {hoje.toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' })}
          </p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <div className="card">
          <p className="text-xs text-zinc-500">Hoje</p>
          <p className="mt-1 text-2xl font-bold text-cris-400">{totalHoje}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Esta semana</p>
          <p className="mt-1 text-2xl font-bold text-blue-400">{totalSemana}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Atrasadas</p>
          <p className="mt-1 text-2xl font-bold text-orange-400">{totalAtrasadas}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Sem prazo</p>
          <p className="mt-1 text-2xl font-bold text-zinc-400">{totalSemPrazo}</p>
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
          {tarefasAtrasadas.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-red-400 mb-2 flex items-center gap-2">
                <Clock className="h-4 w-4" /> Atrasadas
              </h2>
              <div className="card divide-y divide-zinc-800">
                {tarefasAtrasadas.map(t => (
                  <div key={t.id} className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-3">
                      <CheckCircle
                        className="h-4 w-4 text-red-400 cursor-pointer hover:text-cris-400"
                        onClick={() => concluir(t.id)}
                      />
                      <div>
                        <p className="text-sm font-medium text-zinc-200">{t.titulo}</p>
                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                          {t.projeto_nome && <span>{t.projeto_nome}</span>}
                          <AlertCircle className={`h-3 w-3 ${PRIORITY_COLORS[t.prioridade]}`} />
                          <span>{t.prioridade}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tarefasHoje.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-cris-400 mb-2 flex items-center gap-2">
                <CalendarDays className="h-4 w-4" /> Hoje
              </h2>
              <div className="card divide-y divide-zinc-800">
                {tarefasHoje.map(t => (
                  <div key={t.id} className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-3">
                      <CheckCircle
                        className="h-4 w-4 text-zinc-600 cursor-pointer hover:text-cris-400"
                        onClick={() => concluir(t.id)}
                      />
                      <div>
                        <p className="text-sm font-medium text-zinc-200">{t.titulo}</p>
                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                          {t.projeto_nome && <span>{t.projeto_nome}</span>}
                          <AlertCircle className={`h-3 w-3 ${PRIORITY_COLORS[t.prioridade]}`} />
                          <span>{t.prioridade}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tarefasSemana.filter(t => !t.prazo || new Date(t.prazo) > hoje).length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-blue-400 mb-2 flex items-center gap-2">
                <CalendarDays className="h-4 w-4" /> Esta semana
              </h2>
              {datasOrdenadas.filter(d => d !== 'sem-prazo' && d !== hojeStr && new Date(d) > hoje && new Date(d) <= fimSemana).map(data => (
                <div key={data} className="mb-3">
                  <p className="text-xs text-zinc-500 mb-1">{new Date(data).toLocaleDateString('pt-BR')}</p>
                  <div className="card divide-y divide-zinc-800">
                    {grupos[data].filter(t => t.prazo && new Date(t.prazo) > hoje && new Date(t.prazo) <= fimSemana).map(t => (
                      <div key={t.id} className="flex items-center justify-between py-2">
                        <div className="flex items-center gap-3">
                          <CheckCircle
                            className="h-4 w-4 text-zinc-600 cursor-pointer hover:text-cris-400"
                            onClick={() => concluir(t.id)}
                          />
                          <div>
                            <p className="text-sm font-medium text-zinc-200">{t.titulo}</p>
                            <div className="flex items-center gap-2 text-xs text-zinc-500">
                              {t.projeto_nome && <span>{t.projeto_nome}</span>}
                              <AlertCircle className={`h-3 w-3 ${PRIORITY_COLORS[t.prioridade]}`} />
                              <span>{t.prioridade}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {tarefasSemPrazo.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-zinc-500 mb-2 flex items-center gap-2">
                <ListTodo className="h-4 w-4" /> Sem prazo definido
              </h2>
              <div className="card divide-y divide-zinc-800">
                {tarefasSemPrazo.map(t => (
                  <div key={t.id} className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-3">
                      <CheckCircle
                        className="h-4 w-4 text-zinc-600 cursor-pointer hover:text-cris-400"
                        onClick={() => concluir(t.id)}
                      />
                      <div>
                        <p className="text-sm font-medium text-zinc-200">{t.titulo}</p>
                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                          {t.projeto_nome && <span>{t.projeto_nome}</span>}
                          <AlertCircle className={`h-3 w-3 ${PRIORITY_COLORS[t.prioridade]}`} />
                          <span>{t.prioridade}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {filtered.length === 0 && (
            <p className="text-center text-sm text-zinc-600 py-8">Nenhuma tarefa na agenda</p>
          )}
        </div>
      )}
    </div>
  )
}
