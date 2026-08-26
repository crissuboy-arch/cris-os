import { useEffect, useState } from 'react'
import { FolderKanban, Plus, Pencil, Trash2, Calendar, CheckCircle, Clock, ListTodo, BarChart3 } from 'lucide-react'
import { api } from '../lib/api'

interface Projeto {
  id: number
  nome: string
  descricao?: string
  status: string
  contexto?: string
  criado_em?: string
  atualizado_em?: string
}

interface Tarefa {
  id: number
  titulo: string
  prioridade: string
  prazo?: string
  status: string
  projeto_id?: number
}

export default function Projetos() {
  const [items, setItems] = useState<Projeto[]>([])
  const [tarefasPorProjeto, setTarefasPorProjeto] = useState<Record<number, Tarefa[]>>({})
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [nome, setNome] = useState('')
  const [descricao, setDescricao] = useState('')
  const [contexto, setContexto] = useState('')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const p = await api.projetos()
      setItems(p)
      const t = await api.tarefas()
      const map: Record<number, Tarefa[]> = {}
      t.forEach(tarefa => {
        if (tarefa.projeto_id) {
          if (!map[tarefa.projeto_id]) map[tarefa.projeto_id] = []
          map[tarefa.projeto_id].push(tarefa)
        }
      })
      setTarefasPorProjeto(map)
    } catch (e) {
      console.error('Erro ao carregar:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const resetForm = () => {
    setNome('')
    setDescricao('')
    setContexto('')
    setEditId(null)
    setShowForm(false)
  }

  const save = async () => {
    if (!nome) return
    try {
      if (editId) {
        await api.atualizarProjeto(editId, { nome, descricao, contexto })
      } else {
        await api.criarProjeto({ nome, descricao, contexto })
      }
      resetForm()
      load()
    } catch (e) {
      console.error('Erro ao salvar:', e)
    }
  }

  const edit = (item: Projeto) => {
    setNome(item.nome)
    setDescricao(item.descricao || '')
    setContexto(item.contexto || '')
    setEditId(item.id)
    setShowForm(true)
  }

  const remove = async (id: number) => {
    if (!confirm('Excluir este projeto?')) return
    try {
      await api.excluirProjeto(id)
      load()
    } catch (e) {
      console.error('Erro ao excluir:', e)
    }
  }

  const totalProjetos = items.filter(p => p.status === 'ativo').length
  const totalTarefas = Object.values(tarefasPorProjeto).flat().length
  const totalPendentes = Object.values(tarefasPorProjeto).flat().filter(t => t.status === 'pendente').length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Projetos</h1>
          <p className="text-sm text-zinc-500">
            {totalProjetos} ativos, {totalTarefas} tarefas, {totalPendentes} pendentes
          </p>
        </div>
        <button className="btn-primary" onClick={() => { resetForm(); setShowForm(true) }}>
          <Plus className="mr-1 h-4 w-4" /> Novo Projeto
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card">
          <p className="text-xs text-zinc-500">Projetos ativos</p>
          <p className="mt-1 text-2xl font-bold text-cris-400">{totalProjetos}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Total de tarefas</p>
          <p className="mt-1 text-2xl font-bold text-yellow-400">{totalTarefas}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Pendentes</p>
          <p className="mt-1 text-2xl font-bold text-orange-400">{totalPendentes}</p>
        </div>
      </div>

      {showForm && (
        <div className="card space-y-3">
          <input
            className="input"
            placeholder="Nome do projeto"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            autoFocus
          />
          <input
            className="input"
            placeholder="Descrição"
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
          />
          <textarea
            className="input min-h-20"
            placeholder="Contexto do projeto"
            value={contexto}
            onChange={(e) => setContexto(e.target.value)}
          />
          <div className="flex gap-2">
            <button className="btn-primary" onClick={save}>
              {editId ? 'Atualizar' : 'Criar'}
            </button>
            <button className="btn-secondary" onClick={resetForm}>Cancelar</button>
          </div>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {loading ? (
          <p className="col-span-2 py-8 text-center text-sm text-zinc-600">Carregando...</p>
        ) : items.length === 0 ? (
          <p className="col-span-2 py-12 text-center text-sm text-zinc-600">Nenhum projeto ainda. Crie o primeiro!</p>
        ) : (
          items.map((item) => {
            const tarefas = tarefasPorProjeto[item.id] || []
            const pendentes = tarefas.filter(t => t.status === 'pendente')
            const atrasadas = tarefas.filter(t => t.prazo && new Date(t.prazo) < new Date() && t.status !== 'concluida')
            const progresso = tarefas.length > 0 ? Math.round((tarefas.filter(t => t.status === 'concluida').length / tarefas.length) * 100) : 0

            return (
              <div key={item.id} className="card-hover">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <FolderKanban className="h-5 w-5 text-orange-400" />
                    <div>
                      <p className="font-medium">{item.nome}</p>
                      <p className="text-xs text-zinc-500">{item.descricao || 'Sem descrição'}</p>
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <button className="btn-ghost p-1" onClick={() => edit(item)}>
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button className="btn-ghost p-1" onClick={() => remove(item.id)}>
                      <Trash2 className="h-4 w-4 text-red-400" />
                    </button>
                  </div>
                </div>

                <div className="mt-3 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-zinc-500">Progresso</span>
                    <span className="text-zinc-400">{progresso}%</span>
                  </div>
                  <div className="h-2 rounded bg-zinc-800">
                    <div
                      className="h-2 rounded bg-cris-500/50 transition-all"
                      style={{ width: `${progresso}%` }}
                    />
                  </div>

                  <div className="flex items-center gap-3 text-xs text-zinc-500">
                    <span className="flex items-center gap-1">
                      <ListTodo className="h-3 w-3" />
                      {tarefas.length}
                    </span>
                    <span className="flex items-center gap-1 text-yellow-400">
                      <Clock className="h-3 w-3" />
                      {pendentes.length} pendentes
                    </span>
                    {atrasadas.length > 0 && (
                      <span className="flex items-center gap-1 text-orange-400">
                        <Calendar className="h-3 w-3" />
                        {atrasadas.length} atrasadas
                      </span>
                    )}
                  </div>

                  {tarefas.slice(0, 3).map((t) => (
                    <div key={t.id} className="text-xs text-zinc-400 truncate">
                      • {t.titulo}
                    </div>
                  ))}
                  {tarefas.length > 3 && (
                    <div className="text-xs text-zinc-600">+{tarefas.length - 3} mais</div>
                  )}
                </div>

                <div className="mt-2 flex items-center justify-between text-xs text-zinc-500">
                  <span className={`badge ${item.status === 'ativo' ? 'badge-green' : 'badge-zinc'}`}>
                    {item.status}
                  </span>
                  {item.atualizado_em && (
                    <span>Atualizado: {new Date(item.atualizado_em).toLocaleTimeString('pt-BR')}</span>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
