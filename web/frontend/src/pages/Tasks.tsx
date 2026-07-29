import { useEffect, useState } from 'react'
import { Plus, CheckCircle, Trash2, AlertCircle, Circle } from 'lucide-react'
import { api } from '../lib/api'

const PRIORITY_COLORS: Record<string, string> = {
  alta: 'text-red-400',
  media: 'text-yellow-400',
  baixa: 'text-zinc-500',
}

export default function Tasks() {
  const [items, setItems] = useState<any[]>([])
  const [showForm, setShowForm] = useState(false)
  const [titulo, setTitulo] = useState('')
  const [prioridade, setPrioridade] = useState('media')

  const load = () => { api.tarefas().then(setItems) }
  useEffect(() => { load() }, [])

  const save = async () => {
    if (!titulo) return
    await api.criarTarefa({ titulo, prioridade })
    setTitulo('')
    setPrioridade('media')
    setShowForm(false)
    load()
  }

  const concluir = async (id: number) => {
    await api.concluirTarefa(id)
    load()
  }

  const remove = async (id: number) => {
    await api.excluirTarefa(id)
    load()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Tarefas</h1>
          <p className="text-sm text-zinc-500">{items.length} tarefas</p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm(true)}>
          <Plus className="mr-1 h-4 w-4" /> Nova Tarefa
        </button>
      </div>

      {showForm && (
        <div className="card flex gap-2">
          <input
            className="input flex-1"
            placeholder="O que precisa ser feito?"
            value={titulo}
            onChange={(e) => setTitulo(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && save()}
            autoFocus
          />
          <select className="input w-32" value={prioridade} onChange={(e) => setPrioridade(e.target.value)}>
            <option value="alta">Alta</option>
            <option value="media">Media</option>
            <option value="baixa">Baixa</option>
          </select>
          <button className="btn-primary" onClick={save}>Adicionar</button>
          <button className="btn-secondary" onClick={() => setShowForm(false)}>X</button>
        </div>
      )}

      <div className="card divide-y divide-zinc-800">
        {items.length === 0 && (
          <p className="py-8 text-center text-sm text-zinc-600">Nenhuma tarefa</p>
        )}
        {items.map((item) => (
          <div key={item.id} className="flex items-center justify-between py-3">
            <div className="flex items-center gap-3">
              <button onClick={() => concluir(item.id)} className="text-zinc-600 hover:text-cris-400">
                <Circle className="h-5 w-5" />
              </button>
              <div>
                <p className={`text-sm ${item.status === 'concluida' ? 'text-zinc-600 line-through' : 'text-zinc-200'}`}>
                  {item.titulo}
                </p>
                {item.prazo && <p className="text-xs text-zinc-600">Prazo: {item.prazo}</p>}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <AlertCircle className={`h-4 w-4 ${PRIORITY_COLORS[item.prioridade] || 'text-zinc-500'}`} />
              <button className="btn-ghost p-1" onClick={() => remove(item.id)}>
                <Trash2 className="h-4 w-4 text-red-400" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
