import { useMemo, useState } from 'react'
import { AlertTriangle, Check, ChevronDown, ChevronUp, Search } from 'lucide-react'
import { clsx } from 'clsx'
import type { StudioCapability } from '../../../../lib/api'
import { isSensitive, type AgentForm } from '../types'

interface Props {
  form: AgentForm
  setForm: React.Dispatch<React.SetStateAction<AgentForm>>
  capabilities: StudioCapability[]
}

const HEALTH_DOT: Record<string, string> = {
  ok: 'bg-cris-400',
  degraded: 'bg-yellow-400',
  down: 'bg-red-400',
  unknown: 'bg-zinc-500',
}

export default function SectionCapabilities({ form, setForm, capabilities }: Props) {
  const [search, setSearch] = useState('')
  const [domain, setDomain] = useState('')
  const [plugin, setPlugin] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)

  const domains = useMemo(() => [...new Set(capabilities.map(c => c.domain))].sort(), [capabilities])
  const plugins = useMemo(() => [...new Set(capabilities.map(c => c.plugin))].sort(), [capabilities])

  const filtered = useMemo(() => capabilities.filter(c => {
    const q = search.toLowerCase()
    const matchQ = !q || c.name.toLowerCase().includes(q) || c.description.toLowerCase().includes(q)
    const matchD = !domain || c.domain === domain
    const matchP = !plugin || c.plugin === plugin
    return matchQ && matchD && matchP
  }), [capabilities, search, domain, plugin])

  const grouped = useMemo(() => {
    const map = new Map<string, StudioCapability[]>()
    for (const c of filtered) {
      const list = map.get(c.plugin) ?? []
      list.push(c)
      map.set(c.plugin, list)
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [filtered])

  const toggle = (name: string) =>
    setForm(prev => ({
      ...prev,
      selectedCapabilities: prev.selectedCapabilities.includes(name)
        ? prev.selectedCapabilities.filter(n => n !== name)
        : [...prev.selectedCapabilities, name],
    }))

  const selected = new Set(form.selectedCapabilities)
  const missing = form.selectedCapabilities.filter(n => !capabilities.some(c => c.name === n))

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Capabilities</h2>
        <p className="text-sm text-zinc-500">
          Selecione as capacidades que este agente pode usar. {form.selectedCapabilities.length} selecionadas.
        </p>
      </div>

      {missing.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400" role="alert">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <div>
            <p className="font-medium">Capabilities indisponíveis</p>
            <p className="text-xs">Estas capabilities estão salvas no agente mas não existem mais no registry: {missing.join(', ')}</p>
          </div>
        </div>
      )}

      <div className="space-y-2">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" aria-hidden="true" />
          <input
            className="input pl-9"
            placeholder="Buscar capability..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Buscar capability"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            className="input w-auto text-xs"
            value={domain}
            onChange={e => setDomain(e.target.value)}
            aria-label="Filtrar por domínio"
          >
            <option value="">Todos os domínios</option>
            {domains.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
          <select
            className="input w-auto text-xs"
            value={plugin}
            onChange={e => setPlugin(e.target.value)}
            aria-label="Filtrar por plugin"
          >
            <option value="">Todos os plugins</option>
            {plugins.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </div>

      {grouped.length === 0 ? (
        <div className="card flex flex-col items-center py-10 text-center">
          <Search className="mb-2 h-8 w-8 text-zinc-600" aria-hidden="true" />
          <p className="text-sm text-zinc-500">Nenhuma capability encontrada</p>
        </div>
      ) : (
        <div className="space-y-4">
          {grouped.map(([pluginName, caps]) => (
            <div key={pluginName}>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
                {pluginName} <span className="text-zinc-600">({caps.length})</span>
              </h3>
              <div className="space-y-1">
                {caps.map(c => {
                  const isSelected = selected.has(c.name)
                  const unavailable = c.health === 'down' || c.status !== 'active'
                  const isExpanded = expanded === c.name
                  return (
                    <div
                      key={c.name}
                      className={clsx(
                        'rounded-lg border transition-colors',
                        isSelected ? 'border-cris-500/50 bg-cris-500/5' : 'border-zinc-800',
                        unavailable && 'opacity-70',
                      )}
                    >
                      <div className="flex items-center gap-3 p-3">
                        <button
                          type="button"
                          role="checkbox"
                          aria-checked={isSelected}
                          aria-label={`Selecionar ${c.name}`}
                          onClick={() => toggle(c.name)}
                          className={clsx(
                            'flex h-5 w-5 shrink-0 items-center justify-center rounded border transition-colors',
                            isSelected ? 'border-cris-500 bg-cris-500 text-white' : 'border-zinc-700 hover:border-zinc-500',
                          )}
                        >
                          {isSelected && <Check className="h-3 w-3" />}
                        </button>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-sm">{c.name}</span>
                            <span className="badge-zinc">v{c.version}</span>
                            {isSensitive(c.name) && <span className="badge-yellow">sensível</span>}
                            {unavailable && (
                              <span className="badge-red flex items-center gap-1">
                                <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                                {c.status !== 'active' ? c.status : 'indisponível'}
                              </span>
                            )}
                          </div>
                          <p className="truncate text-xs text-zinc-500">{c.description}</p>
                        </div>
                        <span
                          className={clsx('h-2 w-2 shrink-0 rounded-full', HEALTH_DOT[c.health] ?? HEALTH_DOT.unknown)}
                          title={`health: ${c.health}`}
                          aria-label={`health ${c.health}`}
                          role="img"
                        />
                        <button
                          type="button"
                          onClick={() => setExpanded(isExpanded ? null : c.name)}
                          className="rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-100"
                          aria-label={isExpanded ? `Recolher detalhes de ${c.name}` : `Ver detalhes de ${c.name}`}
                          aria-expanded={isExpanded}
                        >
                          {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </button>
                      </div>
                      {isExpanded && (
                        <div className="space-y-2 border-t border-zinc-800 p-3 text-xs">
                          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                            <div><span className="text-zinc-600">Provider:</span> <span className="text-zinc-300">{c.plugin}</span></div>
                            <div><span className="text-zinc-600">Domínio:</span> <span className="text-zinc-300">{c.domain}</span></div>
                            <div><span className="text-zinc-600">Timeout:</span> <span className="text-zinc-300">{c.timeout_ms}ms</span></div>
                            <div><span className="text-zinc-600">Idempotente:</span> <span className="text-zinc-300">{c.idempotent ? 'sim' : 'não'}</span></div>
                          </div>
                          {c.input_schema?.properties && Object.keys(c.input_schema.properties).length > 0 && (
                            <div>
                              <p className="mb-1 text-zinc-600">Parâmetros de entrada:</p>
                              <div className="flex flex-wrap gap-1">
                                {Object.entries(c.input_schema.properties).map(([key, prop]) => (
                                  <span key={key} className={clsx('badge', c.input_schema?.required?.includes(key) ? 'badge-blue' : 'badge-zinc')}>
                                    {key}{prop.type ? `: ${prop.type}` : ''}{c.input_schema?.required?.includes(key) ? ' *' : ''}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
