import { useEffect, useState, useCallback } from 'react'
import {
  Activity, BarChart3, Clock, AlertCircle, CheckCircle2, Shield,
  Brain, RefreshCw, ChevronDown, ChevronRight, Search,
} from 'lucide-react'
import { studioApi, type StudioMetrics, type StudioExecution, type StudioConfirmation } from '../../lib/api'

type Tab = 'overview' | 'executions' | 'confirmations'

export default function StudioObservability() {
  const [tab, setTab] = useState<Tab>('overview')
  const [metrics, setMetrics] = useState<StudioMetrics | null>(null)
  const [executions, setExecutions] = useState<StudioExecution[]>([])
  const [confirmations, setConfirmations] = useState<StudioConfirmation[]>([])
  const [confStats, setConfStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [since, setSince] = useState('24h')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [m, e, cs, cstats] = await Promise.all([
        studioApi.metrics(since),
        studioApi.executions(100),
        studioApi.confirmations(),
        studioApi.confirmationStats(),
      ])
      setMetrics(m)
      setExecutions(e)
      setConfirmations(cs)
      setConfStats(cstats)
    } catch {
      // Silent
    } finally {
      setLoading(false)
    }
  }, [since])

  useEffect(() => { load() }, [load])

  const filtered = executions.filter(ex =>
    !searchTerm || ex.agent_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    ex.instruction.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const tabs: { key: Tab; label: string; icon: any }[] = [
    { key: 'overview', label: 'Visao Geral', icon: BarChart3 },
    { key: 'executions', label: 'Execucoes', icon: Activity },
    { key: 'confirmations', label: 'Confirmacoes', icon: Shield },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Observabilidade</h1>
          <p className="text-sm text-zinc-500">Metricas, logs e monitoramento do Studio</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            className="input w-32"
            value={since}
            onChange={(e) => setSince(e.target.value)}
          >
            <option value="1h">Ultima hora</option>
            <option value="24h">Ultimas 24h</option>
            <option value="7d">Ultimos 7 dias</option>
            <option value="30d">Ultimos 30 dias</option>
          </select>
          <button onClick={load} className="btn-ghost flex items-center gap-2" disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-zinc-800">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? 'border-cris-500 text-cris-400'
                : 'border-transparent text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
            {t.key === 'confirmations' && confStats?.pending > 0 && (
              <span className="ml-1 rounded-full bg-yellow-500/20 px-1.5 text-xs text-yellow-400">
                {confStats.pending}
              </span>
            )}
          </button>
        ))}
      </div>

      {loading && !metrics ? (
        <div className="flex h-48 items-center justify-center">
          <Activity className="h-8 w-8 animate-pulse text-cris-500" />
        </div>
      ) : (
        <>
          {/* OVERVIEW TAB */}
          {tab === 'overview' && metrics && (
            <div className="space-y-6">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard
                  label="Total Execucoes"
                  value={metrics.total}
                  icon={Activity}
                  color="text-blue-400"
                />
                <StatCard
                  label="Taxa de Sucesso"
                  value={`${metrics.success_rate}%`}
                  icon={CheckCircle2}
                  color="text-green-400"
                />
                <StatCard
                  label="Tempo Medio"
                  value={`${metrics.avg_duration_ms}ms`}
                  icon={Clock}
                  color="text-yellow-400"
                />
                <StatCard
                  label="Erros"
                  value={metrics.error}
                  icon={AlertCircle}
                  color="text-red-400"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <StatCard
                  label="P95 Latencia"
                  value={`${metrics.p95_duration_ms}ms`}
                  icon={BarChart3}
                  color="text-purple-400"
                />
                <StatCard
                  label="Memory Leituras"
                  value={metrics.memory_reads}
                  icon={Brain}
                  color="text-cyan-400"
                />
                <StatCard
                  label="Permissoes Negadas"
                  value={metrics.permissions_denied}
                  icon={Shield}
                  color="text-orange-400"
                />
              </div>

              {/* By Agent */}
              {Object.keys(metrics.by_agent).length > 0 && (
                <div className="card">
                  <h3 className="mb-3 text-sm font-medium text-zinc-400">Por Agente</h3>
                  <div className="space-y-2">
                    {Object.entries(metrics.by_agent).map(([name, data]) => (
                      <div key={name} className="flex items-center justify-between rounded bg-zinc-800/50 px-3 py-2">
                        <span className="text-sm">{name}</span>
                        <div className="flex items-center gap-4 text-xs text-zinc-500">
                          <span>{data.total} execucoes</span>
                          <span className="text-green-400">{data.success} ok</span>
                          <span className="text-red-400">{data.error} erros</span>
                          <span>{data.avg_ms}ms media</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* By Capability */}
              {Object.keys(metrics.by_capability).length > 0 && (
                <div className="card">
                  <h3 className="mb-3 text-sm font-medium text-zinc-400">Por Capability</h3>
                  <div className="space-y-2">
                    {Object.entries(metrics.by_capability).map(([name, data]) => (
                      <div key={name} className="flex items-center justify-between rounded bg-zinc-800/50 px-3 py-2">
                        <span className="text-sm font-mono">{name}</span>
                        <div className="flex items-center gap-4 text-xs text-zinc-500">
                          <span>{data.total} chamadas</span>
                          <span className="text-green-400">{data.success} ok</span>
                          <span className="text-red-400">{data.error} erros</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* EXECUTIONS TAB */}
          {tab === 'executions' && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
                  <input
                    className="input w-full pl-9"
                    placeholder="Buscar por agente ou instrucao..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <span className="text-xs text-zinc-600">{filtered.length} resultados</span>
              </div>

              <div className="space-y-2">
                {filtered.length === 0 ? (
                  <div className="card flex flex-col items-center justify-center py-12">
                    <Activity className="mb-3 h-10 w-10 text-zinc-600" />
                    <p className="text-sm text-zinc-500">Nenhuma execucao registrada</p>
                  </div>
                ) : (
                  filtered.map(ex => (
                    <div key={ex.id} className="card">
                      <button
                        className="flex w-full items-center justify-between text-left"
                        onClick={() => setExpandedId(expandedId === ex.id ? null : ex.id)}
                      >
                        <div className="flex items-center gap-3">
                          {ex.status === 'success' ? (
                            <CheckCircle2 className="h-4 w-4 text-green-400" />
                          ) : ex.status === 'error' ? (
                            <AlertCircle className="h-4 w-4 text-red-400" />
                          ) : (
                            <Activity className="h-4 w-4 text-zinc-500" />
                          )}
                          <div>
                            <p className="text-sm font-medium">{ex.agent_name}</p>
                            <p className="text-xs text-zinc-500">{ex.instruction}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-zinc-500">
                          <span>{ex.duration_ms.toFixed(1)}ms</span>
                          <span>{new Date(ex.timestamp * 1000).toLocaleTimeString()}</span>
                          {expandedId === ex.id ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </div>
                      </button>

                      {expandedId === ex.id && (
                        <div className="mt-4 space-y-3 border-t border-zinc-800 pt-4">
                          {ex.system_prompt && (
                            <div>
                              <p className="mb-1 text-xs font-medium text-zinc-500">System Prompt</p>
                              <pre className="max-h-32 overflow-auto rounded bg-zinc-800/50 p-2 text-xs text-zinc-400">
                                {ex.system_prompt}
                              </pre>
                            </div>
                          )}
                          {ex.capabilities_called.length > 0 && (
                            <div>
                              <p className="mb-1 text-xs font-medium text-zinc-500">Capabilities Chamadas</p>
                              {ex.capabilities_called.map((c, i) => (
                                <div key={i} className="rounded bg-zinc-800/50 p-2 text-xs">
                                  <span className="font-mono text-cris-400">{c.capability}</span>
                                  <pre className="mt-1 text-zinc-500">{JSON.stringify(c.params, null, 2)}</pre>
                                </div>
                              ))}
                            </div>
                          )}
                          {ex.permissions_denied.length > 0 && (
                            <div>
                              <p className="mb-1 text-xs font-medium text-red-400">Permissoes Negadas</p>
                              {ex.permissions_denied.map((p, i) => (
                                <span key={i} className="mr-2 rounded bg-red-500/10 px-2 py-0.5 text-xs text-red-400">{p}</span>
                              ))}
                            </div>
                          )}
                          {ex.errors.length > 0 && (
                            <div>
                              <p className="mb-1 text-xs font-medium text-red-400">Erros</p>
                              {ex.errors.map((e, i) => (
                                <p key={i} className="text-xs text-red-400">{e}</p>
                              ))}
                            </div>
                          )}
                          {ex.output && (
                            <div>
                              <p className="mb-1 text-xs font-medium text-zinc-500">Output</p>
                              <p className="rounded bg-zinc-800/50 p-2 text-xs text-zinc-400">{ex.output}</p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* CONFIRMATIONS TAB */}
          {tab === 'confirmations' && (
            <div className="space-y-4">
              {confStats && (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <StatCard label="Pendentes" value={confStats.pending} icon={Shield} color="text-yellow-400" />
                  <StatCard label="Confirmadas" value={confStats.confirmed} icon={CheckCircle2} color="text-green-400" />
                  <StatCard label="Rejeitadas" value={confStats.rejected} icon={AlertCircle} color="text-red-400" />
                  <StatCard label="Total" value={confStats.total} icon={BarChart3} color="text-blue-400" />
                </div>
              )}

              {confirmations.length === 0 ? (
                <div className="card flex flex-col items-center justify-center py-12">
                  <Shield className="mb-3 h-10 w-10 text-zinc-600" />
                  <p className="text-sm text-zinc-500">Nenhuma confirmacao pendente</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {confirmations.map(conf => (
                    <div key={conf.id} className="card">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className={`rounded px-1.5 py-0.5 text-xs ${
                              conf.status === 'pending' ? 'bg-yellow-500/20 text-yellow-400' :
                              conf.status === 'confirmed' ? 'bg-green-500/20 text-green-400' :
                              'bg-red-500/20 text-red-400'
                            }`}>
                              {conf.status}
                            </span>
                            <span className="text-sm font-medium">{conf.agent_name}</span>
                          </div>
                          <p className="mt-1 text-xs text-zinc-500">
                            <span className="font-mono">{conf.capability}</span> — {conf.instruction}
                          </p>
                        </div>
                        {conf.status === 'pending' && (
                          <div className="flex gap-2">
                            <button
                              onClick={async () => {
                                await studioApi.confirmAction(conf.id)
                                load()
                              }}
                              className="rounded bg-green-600 px-3 py-1 text-xs text-white hover:bg-green-500"
                            >
                              Confirmar
                            </button>
                            <button
                              onClick={async () => {
                                await studioApi.rejectAction(conf.id)
                                load()
                              }}
                              className="rounded bg-red-600 px-3 py-1 text-xs text-white hover:bg-red-500"
                            >
                              Rejeitar
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function StatCard({ label, value, icon: Icon, color }: {
  label: string; value: string | number; icon: any; color: string
}) {
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-zinc-500">{label}</p>
          <p className="mt-1 text-2xl font-bold">{value}</p>
        </div>
        <Icon className={`h-5 w-5 ${color}`} />
      </div>
    </div>
  )
}
