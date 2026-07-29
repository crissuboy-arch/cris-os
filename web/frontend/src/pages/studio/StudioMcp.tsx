import { useEffect, useState } from 'react'
import { Server, Plus, Trash2, RefreshCw, Play, Search } from 'lucide-react'
import { studioApi } from '../../lib/api'

export default function StudioMcp() {
  const [servers, setServers] = useState<any[]>([])
  const [tools, setTools] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ name: '', command: '', args: '', timeout_s: 30 })
  const [execResult, setExecResult] = useState<any>(null)
  const [execTool, setExecTool] = useState('')
  const [execParams, setExecParams] = useState('{}')

  const load = async () => {
    setLoading(true)
    try {
      const [s, t] = await Promise.all([studioApi.mcpServers(), studioApi.mcpTools()])
      setServers(s)
      setTools(t)
    } catch { /* */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const handleRegister = async () => {
    try {
      await studioApi.registerMcpServer({
        name: form.name,
        command: form.command,
        args: form.args.split(' ').filter(Boolean),
        timeout_s: form.timeout_s,
      })
      setShowAdd(false)
      setForm({ name: '', command: '', args: '', timeout_s: 30 })
      load()
    } catch (e: any) {
      alert(e.message)
    }
  }

  const handleDiscover = async (server?: string) => {
    try {
      await studioApi.discoverMcpTools(server)
      load()
    } catch (e: any) {
      alert(e.message)
    }
  }

  const handleExecute = async () => {
    try {
      const params = JSON.parse(execParams || '{}')
      const result = await studioApi.executeMcpTool(execTool, params)
      setExecResult(result)
    } catch (e: any) {
      setExecResult({ success: false, error: e.message })
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">MCP Servers</h1>
          <p className="text-sm text-zinc-500">Gerencie servidores Model Context Protocol</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => handleDiscover()} className="btn-ghost flex items-center gap-2">
            <Search className="h-4 w-4" /> Descobrir
          </button>
          <button onClick={() => setShowAdd(true)} className="btn-primary flex items-center gap-2">
            <Plus className="h-4 w-4" /> Novo Servidor
          </button>
        </div>
      </div>

      {showAdd && (
        <div className="card space-y-3">
          <h3 className="text-sm font-medium">Novo Servidor MCP</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <input className="input" placeholder="Nome" value={form.name} onChange={e => setForm({...form, name: e.target.value})} />
            <input className="input" placeholder="Comando (ex: npx @modelcontextprotocol/server-...)" value={form.command} onChange={e => setForm({...form, command: e.target.value})} />
            <input className="input" placeholder="Args (separados por espaco)" value={form.args} onChange={e => setForm({...form, args: e.target.value})} />
            <input className="input" type="number" placeholder="Timeout (s)" value={form.timeout_s} onChange={e => setForm({...form, timeout_s: +e.target.value})} />
          </div>
          <div className="flex gap-2">
            <button onClick={handleRegister} className="btn-primary">Registrar</button>
            <button onClick={() => setShowAdd(false)} className="btn-ghost">Cancelar</button>
          </div>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-zinc-400">Servidores ({servers.length})</h2>
          {servers.length === 0 ? (
            <div className="card py-8 text-center text-sm text-zinc-500">Nenhum servidor registrado</div>
          ) : (
            servers.map(s => (
              <div key={s.name} className="card flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Server className="h-4 w-4 text-cris-400" />
                  <div>
                    <p className="text-sm font-medium">{s.name}</p>
                    <p className="text-xs text-zinc-500 font-mono">{s.command}</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleDiscover(s.name)} className="btn-ghost text-xs">Descobrir</button>
                  <button onClick={async () => { await studioApi.unregisterMcpServer(s.name); load() }} className="text-red-400 hover:text-red-300">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="space-y-3">
          <h2 className="text-sm font-medium text-zinc-400">Ferramentas ({tools.length})</h2>
          {tools.length === 0 ? (
            <div className="card py-8 text-center text-sm text-zinc-500">Nenhuma ferramenta descoberta</div>
          ) : (
            tools.map(t => (
              <div key={t.full_name || t.name} className="card cursor-pointer hover:border-cris-500/50" onClick={() => { setExecTool(t.full_name || t.name); setExecParams('{}') }}>
                <p className="text-sm font-medium">{t.name}</p>
                <p className="text-xs text-zinc-500">{t.description}</p>
                <p className="mt-1 text-xs text-zinc-600">Servidor: {t.server}</p>
              </div>
            ))
          )}
        </div>
      </div>

      {execTool && (
        <div className="card space-y-3">
          <h3 className="text-sm font-medium">Executar: {execTool}</h3>
          <textarea
            className="input h-20 font-mono text-xs"
            placeholder='{"key": "value"}'
            value={execParams}
            onChange={e => setExecParams(e.target.value)}
          />
          <div className="flex gap-2">
            <button onClick={handleExecute} className="btn-primary flex items-center gap-2">
              <Play className="h-4 w-4" /> Executar
            </button>
            <button onClick={() => { setExecTool(''); setExecResult(null) }} className="btn-ghost">Fechar</button>
          </div>
          {execResult && (
            <pre className="max-h-40 overflow-auto rounded bg-zinc-800/50 p-3 text-xs text-zinc-400">
              {JSON.stringify(execResult, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
