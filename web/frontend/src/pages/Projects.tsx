import { useEffect, useState } from 'react'
import { Plus, Pencil, Trash2, FolderKanban } from 'lucide-react'
import { api } from '../lib/api'

export default function Projects() {
  const [items, setItems] = useState<any[]>([])
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [nome, setNome] = useState('')
  const [descricao, setDescricao] = useState('')

  const load = () => { api.projetos().then(setItems) }
  useEffect(() => { load() }, [])

  const resetForm = () => {
    setNome('')
    setDescricao('')
    setEditId(null)
    setShowForm(false)
  }

  const save = async () => {
    if (!nome) return
    if (editId) {
      await api.atualizarProjeto(editId, { nome, descricao })
    } else {
      await api.criarProjeto({ nome, descricao })
    }
    resetForm()
    load()
  }

  const edit = (item: any) => {
    setNome(item.nome)
    setDescricao(item.descricao)
    setEditId(item.id)
    setShowForm(true)
  }

  const remove = async (id: number) => {
    await api.excluirProjeto(id)
    load()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Projetos</h1>
          <p className="text-sm text-zinc-500">{items.length} projetos</p>
        </div>
        <button className="btn-primary" onClick={() => { resetForm(); setShowForm(true) }}>
          <Plus className="mr-1 h-4 w-4" /> Novo Projeto
        </button>
      </div>

      {showForm && (
        <div className="card space-y-3">
          <input className="input" placeholder="Nome do projeto" value={nome} onChange={(e) => setNome(e.target.value)} />
          <input className="input" placeholder="Descricao" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
          <div className="flex gap-2">
            <button className="btn-primary" onClick={save}>{editId ? 'Atualizar' : 'Criar'}</button>
            <button className="btn-secondary" onClick={resetForm}>Cancelar</button>
          </div>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {items.map((item) => (
          <div key={item.id} className="card-hover">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <FolderKanban className="h-5 w-5 text-orange-400" />
                <div>
                  <p className="font-medium">{item.nome}</p>
                  <p className="text-xs text-zinc-500">{item.descricao || 'Sem descricao'}</p>
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
            <div className="mt-2">
              <span className={`badge ${item.status === 'ativo' ? 'badge-green' : 'badge-zinc'}`}>
                {item.status}
              </span>
            </div>
          </div>
        ))}
        {items.length === 0 && !showForm && (
          <div className="col-span-2 py-12 text-center text-sm text-zinc-600">
            Nenhum projeto ainda. Crie o primeiro!
          </div>
        )}
      </div>
    </div>
  )
}
