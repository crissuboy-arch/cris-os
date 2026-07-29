import { useMemo, useState } from 'react'
import { Ban, Check, Search, Wrench } from 'lucide-react'
import { clsx } from 'clsx'
import type { StudioToolType } from '../../../../lib/api'
import type { AgentForm } from '../types'

interface Props {
  form: AgentForm
  setForm: React.Dispatch<React.SetStateAction<AgentForm>>
  toolTypes: StudioToolType[]
}

export default function SectionTools({ form, setForm, toolTypes }: Props) {
  const [search, setSearch] = useState('')

  const internal = toolTypes.find(t => t.type === 'internal')
  const filteredInternal = useMemo(() => {
    const items = internal?.items ?? []
    const q = search.toLowerCase()
    if (!q) return items
    return items.filter(t => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q))
  }, [internal, search])

  const toggle = (name: string) =>
    setForm(prev => ({
      ...prev,
      tools: {
        ...prev.tools,
        internal: prev.tools.internal.includes(name)
          ? prev.tools.internal.filter(n => n !== name)
          : [...prev.tools.internal, name],
      },
    }))

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Ferramentas</h2>
        <p className="text-sm text-zinc-500">
          Ferramentas que o agente pode usar. {form.tools.internal.length} internas selecionadas.
        </p>
      </div>

      {toolTypes.filter(t => !t.available).map(t => (
        <div key={t.type} className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4 opacity-60">
          <div className="flex items-center gap-2">
            <Ban className="h-4 w-4 text-zinc-600" aria-hidden="true" />
            <span className="text-sm font-medium">{t.label}</span>
            <span className="badge-zinc">ainda não configurado</span>
          </div>
          <p className="mt-1 text-xs text-zinc-500">{t.reason}</p>
        </div>
      ))}

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-zinc-400">
            {internal?.label ?? 'Ferramentas internas'}
            <span className="ml-2 text-xs text-zinc-600">({internal?.items.length ?? 0} disponíveis)</span>
          </h3>
        </div>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" aria-hidden="true" />
          <input
            className="input pl-9"
            placeholder="Buscar ferramenta..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Buscar ferramenta"
          />
        </div>

        {internal?.errors && internal.errors.length > 0 && (
          <p className="text-xs text-yellow-500/80">
            Alguns módulos não puderam ser lidos: {internal.errors.join('; ')}
          </p>
        )}

        {filteredInternal.length === 0 ? (
          <div className="card flex flex-col items-center py-10 text-center">
            <Wrench className="mb-2 h-8 w-8 text-zinc-600" aria-hidden="true" />
            <p className="text-sm text-zinc-500">
              {search ? `Nenhuma ferramenta encontrada para "${search}"` : 'Nenhuma ferramenta interna disponível'}
            </p>
          </div>
        ) : (
          <div className="grid gap-1 sm:grid-cols-2">
            {filteredInternal.map(t => {
              const isSelected = form.tools.internal.includes(t.name)
              return (
                <button
                  key={`${t.module}:${t.name}`}
                  type="button"
                  role="checkbox"
                  aria-checked={isSelected}
                  onClick={() => toggle(t.name)}
                  className={clsx(
                    'flex items-center gap-2 rounded-md border p-2 text-left transition-colors',
                    isSelected ? 'border-cris-500/50 bg-cris-500/5' : 'border-zinc-800 hover:border-zinc-700',
                  )}
                >
                  <span
                    className={clsx(
                      'flex h-4 w-4 shrink-0 items-center justify-center rounded border',
                      isSelected ? 'border-cris-500 bg-cris-500 text-white' : 'border-zinc-700',
                    )}
                    aria-hidden="true"
                  >
                    {isSelected && <Check className="h-3 w-3" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm">{t.name}</span>
                    <span className="block truncate text-xs text-zinc-500">{t.description}</span>
                  </span>
                  <span className="badge-zinc shrink-0 text-[10px]">{t.module.replace('_tools', '')}</span>
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
