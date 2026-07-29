const API = '/api'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let message = res.statusText
    try {
      const data = await res.json()
      if (data?.detail) message = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
      else if (data?.error) message = data.error
    } catch {
      message = await res.text().catch(() => res.statusText)
    }
    throw new Error(message || res.statusText)
  }
  return res.json()
}

export const api = {
  // Sistema
  status: () => request<any>('/status'),
  health: () => request<any>('/health'),

  // Agentes
  agents: () => request<any[]>('/agents'),
  agent: (name: string) => request<any>(`/agents/${name}`),

  // Chat
  chat: (mensagem: string, agente = 'auto', modelo = '') =>
    request<any>('/chat/enviar', {
      method: 'POST',
      body: JSON.stringify({ mensagem, agente, modelo }),
    }),
  historico: (usuarioId = 'dashboard', limite = 50) =>
    request<any[]>(`/chat/historico/${usuarioId}?limite=${limite}`),
  limparHistorico: (usuarioId = 'dashboard') =>
    request<any>(`/chat/historico/${usuarioId}`, { method: 'DELETE' }),

  // Memoria
  memoria: () => request<any>('/memoria'),
  adicionarMemoria: (chave: string, valor: string) =>
    request<any>('/memoria', {
      method: 'POST',
      body: JSON.stringify({ chave, valor }),
    }),
  atualizarMemoria: (chave: string, valor: string) =>
    request<any>(`/memoria/${chave}`, {
      method: 'PUT',
      body: JSON.stringify({ chave, valor }),
    }),
  excluirMemoria: (chave: string) =>
    request<any>(`/memoria/${chave}`, { method: 'DELETE' }),

  // Clientes
  clientes: () => request<any[]>('/clientes'),
  cliente: (id: number) => request<any>(`/clientes/${id}`),
  criarCliente: (data: any) =>
    request<any>('/clientes', { method: 'POST', body: JSON.stringify(data) }),
  atualizarCliente: (id: number, data: any) =>
    request<any>(`/clientes/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  excluirCliente: (id: number) =>
    request<any>(`/clientes/${id}`, { method: 'DELETE' }),

  // Projetos
  projetos: () => request<any[]>('/projetos'),
  projeto: (id: number) => request<any>(`/projetos/${id}`),
  criarProjeto: (data: any) =>
    request<any>('/projetos', { method: 'POST', body: JSON.stringify(data) }),
  atualizarProjeto: (id: number, data: any) =>
    request<any>(`/projetos/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  excluirProjeto: (id: number) =>
    request<any>(`/projetos/${id}`, { method: 'DELETE' }),

  // Tarefas
  tarefas: () => request<any[]>('/tarefas'),
  tarefasPendentes: () => request<any[]>('/tarefas/pendentes'),
  tarefa: (id: number) => request<any>(`/tarefas/${id}`),
  criarTarefa: (data: any) =>
    request<any>('/tarefas', { method: 'POST', body: JSON.stringify(data) }),
  atualizarTarefa: (id: number, data: any) =>
    request<any>(`/tarefas/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  concluirTarefa: (id: number) =>
    request<any>(`/tarefas/${id}/concluir`, { method: 'POST' }),
  excluirTarefa: (id: number) =>
    request<any>(`/tarefas/${id}`, { method: 'DELETE' }),

  // Prompts
  prompts: (categoria = '') =>
    request<any[]>(`/prompts${categoria ? `?categoria=${categoria}` : ''}`),
  buscarPrompts: (termo: string) =>
    request<any[]>(`/prompts/buscar?termo=${termo}`),
  promptsFavoritos: () => request<any[]>('/prompts/favoritos'),
  criarPrompt: (data: any) =>
    request<any>('/prompts', { method: 'POST', body: JSON.stringify(data) }),
  atualizarPrompt: (id: number, data: any) =>
    request<any>(`/prompts/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  alternarFavorito: (id: number) =>
    request<any>(`/prompts/${id}/favorito`, { method: 'POST' }),
  excluirPrompt: (id: number) =>
    request<any>(`/prompts/${id}`, { method: 'DELETE' }),

  // Logs
  logs: (params?: { limite?: number; agente?: string; erro?: boolean }) => {
    const p = new URLSearchParams()
    if (params?.limite) p.set('limite', String(params.limite))
    if (params?.agente) p.set('agente', params.agente)
    if (params?.erro) p.set('erro', 'true')
    return request<any[]>(`/logs?${p}`)
  },
  metricasLogs: () => request<any>('/logs/metricas'),

  // Configuracoes
  configuracoes: () => request<Record<string, string>>('/configuracoes'),
  definirConfig: (chave: string, valor: string) =>
    request<any>('/configuracoes', {
      method: 'POST',
      body: JSON.stringify({ chave, valor }),
    }),
  resetarConfig: () =>
    request<any>('/configuracoes/resetar', { method: 'POST' }),
}

export interface StudioAgent {
  agent_id: string
  name: string
  version: string
  description: string
  status: 'draft' | 'published' | 'deactivated' | 'archived'
  bindings: Array<{
    keyword: string
    capability: string
    input_template: Record<string, string>
    description: string
    priority: number
  }>
  config: {
    timeout_ms: number
    max_iterations: number
    allow_fallback: boolean
  }
  metadata: Record<string, any>
  created_at: string
  updated_at: string
  published_at: string | null
}

export interface StudioCapability {
  name: string
  version: string
  plugin: string
  domain: string
  description: string
  priority: number
  health: 'ok' | 'degraded' | 'down' | 'unknown'
  status: 'active' | 'degraded' | 'deprecated' | 'removed'
  timeout_ms: number
  idempotent: boolean
  input_schema: {
    type?: string
    properties?: Record<string, { type?: string; default?: any; items?: any }>
    required?: string[]
  } | null
  output_schema: Record<string, any> | null
}

export interface StudioPlugin {
  name: string
  version: string
  description: string
  author: string
  state: 'installed' | 'active' | 'degraded' | 'stopped' | 'uninstalled'
  capabilities: Array<{ name: string; version: string; description: string }>
}

export interface StudioToolType {
  type: 'internal' | 'http' | 'mcp'
  label: string
  available: boolean
  reason?: string
  items: Array<{ name: string; description: string; module: string }>
  errors?: string[]
}

export interface StudioAgentUpdatePayload {
  name?: string
  description?: string
  bindings?: Array<{
    keyword: string
    capability: string
    input_template: Record<string, string>
    description?: string
    priority?: number
  }>
  config?: { timeout_ms?: number; max_iterations?: number; allow_fallback?: boolean }
  metadata?: Record<string, any>
}

export const studioApi = {
  list: () => request<StudioAgent[]>('/studio/agents'),
  get: (id: string) => request<StudioAgent>(`/studio/agents/${id}`),
  create: (name: string, description = '') =>
    request<StudioAgent>('/studio/agents', {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    }),
  update: (id: string, payload: StudioAgentUpdatePayload) =>
    request<StudioAgent>(`/studio/agents/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  delete: (id: string) =>
    request<{ deleted: boolean }>(`/studio/agents/${id}`, { method: 'DELETE' }),
  publish: (id: string) =>
    request<StudioAgent>(`/studio/agents/${id}/publish`, { method: 'POST' }),
  capabilities: () => request<StudioCapability[]>('/studio/capabilities'),
  plugins: () => request<StudioPlugin[]>('/studio/plugins'),
  tools: () => request<{ types: StudioToolType[] }>('/studio/tools'),
}
