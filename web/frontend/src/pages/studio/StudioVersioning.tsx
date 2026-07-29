import { useEffect, useState } from 'react'
import { History, Diff, RotateCcw, ChevronDown } from 'lucide-react'
import { studioApi } from '../../lib/api'

export default function StudioVersioning() {
  const [agents, setAgents] = useState<any[]>([])
  const [selectedAgent, setSelectedAgent] = useState('')
  const [versions, setVersions] = useState<any[]>([])
  const [diffFrom, setDiffFrom] = useState('')
  const [diffTo, setDiffTo] = useState('')
  const [diff, setDiff] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    studioApi.list().then((r: any) => setAgents(Array.isArray(r) ? r : [])).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedAgent) return
    setLoading(true)
    studioApi.versions(selectedAgent).then((r: any) => {
      setVersions(r.versions || [])
      setDiff(null)
      setDiffFrom('')
      setDiffTo('')
    }).finally(() => setLoading(false))
  }, [selectedAgent])

  const handleDiff = async () => {
    if (!selectedAgent || !diffFrom || !diffTo) return
    const r = await studioApi.versionDiff(selectedAgent, diffFrom, diffTo)
    setDiff(r)
  }

  const handleRestore = async (v: string) => {
    if (!confirm(`Restaurar versao ${v}?`)) return
    await studioApi.restoreVersion(selectedAgent, v)
    alert('Restaurado com sucesso')
  }

  const changed = (d: any): number => {
    if (!d) return 0
    return (d.added?.length || 0) + (d.removed?.length || 0) + (d.changed?.length || 0)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Versionamento</h1>
        <p className="text-sm text-zinc-500">Historico, diff e restauracao de versoes</p>
      </div>

      <div>
        <label className="mb-1 block text-xs text-zinc-500">Agente</label>
        <div className="relative">
          <select
            className="input w-full appearance-none pr-8"
            value={selectedAgent}
            onChange={e => setSelectedAgent(e.target.value)}
          >
            <option value="">Selecione um agente...</option>
            {agents.map((a: any) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500 pointer-events-none" />
        </div>
      </div>

      {selectedAgent && (
        <div className="space-y-4">
          <div className="card">
            <h2 className="mb-3 text-sm font-medium text-zinc-400 flex items-center gap-2">
              <History className="h-4 w-4" /> Versoes ({versions.length})
            </h2>
            {loading ? (
              <p className="text-xs text-zinc-500">Carregando...</p>
            ) : versions.length === 0 ? (
              <p className="text-xs text-zinc-500">Nenhuma versao encontrada</p>
            ) : (
              <div className="space-y-2">
                {versions.map((v, i) => (
                  <div key={v.version} className="flex items-center justify-between rounded bg-zinc-800/50 p-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs bg-cris-500/10 text-cris-400 px-2 py-0.5 rounded">
                          v{v.version}
                        </span>
                        {i === 0 && <span className="text-xs text-zinc-500">atual</span>}
                      </div>
                      <p className="mt-1 text-xs text-zinc-500">
                        {new Date(v.timestamp).toLocaleString()} — {v.change_log || 'sem log'}
                      </p>
                      {v.published && <span className="text-xs text-emerald-500">publicado</span>}
                    </div>
                    {i > 0 && (
                      <button onClick={() => handleRestore(v.version)} className="btn-ghost flex items-center gap-1 text-xs">
                        <RotateCcw className="h-3 w-3" /> Restaurar
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {versions.length >= 2 && (
            <div className="card space-y-3">
              <h2 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
                <Diff className="h-4 w-4" /> Comparar Versoes
              </h2>
              <div className="flex items-center gap-3">
                <select className="input flex-1" value={diffFrom} onChange={e => setDiffFrom(e.target.value)}>
                  <option value="">De...</option>
                  {versions.map(v => <option key={v.version} value={v.version}>v{v.version}</option>)}
                </select>
                <select className="input flex-1" value={diffTo} onChange={e => setDiffTo(e.target.value)}>
                  <option value="">Ate...</option>
                  {versions.map(v => <option key={v.version} value={v.version}>v{v.version}</option>)}
                </select>
                <button onClick={handleDiff} disabled={!diffFrom || !diffTo || diffFrom === diffTo} className="btn-primary flex items-center gap-1">
                  <Diff className="h-4 w-4" /> Comparar
                </button>
              </div>
              {diff && (
                <div className="rounded bg-zinc-800/50 p-3 text-xs">
                  {diff.unchanged ? (
                    <p className="text-zinc-500">Sem alteracoes entre v{diff.from_version} e v{diff.to_version}</p>
                  ) : (
                    <div className="space-y-1">
                      <p className="text-zinc-400">{changed(diff)} campo(s) alterado(s)</p>
                      {diff.added?.map((k: string) => <p key={k} className="text-emerald-400">+ {k}</p>)}
                      {diff.removed?.map((k: string) => <p key={k} className="text-red-400">- {k}</p>)}
                      {diff.changed?.map((c: any) => (
                        <div key={c.path}>
                          <p className="text-yellow-400">~ {c.path}</p>
                          <p className="pl-3 text-zinc-500">{JSON.stringify(c.from)} → {JSON.stringify(c.to)}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
