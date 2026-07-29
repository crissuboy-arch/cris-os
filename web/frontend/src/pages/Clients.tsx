import { useEffect, useState } from 'react'
import { Plus, Pencil, Trash2, Users } from 'lucide-react'
import { api } from '../lib/api'

export default function Clients() {
  const [items, setItems] = useState<any[]>([])
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [nome, setNome] = useState('')
  const [empresa, setEmpresa] = useState('')
  const [telefone, setTelefone] = useState('')
  const [email, setEmail] = useState('')

  const load = () => { api.clientes().then(setItems) }
  useEffect(() => { load() }, [])

  const resetForm = () => {
    setNome('')
    setEmpresa('')
    setTelefone('')
    setEmail('')
    setEditId(null)
    setShowForm(false)
  }

  const save = async () => {
    if (!nome) return
    const data = { nome, empresa, telefone, email, observacoes: '' }
    if (editId) {
      await api.atualizarCliente(editId, data)
    } else {
      await api.criarCliente(data)
    }
    resetForm()
    load()
  }

  const edit = (item: any) => {
    setNome(item.nome)
    setEmpresa(item.empresa)
    setTelefone(item.telefone)
    setEmail(item.email)
    setEditId(item.id)
    setShowForm(true)
  }

  const remove = async (id: number) => {
    await api.excluirCliente(id)
    load()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Clientes</h1>
          <p className="text-sm text-zinc-500">{items.length} clientes</p>
        </div>
        <button className="btn-primary" onClick={() => { resetForm(); setShowForm(true) }}>
          <Plus className="mr-1 h-4 w-4" /> Novo Cliente
        </button>
      </div>

      {showForm && (
        <div className="card space-y-3">
          <input className="input" placeholder="Nome" value={nome} onChange={(e) => setNome(e.target.value)} />
          <input className="input" placeholder="Empresa" value={empresa} onChange={(e) => setEmpresa(e.target.value)} />
          <input className="input" placeholder="Telefone" value={telefone} onChange={(e) => setTelefone(e.target.value)} />
          <input className="input" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <div className="flex gap-2">
            <button className="btn-primary" onClick={save}>{editId ? 'Atualizar' : 'Criar'}</button>
            <button className="btn-secondary" onClick={resetForm}>Cancelar</button>
          </div>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <div key={item.id} className="card-hover">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <Users className="h-5 w-5 text-blue-400" />
                <div>
                  <p className="font-medium">{item.nome}</p>
                  <p className="text-xs text-zinc-500">{item.empresa || '—'}</p>
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
            <div className="mt-2 space-y-1 text-xs text-zinc-500">
              {item.telefone && <p>📞 {item.telefone}</p>}
              {item.email && <p>✉️ {item.email}</p>}
            </div>
          </div>
        ))}
        {items.length === 0 && !showForm && (
          <div className="col-span-3 py-12 text-center text-sm text-zinc-600">
            Nenhum cliente cadastrado.
          </div>
        )}
      </div>
    </div>
  )
}
