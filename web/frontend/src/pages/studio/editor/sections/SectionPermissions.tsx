import { ShieldAlert, ShieldCheck } from 'lucide-react'
import { clsx } from 'clsx'
import type { StudioCapability } from '../../../../lib/api'
import { isSensitive, type AgentForm } from '../types'

interface Props {
  form: AgentForm
  setForm: React.Dispatch<React.SetStateAction<AgentForm>>
  capabilities: StudioCapability[]
}

export default function SectionPermissions({ form, setForm, capabilities }: Props) {
  const inUse = new Set<string>([...form.selectedCapabilities, ...form.bindings.map(b => b.capability)])
  const sensitive = capabilities.filter(c => isSensitive(c.name) && inUse.has(c.name))

  const toggle = (name: string) =>
    setForm(prev => ({
      ...prev,
      requireConfirmation: prev.requireConfirmation.includes(name)
        ? prev.requireConfirmation.filter(n => n !== name)
        : [...prev.requireConfirmation, name],
    }))

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Permissões</h2>
        <p className="text-sm text-zinc-500">
          Capabilities sensíveis (enviar, apagar, arquivar, publicar...) devem exigir
          confirmação do usuário antes de executar.
        </p>
      </div>

      {sensitive.length === 0 ? (
        <div className="card flex flex-col items-center py-10 text-center">
          <ShieldCheck className="mb-2 h-8 w-8 text-cris-400" aria-hidden="true" />
          <p className="text-sm text-zinc-400">Nenhuma capability sensível em uso</p>
          <p className="text-xs text-zinc-600">
            As capabilities selecionadas para este agente não incluem ações destrutivas ou externas
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-start gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3 text-sm text-yellow-300">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p className="text-xs">
              Este agente usa {sensitive.length} {sensitive.length === 1 ? 'capability sensível' : 'capabilities sensíveis'}.
              Ative a confirmação para exigir aprovação antes da execução.
            </p>
          </div>

          {sensitive.map(c => {
            const required = form.requireConfirmation.includes(c.name)
            return (
              <div
                key={c.name}
                className={clsx(
                  'flex items-center justify-between rounded-lg border p-3',
                  required ? 'border-cris-500/40 bg-cris-500/5' : 'border-yellow-500/30 bg-yellow-500/5',
                )}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm">{c.name}</span>
                    <span className="badge-yellow">sensível</span>
                  </div>
                  <p className="mt-0.5 text-xs text-zinc-500">{c.description}</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={required}
                  aria-label={`Exigir confirmação para ${c.name}`}
                  onClick={() => toggle(c.name)}
                  className={clsx(
                    'relative h-6 w-11 shrink-0 rounded-full transition-colors',
                    required ? 'bg-cris-500' : 'bg-zinc-700',
                  )}
                >
                  <span
                    className={clsx(
                      'absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform',
                      required ? 'translate-x-5' : 'translate-x-0.5',
                    )}
                    aria-hidden="true"
                  />
                </button>
              </div>
            )
          })}

          <p className="text-xs text-zinc-600">
            Regra: a confirmação é registrada no manifesto (<code className="font-mono">permissoes.require_confirmation</code>)
            e será aplicada pelo runtime antes de executar a capability.
          </p>
        </div>
      )}
    </div>
  )
}
