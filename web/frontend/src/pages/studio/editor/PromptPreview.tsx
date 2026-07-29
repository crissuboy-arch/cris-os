import { useMemo } from 'react'
import { Eye } from 'lucide-react'
import type { AgentForm } from './types'

interface Props {
  form: AgentForm
  agentName: string
  description: string
}

/** Build system prompt from form data (mirrors DynamicAgent._build_system_prompt). */
function buildPrompt(form: AgentForm, agentName: string, description: string): string {
  const parts: string[] = []

  // Role
  if (form.instrucoes.papel) {
    parts.push(`Voce e: ${form.instrucoes.papel}`)
  }

  // Objective
  if (form.instrucoes.objetivo) {
    parts.push(`Objetivo: ${form.instrucoes.objetivo}`)
  }

  // Custom prompt (raw)
  if (form.instrucoes.prompt) {
    parts.push(form.instrucoes.prompt)
  }

  // Rules
  const rules = form.instrucoes.regras.split('\n').filter(Boolean)
  if (rules.length > 0) {
    parts.push('Regras:')
    rules.forEach((rule, i) => {
      parts.push(`  ${i + 1}. ${rule}`)
    })
  }

  // Restrictions
  const restrictions = form.instrucoes.restricoes.split('\n').filter(Boolean)
  if (restrictions.length > 0) {
    parts.push('Restricoes:')
    restrictions.forEach((rest, i) => {
      parts.push(`  ${i + 1}. ${rest}`)
    })
  }

  // Output format
  if (form.instrucoes.formato_saida) {
    parts.push(`Formato de saida: ${form.instrucoes.formato_saida}`)
  }

  // Fallback to description
  if (parts.length === 0 && description) {
    parts.push(description)
  }

  // Fallback to agent name
  if (parts.length === 0 && agentName) {
    parts.push(`Agente: ${agentName}`)
  }

  return parts.join('\n') || '(nenhuma instrucao definida)'
}

export default function PromptPreview({ form, agentName, description }: Props) {
  const prompt = useMemo(() => buildPrompt(form, agentName, description), [form, agentName, description])

  const lineCount = prompt.split('\n').length
  const charCount = prompt.length

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 text-xs font-medium text-zinc-400">
          <Eye className="h-3.5 w-3.5" /> System Prompt
        </h3>
        <span className="text-[10px] text-zinc-600">{lineCount} linhas · {charCount} chars</span>
      </div>
      <pre className="max-h-[55vh] overflow-y-auto whitespace-pre-wrap rounded-md bg-zinc-950/80 p-3 font-mono text-xs leading-relaxed text-zinc-300 border border-zinc-800/50">
        {prompt}
      </pre>
    </div>
  )
}
