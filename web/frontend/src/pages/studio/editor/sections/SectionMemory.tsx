import { AlertTriangle, Ban, CheckCircle } from 'lucide-react'
import { clsx } from 'clsx'
import { MEMORY_OPTIONS, type AgentForm } from '../types'

interface Props {
  form: AgentForm
  setForm: React.Dispatch<React.SetStateAction<AgentForm>>
}

const DESCRIPTIONS: Record<string, string> = {
  none: 'O agente não guarda nenhum contexto entre execuções.',
  session: 'O agente usa a memória da conversa atual (L1) durante a sessão.',
  agent: 'Memória persistente dedicada a este agente, entre sessões.',
  project: 'Memória compartilhada no escopo de um projeto.',
}

export default function SectionMemory({ form, setForm }: Props) {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Memória</h2>
        <p className="text-sm text-zinc-500">
          Escolha o escopo de memória do agente. Opções ainda não suportadas pelo
          runtime aparecem desativadas com explicação.
        </p>
      </div>

      <div className="space-y-2" role="radiogroup" aria-label="Escopo de memória">
        {MEMORY_OPTIONS.map(opt => {
          const selected = form.memoryMode === opt.mode
          return (
            <button
              key={opt.mode}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={!opt.enabled}
              onClick={() => setForm(prev => ({ ...prev, memoryMode: opt.mode }))}
              className={clsx(
                'flex w-full items-start gap-3 rounded-lg border p-4 text-left transition-colors',
                selected
                  ? 'border-cris-500 bg-cris-500/10'
                  : 'border-zinc-800 hover:border-zinc-700',
                !opt.enabled && 'cursor-not-allowed opacity-50 hover:border-zinc-800',
              )}
            >
              <span className="mt-0.5">
                {!opt.enabled ? (
                  <Ban className="h-4 w-4 text-zinc-600" aria-hidden="true" />
                ) : selected ? (
                  <CheckCircle className="h-4 w-4 text-cris-400" aria-hidden="true" />
                ) : (
                  <span className="block h-4 w-4 rounded-full border border-zinc-700" aria-hidden="true" />
                )}
              </span>
              <span className="flex-1">
                <span className="flex items-center gap-2">
                  <span className="text-sm font-medium">{opt.label}</span>
                  {!opt.enabled && <span className="badge-yellow">indisponível</span>}
                </span>
                <span className="mt-0.5 block text-xs text-zinc-500">{DESCRIPTIONS[opt.mode]}</span>
                {!opt.enabled && (
                  <span className="mt-1 flex items-start gap-1 text-xs text-yellow-500/80">
                    <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                    {opt.reason}
                  </span>
                )}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
