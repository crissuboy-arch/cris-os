import { useEffect, useState } from 'react'
import { BarChart3, AlertCircle, Clock, Bot, Wrench } from 'lucide-react'
import { api } from '../lib/api'

export default function Logs() {
  const [logs, setLogs] = useState<any[]>([])
  const [metricas, setMetricas] = useState<any>(null)
  const [filtroAgente, setFiltroAgente] = useState('')
  const [filtroErro, setFiltroErro] = useState(false)

  const load = () => {
    api.logs({ limite: 100, agente: filtroAgente || undefined, erro: filtroErro || undefined }).then(setLogs)
    api.metricasLogs().then(setMetricas)
  }

  useEffect(load, [filtroAgente, filtroErro])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Logs</h1>
        <p className="text-sm text-zinc-500">Registro de atividades do sistema</p>
      </div>

      {metricas && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-zinc-500">Total</p>
                <p className="text-xl font-bold">{metricas.total}</p>
              </div>
              <BarChart3 className="h-5 w-5 text-blue-400" />
            </div>
          </div>
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-zinc-500">Erros</p>
                <p className="text-xl font-bold">{metricas.erros}</p>
              </div>
              <AlertCircle className="h-5 w-5 text-red-400" />
            </div>
          </div>
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-zinc-500">Tempo Medio</p>
                <p className="text-xl font-bold">{metricas.media_tempo_ms}ms</p>
              </div>
              <Clock className="h-5 w-5 text-yellow-400" />
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <select className="input w-40" value={filtroAgente} onChange={(e) => setFiltroAgente(e.target.value)}>
          <option value="">Todos os agentes</option>
          {(metricas?.top_agentes || []).map((a: any) => (
            <option key={a.agente} value={a.agente}>{a.agente}</option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-zinc-400">
          <input type="checkbox" checked={filtroErro} onChange={(e) => setFiltroErro(e.target.checked)} />
          So erros
        </label>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800 text-left text-xs text-zinc-500">
              <th className="pb-2 font-medium">Data</th>
              <th className="pb-2 font-medium">Agente</th>
              <th className="pb-2 font-medium">Ferramenta</th>
              <th className="pb-2 font-medium">Modelo</th>
              <th className="pb-2 font-medium">Tempo</th>
              <th className="pb-2 font-medium">Erro</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id} className="border-b border-zinc-800/50 text-zinc-400">
                <td className="py-2 text-xs">{log.criado_em}</td>
                <td className="py-2">{log.agente || '—'}</td>
                <td className="py-2">{log.ferramenta || '—'}</td>
                <td className="py-2 text-xs">{log.modelo || '—'}</td>
                <td className="py-2">{log.duracao_ms}ms</td>
                <td className="py-2">
                  {log.erro ? (
                    <span className="text-red-400">{log.erro}</span>
                  ) : (
                    '—'
                  )}
                </td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr>
                <td colSpan={6} className="py-8 text-center text-zinc-600">
                  Nenhum log encontrado
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
