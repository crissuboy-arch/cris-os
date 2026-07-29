import type { StudioCapability } from '../../../lib/api'
import { isSensitive, type AgentForm, type BindingForm } from './types'

export interface ValidationIssue {
  level: 'error' | 'warning'
  section: string
  message: string
}

const SEMVER = /^\d+\.\d+\.\d+$/
const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/

export function validateForm(
  form: AgentForm,
  capabilities: StudioCapability[],
  otherSlugs: string[],
): ValidationIssue[] {
  const issues: ValidationIssue[] = []
  const capMap = new Map(capabilities.map(c => [c.name, c]))

  // --- Geral ---
  if (!form.name.trim()) {
    issues.push({ level: 'error', section: 'geral', message: 'Nome é obrigatório' })
  } else if (form.name.trim().length < 3) {
    issues.push({ level: 'error', section: 'geral', message: 'Nome deve ter pelo menos 3 caracteres' })
  }

  if (!form.slug) {
    issues.push({ level: 'error', section: 'geral', message: 'Slug é obrigatório' })
  } else if (!SLUG.test(form.slug)) {
    issues.push({ level: 'error', section: 'geral', message: 'Slug deve conter apenas letras minúsculas, números e hífens' })
  } else if (otherSlugs.includes(form.slug)) {
    issues.push({ level: 'error', section: 'geral', message: `O slug "${form.slug}" já está em uso por outro agente` })
  }

  if (!SEMVER.test(form.version)) {
    issues.push({ level: 'error', section: 'geral', message: 'Versão deve seguir o formato semântico (ex.: 1.0.0)' })
  }

  // --- Instruções ---
  if (!form.instrucoes.prompt.trim()) {
    issues.push({ level: 'warning', section: 'instrucoes', message: 'Prompt principal vazio — o agente não terá orientação de comportamento' })
  }

  // --- Capabilities ---
  for (const name of form.selectedCapabilities) {
    const cap = capMap.get(name)
    if (!cap) {
      issues.push({ level: 'error', section: 'capabilities', message: `Capability "${name}" não existe no registry` })
    } else if (cap.health === 'down' || cap.health === 'degraded') {
      issues.push({ level: 'warning', section: 'capabilities', message: `Capability "${name}" está com health "${cap.health}"` })
    } else if (cap.status !== 'active') {
      issues.push({ level: 'warning', section: 'capabilities', message: `Capability "${name}" está com status "${cap.status}"` })
    }
  }

  // --- Bindings ---
  if (form.bindings.length === 0) {
    issues.push({ level: 'warning', section: 'bindings', message: 'Nenhum binding definido — o agente não conseguirá executar ações' })
  }

  form.bindings.forEach((b, i) => {
    validateBinding(b, i, capMap, issues)
  })

  const keywords = form.bindings.map(b => b.keyword.trim().toLowerCase()).filter(Boolean)
  const dupes = keywords.filter((k, i) => keywords.indexOf(k) !== i)
  if (dupes.length > 0) {
    issues.push({ level: 'error', section: 'bindings', message: `Keywords duplicadas: ${[...new Set(dupes)].join(', ')}` })
  }

  // --- Permissões ---
  const sensitiveInUse = new Set<string>()
  for (const name of form.selectedCapabilities) if (isSensitive(name)) sensitiveInUse.add(name)
  for (const b of form.bindings) if (isSensitive(b.capability)) sensitiveInUse.add(b.capability)
  for (const name of sensitiveInUse) {
    if (!form.requireConfirmation.includes(name)) {
      issues.push({
        level: 'warning',
        section: 'permissoes',
        message: `Capability sensível "${name}" em uso sem regra de confirmação`,
      })
    }
  }

  return issues
}

function validateBinding(
  b: BindingForm,
  index: number,
  capMap: Map<string, StudioCapability>,
  issues: ValidationIssue[],
): void {
  const label = `Binding ${index + 1}`

  if (!b.keyword.trim()) {
    issues.push({ level: 'error', section: 'bindings', message: `${label}: keyword é obrigatória` })
  }
  if (!b.capability) {
    issues.push({ level: 'error', section: 'bindings', message: `${label}: selecione uma capability` })
    return
  }

  const cap = capMap.get(b.capability)
  if (!cap) {
    issues.push({ level: 'error', section: 'bindings', message: `${label}: capability "${b.capability}" não existe no registry` })
    return
  }

  const schema = cap.input_schema
  const required = schema?.required ?? []
  const properties = schema?.properties ?? {}
  const mappedKeys = new Set(b.params.map(p => p.key.trim()).filter(Boolean))

  for (const req of required) {
    if (!mappedKeys.has(req)) {
      issues.push({
        level: 'error',
        section: 'bindings',
        message: `${label}: parâmetro obrigatório "${req}" de ${b.capability} não está mapeado`,
      })
    }
  }

  for (const p of b.params) {
    if (!p.key.trim()) {
      issues.push({ level: 'error', section: 'bindings', message: `${label}: parâmetro sem nome` })
      continue
    }
    if (p.source === 'context' && !p.value.trim()) {
      issues.push({ level: 'error', section: 'bindings', message: `${label}: parâmetro "${p.key}" usa contexto mas não informa o campo` })
    }
    if (p.source === 'fixed') {
      const propType = properties[p.key]?.type
      if (propType && !checkType(p.value, propType)) {
        issues.push({
          level: 'error',
          section: 'bindings',
          message: `${label}: valor fixo de "${p.key}" não é do tipo ${propType}`,
        })
      }
    }
  }
}

function checkType(value: string, type: string): boolean {
  switch (type) {
    case 'integer':
    case 'number':
      return value.trim() !== '' && !isNaN(Number(value))
    case 'boolean':
      return ['true', 'false'].includes(value.trim().toLowerCase())
    case 'array':
    case 'object':
      try { JSON.parse(value); return true } catch { return false }
    case 'string':
    default:
      return true
  }
}

export function hasErrors(issues: ValidationIssue[]): boolean {
  return issues.some(i => i.level === 'error')
}

export function issuesBySection(issues: ValidationIssue[]): Map<string, ValidationIssue[]> {
  const map = new Map<string, ValidationIssue[]>()
  for (const issue of issues) {
    const list = map.get(issue.section) ?? []
    list.push(issue)
    map.set(issue.section, list)
  }
  return map
}
