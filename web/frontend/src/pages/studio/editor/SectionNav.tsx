import {
  Blocks, Brain, FileJson, Info, Link2, ListChecks, MessageSquareText,
  Package, ShieldCheck, Wrench,
} from 'lucide-react'
import { clsx } from 'clsx'
import type { ValidationIssue } from './validation'

export const SECTIONS = [
  { id: 'geral', label: 'Geral', icon: Info },
  { id: 'instrucoes', label: 'Instruções', icon: MessageSquareText },
  { id: 'capabilities', label: 'Capabilities', icon: Blocks },
  { id: 'plugins', label: 'Plugins', icon: Package },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'bindings', label: 'Bindings', icon: Link2 },
  { id: 'permissoes', label: 'Permissões', icon: ShieldCheck },
  { id: 'manifest', label: 'Manifest', icon: FileJson },
  { id: 'validacao', label: 'Validação', icon: ListChecks },
] as const

export type SectionId = (typeof SECTIONS)[number]['id']

interface Props {
  active: SectionId
  onChange: (id: SectionId) => void
  issues: ValidationIssue[]
}

export default function SectionNav({ active, onChange, issues }: Props) {
  return (
    <nav className="space-y-0.5" aria-label="Seções do editor">
      {SECTIONS.map(s => {
        const sectionIssues = issues.filter(i => i.section === s.id)
        const errorCount = sectionIssues.filter(i => i.level === 'error').length
        const warnCount = sectionIssues.filter(i => i.level === 'warning').length
        const isActive = active === s.id
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => onChange(s.id)}
            aria-current={isActive ? 'true' : undefined}
            className={clsx(
              'flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
              isActive
                ? 'bg-cris-500/10 font-medium text-cris-400'
                : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100',
            )}
          >
            <s.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span className="flex-1 text-left">{s.label}</span>
            {errorCount > 0 && (
              <span className="badge-red px-1.5" aria-label={`${errorCount} erros`}>{errorCount}</span>
            )}
            {errorCount === 0 && warnCount > 0 && (
              <span className="badge-yellow px-1.5" aria-label={`${warnCount} avisos`}>{warnCount}</span>
            )}
          </button>
        )
      })}
    </nav>
  )
}
