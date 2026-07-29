import { AlertTriangle, Check, Package } from 'lucide-react'
import { clsx } from 'clsx'
import type { StudioPlugin } from '../../../../lib/api'
import type { AgentForm } from '../types'

interface Props {
  form: AgentForm
  setForm: React.Dispatch<React.SetStateAction<AgentForm>>
  plugins: StudioPlugin[]
}

const STATE_STYLE: Record<string, { badge: string; label: string }> = {
  active: { badge: 'badge-green', label: 'ativo' },
  degraded: { badge: 'badge-yellow', label: 'degradado' },
  stopped: { badge: 'badge-zinc', label: 'parado' },
  installed: { badge: 'badge-blue', label: 'instalado' },
  uninstalled: { badge: 'badge-zinc', label: 'removido' },
}

export default function SectionPlugins({ form, setForm, plugins }: Props) {
  const selected = new Set(form.selectedPlugins)

  const toggle = (name: string) =>
    setForm(prev => ({
      ...prev,
      selectedPlugins: prev.selectedPlugins.includes(name)
        ? prev.selectedPlugins.filter(n => n !== name)
        : [...prev.selectedPlugins, name],
    }))

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Plugins</h2>
        <p className="text-sm text-zinc-500">
          Plugins instalados que este agente pode usar. Plugins fora do estado "ativo"
          não podem ser selecionados.
        </p>
      </div>

      {plugins.length === 0 ? (
        <div className="card flex flex-col items-center py-10 text-center">
          <Package className="mb-2 h-8 w-8 text-zinc-600" aria-hidden="true" />
          <p className="text-sm text-zinc-500">Nenhum plugin instalado</p>
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {plugins.map(p => {
            const isSelected = selected.has(p.name)
            const incompatible = p.state !== 'active'
            const style = STATE_STYLE[p.state] ?? STATE_STYLE.installed
            return (
              <div
                key={p.name}
                className={clsx(
                  'rounded-lg border p-4 transition-colors',
                  isSelected ? 'border-cris-500/50 bg-cris-500/5' : 'border-zinc-800',
                  incompatible && 'opacity-60',
                )}
              >
                <div className="flex items-start gap-3">
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={isSelected}
                    aria-label={`Selecionar plugin ${p.name}`}
                    disabled={incompatible}
                    onClick={() => toggle(p.name)}
                    className={clsx(
                      'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border transition-colors',
                      isSelected ? 'border-cris-500 bg-cris-500 text-white' : 'border-zinc-700 hover:border-zinc-500',
                      incompatible && 'cursor-not-allowed opacity-50',
                    )}
                  >
                    {isSelected && <Check className="h-3 w-3" />}
                  </button>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Package className="h-4 w-4 text-cris-400" aria-hidden="true" />
                      <span className="font-medium">{p.name}</span>
                      <span className="badge-zinc">v{p.version}</span>
                      <span className={style.badge}>{style.label}</span>
                    </div>
                    <p className="mt-1 text-xs text-zinc-500">{p.description}</p>
                    {incompatible && (
                      <p className="mt-1 flex items-center gap-1 text-xs text-yellow-500/80">
                        <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                        Plugin incompatível: estado "{style.label}" — apenas plugins ativos podem ser selecionados
                      </p>
                    )}
                    <div className="mt-2">
                      <p className="mb-1 text-xs text-zinc-600">Capabilities fornecidas ({p.capabilities.length}):</p>
                      <div className="flex flex-wrap gap-1">
                        {p.capabilities.map(c => (
                          <span key={c.name} className="badge-zinc font-mono" title={c.description}>
                            {c.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
