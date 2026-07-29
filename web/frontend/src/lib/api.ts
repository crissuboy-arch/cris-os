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
  // Fase 3 fields (top-level)
  instructions?: {
    role?: string
    objective?: string
    rules?: string[]
    restrictions?: string[]
    output_format?: string
    custom_prompt?: string
  }
  memory?: {
    memory_type?: string
    scope?: string[]
    read_enabled?: boolean
    write_enabled?: boolean
    project?: string
  }
  permissions?: {
    allowed_capabilities?: string[]
    denied_capabilities?: string[]
    require_confirmation?: string[]
  }
  tools?: {
    internal?: string[]
    http?: Array<Record<string, any>>
    mcp?: Array<Record<string, any>>
  }
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
  // Fase 3 fields (top-level)
  instructions?: {
    role?: string
    objective?: string
    rules?: string[]
    restrictions?: string[]
    output_format?: string
    custom_prompt?: string
  }
  memory?: {
    memory_type?: string
    scope?: string[]
    read_enabled?: boolean
    write_enabled?: boolean
    project?: string
  }
  permissions?: {
    allowed_capabilities?: string[]
    denied_capabilities?: string[]
    require_confirmation?: string[]
  }
  tools?: {
    internal?: string[]
    http?: Array<Record<string, any>>
    mcp?: Array<Record<string, any>>
  }
}

export interface StudioExecution {
  id: string
  agent_id: string
  agent_name: string
  instruction: string
  status: 'running' | 'success' | 'error' | 'denied'
  duration_ms: number
  system_prompt: string
  bindings_attempted: string[]
  capabilities_called: Array<{ capability: string; params: Record<string, any>; timestamp: number }>
  permissions_checked: Array<{ capability: string; status: string }>
  permissions_denied: string[]
  memory_reads: Array<{ type: string; items: number }>
  memory_writes: Array<{ type: string; key: string; size: number }>
  errors: string[]
  output: string
  timestamp: number
  session: string
}

export interface StudioMetrics {
  total: number
  success: number
  error: number
  success_rate: number
  avg_duration_ms: number
  p95_duration_ms: number
  p99_duration_ms: number
  by_agent: Record<string, { total: number; success: number; error: number; avg_ms: number }>
  by_capability: Record<string, { total: number; success: number; error: number }>
  memory_reads: number
  memory_writes: number
  permissions_denied: number
}

export interface StudioConfirmation {
  id: string
  agent_id: string
  agent_name: string
  capability: string
  instruction: string
  params: Record<string, any>
  status: 'pending' | 'confirmed' | 'rejected'
  created_at: number
  resolved_at: number | null
  notes: string
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

  // Execute
  execute: (id: string, instruction: string, session = 'studio') =>
    request<any>(`/studio/agents/${id}/execute`, {
      method: 'POST',
      body: JSON.stringify({ instruction, session }),
    }),

  // Executions
  executions: (limit = 50) => request<StudioExecution[]>(`/studio/executions?limit=${limit}`),
  execution: (id: string) => request<StudioExecution>(`/studio/executions/${id}`),
  executionStats: () => request<any>('/studio/executions/stats'),
  agentExecutions: (id: string, limit = 20) =>
    request<StudioExecution[]>(`/studio/agents/${id}/executions?limit=${limit}`),

  // Metrics
  metrics: (since?: string) => request<StudioMetrics>(`/studio/metrics${since ? `?since=${since}` : ''}`),
  metricsRecent: (limit = 20) => request<any[]>(`/studio/metrics/recent?limit=${limit}`),
  metricsAgent: (id: string) => request<any>(`/studio/metrics/agent/${id}`),

  // Confirmations
  confirmations: () => request<StudioConfirmation[]>('/studio/confirmations'),
  confirmationsAll: (limit = 50) => request<StudioConfirmation[]>(`/studio/confirmations/all?limit=${limit}`),
  confirmationStats: () => request<any>('/studio/confirmations/stats'),
  confirmAction: (id: string, notes = '') =>
    request<any>(`/studio/confirmations/${id}/confirm`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    }),
  rejectAction: (id: string, notes = '') =>
    request<any>(`/studio/confirmations/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    }),

  // Memory
  sessionMemory: (sessionId: string, limit = 10) =>
    request<any[]>(`/studio/memory/session/${sessionId}?limit=${limit}`),
  projectMemory: (project: string) => request<any[]>(`/studio/memory/project/${project}`),
  writeProjectMemory: (project: string, data: { type?: string; title: string; content: string; tags?: string[] }) =>
    request<any>(`/studio/memory/project/${project}`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Auth
  login: (username: string, password: string) =>
    request<{ success: boolean; token: string; user: any }>('/studio/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<any>('/studio/auth/logout', { method: 'POST' }),
  authMe: () => request<any>('/studio/auth/me'),
  listUsers: () => request<any[]>('/studio/auth/users'),
  createUser: (data: { username: string; password: string; role?: string; display_name?: string }) =>
    request<any>('/studio/auth/users', { method: 'POST', body: JSON.stringify(data) }),
  deleteUser: (username: string) =>
    request<any>(`/studio/auth/users/${username}`, { method: 'DELETE' }),

  // MCP
  mcpServers: () => request<any[]>('/studio/mcp/servers'),
  registerMcpServer: (data: any) =>
    request<any>('/studio/mcp/servers', { method: 'POST', body: JSON.stringify(data) }),
  unregisterMcpServer: (name: string) =>
    request<any>(`/studio/mcp/servers/${name}`, { method: 'DELETE' }),
  discoverMcpTools: (server?: string) =>
    request<any>('/studio/mcp/discover' + (server ? `?server=${server}` : ''), { method: 'POST' }),
  mcpTools: () => request<any[]>('/studio/mcp/tools'),
  executeMcpTool: (toolName: string, params: any = {}) =>
    request<any>('/studio/mcp/execute', { method: 'POST', body: JSON.stringify({ tool_name: toolName, params }) }),

  // Export / Import
  exportAgent: (id: string) => request<any>(`/studio/agents/${id}/export`),
  importAgent: (data: any) =>
    request<any>('/studio/agents/import', { method: 'POST', body: JSON.stringify({ data }) }),

  // Versioning
  versions: (id: string) => request<any>(`/studio/agents/${id}/versions`),
  version: (id: string, v: string) => request<any>(`/studio/agents/${id}/versions/${v}`),
  versionDiff: (id: string, from: string, to: string) =>
    request<any>(`/studio/agents/${id}/diff?from_version=${from}&to_version=${to}`),
  restoreVersion: (id: string, version: string) =>
    request<any>(`/studio/agents/${id}/restore/${version}`, { method: 'POST' }),

  // Notifications
  notificationConfig: () => request<any>('/studio/notifications/config'),
  configureNotifications: (token: string, chatId: string) =>
    request<any>('/studio/notifications/config', {
      method: 'POST',
      body: JSON.stringify({ token, chat_id: chatId }),
    }),
  notificationHistory: (limit = 50) => request<any[]>(`/studio/notifications/history?limit=${limit}`),
  notificationStats: () => request<any>('/studio/notifications/stats'),
}
