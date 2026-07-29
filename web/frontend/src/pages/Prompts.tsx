import { useEffect, useState } from 'react'
import { Plus, Star, Trash2, Search, FileText } from 'lucide-react'
import { api } from '../lib/api'

export default function Prompts() {
  const [items, setItems] = useState<any[]>([])
  const [showForm, setShowForm] = useState(false)
  const [titulo, setTitulo] = useState('')
  const [conteudo, setConteudo] = useState('')
  const [categoria, setCategoria] = useState('')
  const [search, setSearch] = useState('')

  const load = () => { api.prompts().then(setItems) }
  useEffect(() => { load() }, [])

  const save = async () => {
    if (!titulo || !conteudo) return
    await api.criarPrompt({ titulo, conteudo, categoria })
    setTitulo('')
    setConteudo('')
    setCategoria('')
    setShowForm(false)
    load()
  }

  const toggleFav = async (id: number) => {
    await api.alternarFavorito(id)
    load()
  }

  const remove = async (id: number) => {
    await api.excluirPrompt(id)
    load()
  }

  const filtered = items.filter(
    (p) =>
      p.titulo.toLowerCase().includes(search.toLowerCase()) ||
      p.conteudo.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Prompts</h1>
          <p className="text-sm text-zinc-500">{items.length} prompts salvos</p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm(true)}>
          <Plus className="mr-1 h-4 w-4" /> Novo Prompt
        </button>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
        <input
          className="input pl-9"
          placeholder="Pesquisar prompts..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {showForm && (
        <div className="card space-y-3">
          <input className="input" placeholder="Titulo" value={titulo} onChange={(e) => setTitulo(e.target.value)} />
          <textarea className="input min-h-[100px] resize-y" placeholder="Conteudo do prompt" value={conteudo} onChange={(e) => setConteudo(e.target.value)} />
          <input className="input" placeholder="Categoria (opcional)" value={categoria} onChange={(e) => setCategoria(e.target.value)} />
          <div className="flex gap-2">
            <button className="btn-primary" onClick={save}>Salvar</button>
            <button className="btn-secondary" onClick={() => setShowForm(false)}>Cancelar</button>
          </div>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {filtered.map((item) => (
          <div key={item.id} className="card-hover">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-blue-400" />
                <div>
                  <p className="font-medium">{item.titulo}</p>
                  {item.categoria && <p className="text-xs text-zinc-500">{item.categoria}</p>}
                </div>
              </div>
              <div className="flex gap-1">
                <button className="btn-ghost p-1" onClick={() => toggleFav(item.id)}>
                  <Star className={`h-4 w-4 ${item.favorito ? 'text-yellow-400 fill-yellow-400' : 'text-zinc-600'}`} />
                </button>
                <button className="btn-ghost p-1" onClick={() => remove(item.id)}>
                  <Trash2 className="h-4 w-4 text-red-400" />
                </button>
              </div>
            </div>
            <p className="mt-2 line-clamp-3 text-xs text-zinc-500">{item.conteudo}</p>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="col-span-2 py-12 text-center text-sm text-zinc-600">
            Nenhum prompt encontrado.
          </div>
        )}
      </div>
    </div>
  )
}
