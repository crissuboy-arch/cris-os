import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, CartesianGrid, Legend } from 'recharts'
import { Activity, Zap, Clock, Users } from 'lucide-react'
import { studioApi } from '../../lib/api'

const COLORS = ['#22d3ee', '#34d399', '#f59e0b', '#f87171', '#a78bfa', '#fb923c']

export default function StudioExecutiveDashboard() {
  const [metrics, setMetrics] = useState<any>(null)
  const [recent, setRecent] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([studioApi.metrics(), studioApi.metricsRecent(50)])
      .then(([m, r]) => { setMetrics(m); setRecent(r) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-center text-zinc-500">Carregando dashboard...</div>
  if (!metrics) return <div className="p-8 text-center text-zinc-500">Sem dados</div>

  const by_agent = metrics.by_agent || {}
  const by_capability = metrics.by_capability || {}
  const agentData = Object.entries(by_agent).map(([name, v]: [string, any]) => ({
    name, executions: v.total, avg_latency: +(v.avg_latency_ms || 0).toFixed(0)
  }))
  const capData = Object.entries(by_capability).map(([name, v]: [string, any]) => ({
    name, executions: v.total
  }))

  // Build timeline data from recent executions
  const hourly: Record<string, { count: number; success: number; fail: number }> = {}
  recent.forEach((e: any) => {
    const h = new Date(e.started_at || e.timestamp).toISOString().slice(0, 13)
    if (!hourly[h]) hourly[h] = { count: 0, success: 0, fail: 0 }
    hourly[h].count++
    if (e.status === 'success' || e.status === 'completed') hourly[h].success++
    else hourly[h].fail++
  })
  const timelineData = Object.entries(hourly)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-12)
    .map(([hour, v]) => ({ hour: hour.slice(11), ...v }))

  const successRate = recent.length > 0
    ? ((recent.filter((e: any) => ['success', 'completed'].includes(e.status)).length / recent.length) * 100).toFixed(1)
    : '0.0'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard Executivo</h1>
        <p className="text-sm text-zinc-500">Visao geral do CRIS OS Studio</p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="card">
          <Activity className="h-5 w-5 text-cris-400 mb-2" />
          <p className="text-2xl font-bold">{metrics.total_executions}</p>
          <p className="text-xs text-zinc-500">Execucoes Totais</p>
        </div>
        <div className="card">
          <Zap className="h-5 w-5 text-emerald-400 mb-2" />
          <p className="text-2xl font-bold text-emerald-400">{successRate}%</p>
          <p className="text-xs text-zinc-500">Taxa de Sucesso</p>
        </div>
        <div className="card">
          <Clock className="h-5 w-5 text-yellow-400 mb-2" />
          <p className="text-2xl font-bold">{metrics.avg_latency_ms?.toFixed(0) || 0}ms</p>
          <p className="text-xs text-zinc-500">Latencia Media</p>
        </div>
        <div className="card">
          <Users className="h-5 w-5 text-purple-400 mb-2" />
          <p className="text-2xl font-bold">{agentData.length}</p>
          <p className="text-xs text-zinc-500">Agentes Ativos</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-4 text-sm font-medium text-zinc-400">Execucoes por Agente</h2>
          {agentData.length === 0 ? (
            <p className="text-xs text-zinc-500 text-center py-8">Sem dados</p>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={agentData}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="#52525b" />
                <YAxis tick={{ fontSize: 11 }} stroke="#52525b" />
                <Tooltip contentStyle={{ background: '#27272a', border: 'none', borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="executions" fill="#22d3ee" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card">
          <h2 className="mb-4 text-sm font-medium text-zinc-400">Uso por Capability</h2>
          {capData.length === 0 ? (
            <p className="text-xs text-zinc-500 text-center py-8">Sem dados</p>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={capData} dataKey="executions" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }: any) => `${name || ''} ${((percent || 0) * 100).toFixed(0)}%`}>
                  {capData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#27272a', border: 'none', borderRadius: 8, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="card">
        <h2 className="mb-4 text-sm font-medium text-zinc-400">Timeline de Execucoes</h2>
        {timelineData.length === 0 ? (
          <p className="text-xs text-zinc-500 text-center py-8">Sem dados de timeline</p>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={timelineData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
              <XAxis dataKey="hour" tick={{ fontSize: 11 }} stroke="#52525b" />
              <YAxis tick={{ fontSize: 11 }} stroke="#52525b" />
              <Tooltip contentStyle={{ background: '#27272a', border: 'none', borderRadius: 8, fontSize: 12 }} />
              <Legend />
              <Line type="monotone" dataKey="success" stroke="#34d399" name="Sucesso" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="fail" stroke="#f87171" name="Falha" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="card">
        <h2 className="mb-4 text-sm font-medium text-zinc-400">Ultimas Execucoes</h2>
        <div className="space-y-2 max-h-[300px] overflow-y-auto">
          {recent.length === 0 ? (
            <p className="text-xs text-zinc-500 text-center py-4">Nenhuma execucao registrada</p>
          ) : recent.slice(0, 15).map((e: any, i: number) => (
            <div key={i} className="flex items-center justify-between rounded bg-zinc-800/30 px-3 py-2 text-xs">
              <span className="font-mono text-zinc-400">{e.agent_id?.slice(0, 8) || '-'}</span>
              <span className="text-zinc-500">{e.capability}</span>
              <span className={e.status === 'success' || e.status === 'completed' ? 'text-emerald-400' : e.status === 'error' ? 'text-red-400' : 'text-yellow-400'}>
                {e.status}
              </span>
              <span className="text-zinc-500">{e.latency_ms?.toFixed(0) || '-'}ms</span>
              <span className="text-zinc-600">{new Date(e.started_at || e.timestamp).toLocaleTimeString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
