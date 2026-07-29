import type { StudioAgent, StudioAgentUpdatePayload } from '../../../lib/api'

export type ParamSource = 'fixed' | 'instruction' | 'context'

export interface ParamMapping {
  key: string
  source: ParamSource
  value: string
}

export interface BindingForm {
  keyword: string
  capability: string
  description: string
  priority: number
  params: ParamMapping[]
}

export type MemoryMode = 'none' | 'session' | 'agent' | 'project'

export interface AgentForm {
  name: string
  description: string
  slug: string
  version: string
  categoria: string
  icone: string
  tags: string[]
  instrucoes: {
    prompt: string
    papel: string
    regras: string
    restricoes: string
    objetivo: string
    formato_saida: string
  }
  selectedCapabilities: string[]
  selectedPlugins: string[]
  tools: { internal: string[]; http: string[]; mcp: string[] }
  memoryMode: MemoryMode
  bindings: BindingForm[]
  requireConfirmation: string[]
  config: { timeout_ms: number; max_iterations: number; allow_fallback: boolean }
}

export const MEMORY_OPTIONS: Array<{ mode: MemoryMode; label: string; enabled: boolean; reason?: string }> = [
  { mode: 'none', label: 'Sem memória', enabled: true },
  { mode: 'session', label: 'Memória de sessão', enabled: true },
  {
    mode: 'agent',
    label: 'Memória do agente',
    enabled: false,
    reason: 'O runtime de agentes dinâmicos ainda não consome memória dedicada por agente — previsto para fase futura',
  },
  {
    mode: 'project',
    label: 'Memória do projeto',
    enabled: false,
    reason: 'O runtime de agentes dinâmicos ainda não consome memória de projeto — previsto para fase futura',
  },
]

export function emptyForm(agent?: StudioAgent): AgentForm {
  return {
    name: agent?.name ?? '',
    description: agent?.description ?? '',
    slug: agent?.metadata?.slug ?? slugify(agent?.name ?? ''),
    version: agent?.version ?? '1.0.0',
    categoria: agent?.metadata?.categoria ?? '',
    icone: agent?.metadata?.icone ?? 'Bot',
    tags: agent?.metadata?.tags ?? [],
    instrucoes: {
      prompt: agent?.metadata?.instrucoes?.prompt ?? '',
      papel: agent?.metadata?.instrucoes?.papel ?? '',
      regras: agent?.metadata?.instrucoes?.regras ?? '',
      restricoes: agent?.metadata?.instrucoes?.restricoes ?? '',
      objetivo: agent?.metadata?.instrucoes?.objetivo ?? '',
      formato_saida: agent?.metadata?.instrucoes?.formato_saida ?? '',
    },
    selectedCapabilities: agent?.metadata?.capabilities ?? [],
    selectedPlugins: agent?.metadata?.plugins ?? [],
    tools: {
      internal: agent?.metadata?.tools?.internal ?? [],
      http: agent?.metadata?.tools?.http ?? [],
      mcp: agent?.metadata?.tools?.mcp ?? [],
    },
    memoryMode: agent?.metadata?.memory?.mode ?? 'none',
    bindings: (agent?.bindings ?? []).map(b => ({
      keyword: b.keyword,
      capability: b.capability,
      description: b.description ?? '',
      priority: b.priority ?? 50,
      params: templateToParams(b.input_template ?? {}),
    })),
    requireConfirmation: agent?.metadata?.permissoes?.require_confirmation ?? [],
    config: {
      timeout_ms: agent?.config?.timeout_ms ?? 30000,
      max_iterations: agent?.config?.max_iterations ?? 10,
      allow_fallback: agent?.config?.allow_fallback ?? true,
    },
  }
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function templateToParams(template: Record<string, string>): ParamMapping[] {
  return Object.entries(template).map(([key, value]) => {
    const v = String(value)
    if (v.includes('{instruction}')) {
      return { key, source: 'instruction' as ParamSource, value: v === '{instruction}' ? '' : v }
    }
    const ctx = v.match(/^\{context\.(.+)\}$/)
    if (ctx) {
      return { key, source: 'context' as ParamSource, value: ctx[1] }
    }
    return { key, source: 'fixed' as ParamSource, value: v }
  })
}

export function paramsToTemplate(params: ParamMapping[]): Record<string, string> {
  const template: Record<string, string> = {}
  for (const p of params) {
    if (!p.key.trim()) continue
    if (p.source === 'instruction') {
      template[p.key] = p.value.includes('{instruction}') ? p.value : '{instruction}'
    } else if (p.source === 'context') {
      template[p.key] = `{context.${p.value}}`
    } else {
      template[p.key] = p.value
    }
  }
  return template
}

export function formToPayload(form: AgentForm): StudioAgentUpdatePayload {
  return {
    name: form.name.trim(),
    description: form.description.trim(),
    bindings: form.bindings.map(b => ({
      keyword: b.keyword.trim(),
      capability: b.capability,
      description: b.description,
      priority: b.priority,
      input_template: paramsToTemplate(b.params),
    })),
    config: { ...form.config },
    metadata: {
      slug: form.slug,
      categoria: form.categoria,
      icone: form.icone,
      tags: form.tags,
      instrucoes: { ...form.instrucoes },
      capabilities: form.selectedCapabilities,
      plugins: form.selectedPlugins,
      tools: { ...form.tools },
      memory: { mode: form.memoryMode },
      permissoes: { require_confirmation: form.requireConfirmation },
    },
  }
}

/** Monta o manifesto (mesmo formato de AgentDefinition.to_dict) para preview. */
export function formToManifest(form: AgentForm, agent: StudioAgent | null): Record<string, any> {
  const payload = formToPayload(form)
  return {
    agent_id: agent?.agent_id ?? '(gerado ao criar)',
    name: payload.name,
    version: form.version,
    description: payload.description,
    status: agent?.status ?? 'draft',
    bindings: payload.bindings,
    config: payload.config,
    metadata: payload.metadata,
    created_at: agent?.created_at ?? '—',
    updated_at: '(atualizado ao salvar)',
    published_at: agent?.published_at ?? null,
  }
}

/** Capabilities consideradas sensíveis (exigem confirmação antes de executar). */
const SENSITIVE_SUFFIXES = ['send', 'delete', 'archive', 'publish', 'remove', 'execute', 'isolation']

export function isSensitive(capabilityName: string): boolean {
  const suffix = capabilityName.split('.').pop() ?? ''
  return SENSITIVE_SUFFIXES.includes(suffix)
}
