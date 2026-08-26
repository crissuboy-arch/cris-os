import { useEffect, useState } from 'react'
import { Calendar, CheckCircle, Clock, ListTodo, Filter, BarChart3, AlertCircle, User } from 'lucide-react'
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
  status?: string
}

const PRIORITY_COLORS: Record<string, string> = {
  alta: 'text-red-400',
  media: 'text-yellow-400',
  baixa: 'text-zinc-500',
}

export default function RevisaoSemanal() {
  const [tarefas, setTarefas] = useState<Tarefa[]>([])
  const [projetos, setProjetos] = useState<Projeto[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedDate, setSelectedDate] = useState('')

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

  const hoje = new Date()
  const inicioSemana = new Date(hoje)
  inicioSemana.setDate(hoje.getDate() - hoje.getDay() + 1)
  const fimSemana = new Date(inicioSemana)
  fimSemana.setDate(inicioSemana.getDate() + 6)

  const tarefasDaSemana = tarefas.filter(t => {
    if (!t.prazo) return false
    const d = new Date(t.prazo)
    return d >= inicioSemana && d <= fimSemana
  })

  const tarefasConcluidas = tarefas.filter(t => {
    if (t.status !== 'concluida') return false
    if (!t.atualizado_em) return false
    const d = new Date(t.atualizado_em)
    return d >= inicioSemana && d <= fimSemana
  })

  const tarefasPendentes = tarefas.filter(t => t.status === 'pendente')
  const tarefasAtrasadas = tarefas.filter(t => t.prazo && new Date(t.prazo) < hoje && t.status !== 'concluida')

  const totalPlanejado = tarefasDaSemana.length
  const totalConcluido = tarefasConcluidas.length
  const totalPendente = tarefasPendentes.length
  const totalAtrasado = tarefasAtrasadas.length
  const taxaConclusao = totalPlanejado > 0 ? Math.round((totalConcluido / totalPlanejado) * 100) : 0

  const projetosAtivos = projetos.filter(p => p.status === 'ativo')
  const progressoProjetos = projetosAtivos.map(p => {
    const tarefasProj = tarefas.filter(t => t.projeto_id === p.id)
    const concluidas = tarefasProj.filter(t => t.status === 'concluida').length
    const total = tarefasProj.length
    const pct = total > 0 ? Math.round((concluidas / total) * 100) : 0
    return { ...p, total, concluidas, pct }
  })

  const agentesMaisUsados = tarefas
    .filter(t => t.agente)
    .reduce((acc: Record<string, number>, t) => {
      acc[t.agente!] = (acc[t.agente!] || 0) + 1
      return acc
    }, {})

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Revisão Semanal</h1>
          <p className="text-sm text-zinc-500">
            {inicioSemana.toLocaleDateString('pt-BR')} - {fimSemana.toLocaleDateString('pt-BR')}
          </p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <div className="card">
          <p className="text-xs text-zinc-500">Planejado</p>
          <p className="mt-1 text-2xl font-bold text-blue-400">{totalPlanejado}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Concluído</p>
          <p className="mt-1 text-2xl font-bold text-cris-400">{totalConcluido}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Taxa de conclusão</p>
          <p className="mt-1 text-2xl font-bold">{taxaConclusao}%</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Atrasadas</p>
          <p className="mt-1 text-2xl font-bold text-orange-400">{totalAtrasado}</p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card">
          <h3 className="mb-3 text-sm font-medium text-zinc-400">Progresso dos Projetos</h3>
          <div className="space-y-3">
            {progressoProjetos.map(p => (
              <div key={p.id}>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">{p.nome}</span>
                  <span className="text-zinc-500">{p.pct}% ({p.concluidas}/{p.total})</span>
                </div>
                <div className="mt-1 h-2 rounded bg-zinc-800">
                  <div
                    className="h-2 rounded bg-cris-500/50 transition-all"
                    style={{ width: `${p.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h3 className="mb-3 text-sm font-medium text-zinc-400">Estatísticas</h3>
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Tarefas pendentes</span>
              <span className="text-zinc-400">{totalPendente}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Tarefas concluídas esta semana</span>
              <span className="text-cris-400">{totalConcluido}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Projetos ativos</span>
              <span className="text-zinc-400">{projetosAtivos.length}</span>
            </div>
            {Object.keys(agentesMaisUsados).length > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-zinc-500">Agente mais usado</span>
                <span className="text-zinc-400">
                  {Object.entries(agentesMaisUsados).sort((a, b) => b[1] - a[1])[0][0]}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-zinc-600">Carregando...</p>
      ) : (
        <div className="space-y-6">
          {tarefasAtrasadas.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-orange-400 mb-2 flex items-center gap-2">
                <Clock className="h-4 w-4" /> Atrasadas
              </h2>
              <div className="card divide-y divide-zinc-800">
                {tarefasAtrasadas.map(t => (
                  <div key={t.id} className="flex items-center justify-between py-3">
                    <div className="flex items-center gap-3">
                      <AlertCircle className="h-4 w-4 text-orange-400" />
                      <div>
                        <p className="text-sm font-medium text-zinc-200">{t.titulo}</p>
                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                          {t.projeto_nome && <span>{t.projeto_nome}</span>}
                          <Calendar className="h-3 w-3" />
                          <span>Venceu: {new Date(t.prazo!).toLocaleDateString('pt-BR')}</span>
                        </div>
                      </div>
                    </div>
                    <button
                      className="btn-ghost p-1"
                      onClick={() => concluir(t.id)}
                    >
                      <CheckCircle className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tarefasPendentes.slice(0, 10).length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-yellow-400 mb-2 flex items-center gap-2">
                <ListTodo className="h-4 w-4" /> Pendentes (top 10)
              </h2>
              <div className="card divide-y divide-zinc-800">
                {tarefasPendentes.slice(0, 10).map(t => (
                  <div key={t.id} className="flex items-center justify-between py-3">
                    <div className="flex items-center gap-3">
                      <AlertCircle className={`h-4 w-4 ${PRIORITY_COLORS[t.prioridade]}`} />
                      <div>
                        <p className="text-sm font-medium text-zinc-200">{t.titulo}</p>
                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                          {t.projeto_nome && <span>{t.projeto_nome}</span>}
                          <span>{t.prioridade}</span>
                          {t.agente && <span>Agente: {t.agente}</span>}
                        </div>
                      </div>
                    </div>
                    <button
                      className="btn-ghost p-1"
                      onClick={() => concluir(t.id)}
                    >
                      <CheckCircle className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
