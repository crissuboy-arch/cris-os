import { useEffect, useState } from 'react'
import { Calendar, CheckCircle, Clock, Filter, ListTodo, Plus } from 'lucide-react'
import { api } from '../lib/api'
import { Link } from 'react-router-dom'

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
  criado_em?: string
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

const PRIORITY_BG: Record<string, string> = {
  alta: 'bg-red-500/10',
  media: 'bg-yellow-500/10',
  baixa: 'bg-zinc-500/10',
}

export default function Hoje() {
  const [tarefas, setTarefas] = useState<Tarefa[]>([])
  const [projetos, setProjetos] = useState<Projeto[]>([])
  const [filterProjeto, setFilterProjeto] = useState<string>('all')
  const [filterPrioridade, setFilterPrioridade] = useState<string>('all')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [t, p] = await Promise.all([
        api.tarefasHoje(),
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
      console.error('Erro ao carregar dados:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const concluir = async (id: number) => {
    try {
      await api.concluirTarefa(id)
      setTarefas(tarefas.filter(t => t.id !== id))
    } catch (e) {
      console.error('Erro ao concluir:', e)
    }
  }

  const filtered = tarefas.filter(t => {
    if (filterProjeto !== 'all' && String(t.projeto_id || '') !== filterProjeto) return false
    if (filterPrioridade !== 'all' && t.prioridade !== filterPrioridade) return false
    return true
  })

  const hoje = new Date().toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' })

  const totalHoje = filtered.length
  const totalAlta = filtered.filter(t => t.prioridade === 'alta').length
  const totalAtrasadas = filtered.filter(t => t.prazo && new Date(t.prazo) < new Date()).length

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Clock className="h-8 w-8 animate-pulse text-cris-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Hoje</h1>
          <p className="text-sm text-zinc-500">{hoje}</p>
        </div>
        <Link to="/tarefas" className="btn-primary">
          <Plus className="mr-1 h-4 w-4" /> Nova Tarefa
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card">
          <p className="text-xs text-zinc-500">Total de tarefas</p>
          <p className="mt-1 text-2xl font-bold">{totalHoje}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Alta prioridade</p>
          <p className="mt-1 text-2xl font-bold text-red-400">{totalAlta}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Atrasadas</p>
          <p className="mt-1 text-2xl font-bold text-orange-400">{totalAtrasadas}</p>
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
        <select
          className="input w-36"
          value={filterPrioridade}
          onChange={(e) => setFilterPrioridade(e.target.value)}
        >
          <option value="all">Todas as prioridades</option>
          <option value="alta">Alta</option>
          <option value="media">Média</option>
          <option value="baixa">Baixa</option>
        </select>
        <button className="btn-secondary" onClick={() => { setFilterProjeto('all'); setFilterPrioridade('all') }}>
          <Filter className="h-4 w-4" /> Limpar filtros
        </button>
      </div>

      <div className="card divide-y divide-zinc-800">
        {filtered.length === 0 && (
          <p className="py-8 text-center text-sm text-zinc-600">Nenhuma tarefa para hoje</p>
        )}
        {filtered.map((t) => (
          <div key={t.id} className="flex items-center justify-between py-3">
            <div className="flex items-center gap-3">
              <button
                onClick={() => concluir(t.id)}
                className="text-zinc-600 hover:text-cris-400"
              >
                <CheckCircle className="h-5 w-5" />
              </button>
              <div>
                <p className="text-sm font-medium text-zinc-200">{t.titulo}</p>
                <div className="flex items-center gap-2 text-xs text-zinc-500">
                  {t.projeto_nome && (
                    <>
                      <span className="flex items-center gap-1">
                        <ListTodo className="h-3 w-3" />
                        {t.projeto_nome}
                      </span>
                      <span>•</span>
                    </>
                  )}
                  <span className={`font-medium ${PRIORITY_COLORS[t.prioridade]}`}>
                    {t.prioridade}
                  </span>
                  {t.prazo && (
                    <>
                      <span>•</span>
                      <span className={new Date(t.prazo) < new Date() ? 'text-orange-400' : 'text-zinc-500'}>
                        <Clock className="h-3 w-3 inline mr-1" />
                        {new Date(t.prazo).toLocaleDateString('pt-BR')}
                      </span>
                    </>
                  )}
                  {t.responsavel && (
                    <>
                      <span>•</span>
                      <span>Responsável: {t.responsavel}</span>
                    </>
                  )}
                </div>
              </div>
            </div>
            <div className={`px-2 py-1 rounded ${PRIORITY_BG[t.prioridade]}`}>
              <span className={`text-xs font-medium ${PRIORITY_COLORS[t.prioridade]}`}>
                {t.prioridade}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="flex gap-2 text-xs text-zinc-500">
        <Calendar className="h-4 w-4" />
        <span>Última atualização: {new Date().toLocaleTimeString('pt-BR')}</span>
      </div>
    </div>
  )
}
