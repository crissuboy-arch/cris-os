import { useEffect, useState } from 'react'
import { Plus, Trash2, Search } from 'lucide-react'
import { api } from '../lib/api'

export default function Memory() {
  const [items, setItems] = useState<any[]>([])
  const [newKey, setNewKey] = useState('')
  const [newVal, setNewVal] = useState('')
  const [search, setSearch] = useState('')

  const load = () => {
    api.memoria().then((m) => {
      setItems(m.preferencias || [])
    })
  }

  useEffect(load, [])

  const add = async () => {
    if (!newKey || !newVal) return
    await api.adicionarMemoria(newKey, newVal)
    setNewKey('')
    setNewVal('')
    load()
  }

  const remove = async (chave: string) => {
    await api.excluirMemoria(chave)
    load()
  }

  const filtered = items.filter(
    (i) =>
      i.chave.toLowerCase().includes(search.toLowerCase()) ||
      i.valor.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Memória</h1>
        <p className="text-sm text-zinc-500">Preferencias e contexto persistente</p>
      </div>

      <div className="flex gap-2">
        <input
          className="input flex-1"
          placeholder="Chave"
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
        />
        <input
          className="input flex-1"
          placeholder="Valor"
          value={newVal}
          onChange={(e) => setNewVal(e.target.value)}
        />
        <button className="btn-primary" onClick={add}>
          <Plus className="mr-1 h-4 w-4" /> Adicionar
        </button>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
        <input
          className="input pl-9"
          placeholder="Pesquisar na memoria..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="card">
        {filtered.length === 0 && (
          <p className="py-8 text-center text-sm text-zinc-600">Nenhum item na memoria</p>
        )}
        <div className="divide-y divide-zinc-800">
          {filtered.map((item) => (
            <div key={item.chave} className="flex items-center justify-between py-3">
              <div>
                <p className="text-sm font-medium text-zinc-300">{item.chave}</p>
                <p className="text-xs text-zinc-500">{item.valor}</p>
              </div>
              <button className="btn-ghost p-1" onClick={() => remove(item.chave)}>
                <Trash2 className="h-4 w-4 text-red-400" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
