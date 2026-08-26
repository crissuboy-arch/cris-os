import { useEffect, useState } from 'react'
import { Plus, CheckCircle, Trash2, AlertCircle, Clock, Filter, Search, ListTodo, Calendar, User } from 'lucide-react'
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

const STATUS_COLORS: Record<string, string> = {
  pendente: 'badge-yellow',
  concluida: 'badge-green',
  cancelada: 'badge-zinc',
  em_andamento: 'badge-blue',
}

const STATUS_LABELS: Record<string, string> = {
  pendente: 'Pendente',
  concluida: 'Concluída',
  cancelada: 'Cancelada',
  em_andamento: 'Em andamento',
}

export default function Tarefas() {
  const [items, setItems] = useState<Tarefa[]>([])
  const [projetos, setProjetos] = useState<Projeto[]>([])
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [titulo, setTitulo] = useState('')
  const [descricao, setDescricao] = useState('')
  const [prioridade, setPrioridade] = useState('media')
  const [prazo, setPrazo] = useState('')
  const [responsavel, setResponsavel] = useState('')
  const [projetoId, setProjetoId] = useState<number | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterStatus, setFilterStatus] = useState<string>('all')
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
      setItems(tarefasEnriquecidas)
      setProjetos(p)
    } catch (e) {
      console.error('Erro ao carregar:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const resetForm = () => {
    setTitulo('')
    setDescricao('')
    setPrioridade('media')
    setPrazo('')
    setResponsavel('')
    setProjetoId(null)
    setEditId(null)
    setShowForm(false)
  }

  const save = async () => {
    if (!titulo) return
    try {
      const data: any = { titulo, descricao, prioridade, prazo, responsavel }
      if (projetoId) data.projeto_id = projetoId
      if (editId) {
        await api.atualizarTarefa(editId, data)
      } else {
        await api.criarTarefa(data)
      }
      resetForm()
      load()
    } catch (e) {
      console.error('Erro ao salvar:', e)
    }
  }

  const edit = (item: Tarefa) => {
    setTitulo(item.titulo)
    setDescricao(item.descricao || '')
    setPrioridade(item.prioridade)
    setPrazo(item.prazo || '')
    setResponsavel(item.responsavel || '')
    setProjetoId(item.projeto_id || null)
    setEditId(item.id)
    setShowForm(true)
  }

  const concluir = async (id: number) => {
    try {
      await api.concluirTarefa(id)
      load()
    } catch (e) {
      console.error('Erro ao concluir:', e)
    }
  }

  const remove = async (id: number) => {
    if (!confirm('Excluir esta tarefa?')) return
    try {
      await api.excluirTarefa(id)
      load()
    } catch (e) {
      console.error('Erro ao excluir:', e)
    }
  }

  const filtered = items.filter(t => {
    const matchesSearch = t.titulo.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          (t.descricao || '').toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus = filterStatus === 'all' || t.status === filterStatus
    const matchesProjeto = filterProjeto === 'all' || String(t.projeto_id || '') === filterProjeto
    const matchesPrioridade = filterPrioridade === 'all' || t.prioridade === filterPrioridade
    return matchesSearch && matchesStatus && matchesProjeto && matchesPrioridade
  })

  const totalPendentes = items.filter(t => t.status === 'pendente').length
  const totalConcluidas = items.filter(t => t.status === 'concluida').length
  const totalAlta = items.filter(t => t.prioridade === 'alta').length
  const totalAtrasadas = items.filter(t => t.prazo && new Date(t.prazo) < new Date() && t.status !== 'concluida').length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Tarefas</h1>
          <p className="text-sm text-zinc-500">
            {totalPendentes} pendentes, {totalConcluidas} concluídas, {totalAlta} alta prioridade
          </p>
        </div>
        <button className="btn-primary" onClick={() => { resetForm(); setShowForm(true) }}>
          <Plus className="mr-1 h-4 w-4" /> Nova Tarefa
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <div className="card">
          <p className="text-xs text-zinc-500">Pendentes</p>
          <p className="mt-1 text-2xl font-bold text-yellow-400">{totalPendentes}</p>
        </div>
        <div className="card">
          <p className="text-xs text-zinc-500">Concluídas</p>
          <p className="mt-1 text-2xl font-bold text-cris-400">{totalConcluidas}</p>
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

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
          <input
            className="input pl-9"
            placeholder="Buscar tarefas..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <select
          className="input w-36"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
        >
          <option value="all">Todos os status</option>
          <option value="pendente">Pendente</option>
          <option value="concluida">Concluída</option>
          <option value="em_andamento">Em andamento</option>
        </select>
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
          onClick={() => {
            setSearchTerm('')
            setFilterStatus('all')
            setFilterProjeto('all')
            setFilterPrioridade('all')
          }}
        >
          <Filter className="h-4 w-4" /> Limpar
        </button>
      </div>

      {showForm && (
        <div className="card space-y-3">
          <input
            className="input"
            placeholder="Título da tarefa"
            value={titulo}
            onChange={(e) => setTitulo(e.target.value)}
            autoFocus
          />
          <input
            className="input"
            placeholder="Descrição"
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              className="input"
              value={prioridade}
              onChange={(e) => setPrioridade(e.target.value)}
            >
              <option value="alta">Alta</option>
              <option value="media">Média</option>
              <option value="baixa">Baixa</option>
            </select>
            <input
              type="date"
              className="input"
              value={prazo}
              onChange={(e) => setPrazo(e.target.value)}
            />
            <input
              className="input"
              placeholder="Responsável"
              value={responsavel}
              onChange={(e) => setResponsavel(e.target.value)}
            />
            <select
              className="input"
              value={projetoId || ''}
              onChange={(e) => setProjetoId(e.target.value ? parseInt(e.target.value) : null)}
            >
              <option value="">Sem projeto</option>
              {projetos.map(p => (
                <option key={p.id} value={p.id}>{p.nome}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-2">
            <button className="btn-primary" onClick={save}>
              {editId ? 'Atualizar' : 'Criar'}
            </button>
            <button className="btn-secondary" onClick={resetForm}>Cancelar</button>
          </div>
        </div>
      )}

      <div className="card divide-y divide-zinc-800">
        {loading ? (
          <p className="py-8 text-center text-sm text-zinc-600">Carregando...</p>
        ) : filtered.length === 0 ? (
          <p className="py-8 text-center text-sm text-zinc-600">Nenhuma tarefa encontrada</p>
        ) : (
          filtered.map((item) => (
            <div key={item.id} className="flex items-center justify-between py-3">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => concluir(item.id)}
                  className="text-zinc-600 hover:text-cris-400"
                >
                  <CheckCircle className="h-5 w-5" />
                </button>
                <div>
                  <div className="flex items-center gap-2">
                    <p className={`text-sm ${item.status === 'concluida' ? 'text-zinc-600 line-through' : 'text-zinc-200'}`}>
                      {item.titulo}
                    </p>
                    <AlertCircle className={`h-3 w-3 ${PRIORITY_COLORS[item.prioridade]}`} />
                  </div>
                  <div className="flex items-center gap-2 text-xs text-zinc-500">
                    {item.projeto_nome && (
                      <>
                        <ListTodo className="h-3 w-3" />
                        <span>{item.projeto_nome}</span>
                      </>
                    )}
                    {item.prazo && (
                      <>
                        <Clock className="h-3 w-3" />
                        <span>{new Date(item.prazo).toLocaleDateString('pt-BR')}</span>
                      </>
                    )}
                    {item.responsavel && (
                      <>
                        <User className="h-3 w-3" />
                        <span>{item.responsavel}</span>
                      </>
                    )}
                    {item.atualizado_em && (
                      <>
                        <Calendar className="h-3 w-3" />
                        <span>{new Date(item.atualizado_em).toLocaleTimeString('pt-BR')}</span>
                      </>
                    )}
                  </div>
                  <p className="text-xs text-zinc-600">{item.descricao}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`badge ${STATUS_COLORS[item.status] || 'badge-zinc'}`}>
                  {STATUS_LABELS[item.status] || item.status}
                </span>
                <button className="btn-ghost p-1" onClick={() => edit(item)}>
                  <Plus className="h-4 w-4" />
                </button>
                <button className="btn-ghost p-1" onClick={() => remove(item.id)}>
                  <Trash2 className="h-4 w-4 text-red-400" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
