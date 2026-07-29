import { AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import type { ValidationIssue } from './validation'

interface Props {
  issues: ValidationIssue[]
  onGoToSection: (section: string) => void
}

export default function ValidationPanel({ issues, onGoToSection }: Props) {
  const errors = issues.filter(i => i.level === 'error')
  const warnings = issues.filter(i => i.level === 'warning')

  if (issues.length === 0) {
    return (
      <div className="flex flex-col items-center py-8 text-center">
        <CheckCircle className="mb-2 h-8 w-8 text-cris-400" aria-hidden="true" />
        <p className="text-sm font-medium text-cris-400">Tudo válido</p>
        <p className="text-xs text-zinc-500">O agente está pronto para ser salvo e publicado</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2 text-xs">
        <span className={errors.length > 0 ? 'badge-red' : 'badge-zinc'}>
          {errors.length} {errors.length === 1 ? 'erro' : 'erros'}
        </span>
        <span className={warnings.length > 0 ? 'badge-yellow' : 'badge-zinc'}>
          {warnings.length} {warnings.length === 1 ? 'aviso' : 'avisos'}
        </span>
      </div>

      <ul className="space-y-2" aria-label="Problemas de validação">
        {issues.map((issue, i) => (
          <li key={i}>
            <button
              type="button"
              onClick={() => onGoToSection(issue.section)}
              className="flex w-full items-start gap-2 rounded-md border border-zinc-800 p-2 text-left transition-colors hover:border-zinc-700"
              aria-label={`Ir para seção ${issue.section}: ${issue.message}`}
            >
              {issue.level === 'error' ? (
                <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" aria-hidden="true" />
              ) : (
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-yellow-400" aria-hidden="true" />
              )}
              <span className="text-xs text-zinc-300">{issue.message}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
