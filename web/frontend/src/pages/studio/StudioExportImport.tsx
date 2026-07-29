import { useState } from 'react'
import { Download, Upload, CheckCircle, AlertCircle } from 'lucide-react'
import { studioApi } from '../../lib/api'

export default function StudioExportImport() {
  const [agents, setAgents] = useState<any[]>([])
  const [exported, setExported] = useState<any>(null)
  const [importData, setImportData] = useState('')
  const [importResult, setImportResult] = useState<any>(null)
  const [loadingExport, setLoadingExport] = useState(false)

  const handleExport = async () => {
    setLoadingExport(true)
    try {
      const r = await studioApi.list()
      setAgents(Array.isArray(r) ? r : [])
    } catch { /* */ }
    setLoadingExport(false)
  }

  const handleExportAgent = async (id: string) => {
    try {
      const data = await studioApi.exportAgent(id)
      setExported(data)
      navigator.clipboard?.writeText(JSON.stringify(data, null, 2))
    } catch (e: any) {
      alert(e.message)
    }
  }

  const handleImport = async () => {
    try {
      const parsed = JSON.parse(importData)
      const result = await studioApi.importAgent(parsed)
      setImportResult(result)
      setImportData('')
    } catch (e: any) {
      setImportResult({ success: false, error: e.message })
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Export / Import</h1>
        <p className="text-sm text-zinc-500">Exportar e importar agentes como JSON</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <h2 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
            <Download className="h-4 w-4" /> Exportar Agente
          </h2>
          <button onClick={handleExport} className="btn-ghost" disabled={loadingExport}>
            {loadingExport ? 'Carregando...' : 'Listar agentes'}
          </button>
          {agents.length > 0 && (
            <div className="space-y-2">
              {agents.map((a: any) => (
                <div key={a.id} className="card flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{a.name}</p>
                    <p className="text-xs text-zinc-500">{a.id}</p>
                  </div>
                  <button onClick={() => handleExportAgent(a.id)} className="btn-primary flex items-center gap-1 text-xs">
                    <Download className="h-3 w-3" /> Exportar
                  </button>
                </div>
              ))}
            </div>
          )}
          {exported && (
            <div className="card space-y-2">
              <p className="text-sm text-emerald-400">Exportado com sucesso</p>
              <pre className="max-h-40 overflow-auto rounded bg-zinc-800/50 p-3 text-xs text-zinc-400">
                {JSON.stringify(exported, null, 2)}
              </pre>
              <p className="text-xs text-zinc-600">Copiado para a area de transferencia</p>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <h2 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
            <Upload className="h-4 w-4" /> Importar Agente
          </h2>
          <textarea
            className="input h-40 font-mono text-xs"
            placeholder='Cole aqui o JSON exportado...'
            value={importData}
            onChange={e => setImportData(e.target.value)}
          />
          <button onClick={handleImport} disabled={!importData.trim()} className="btn-primary">
            Importar
          </button>
          {importResult && (
            <div className={`card flex items-start gap-2 text-sm ${importResult.success ? 'text-emerald-400' : 'text-red-400'}`}>
              {importResult.success ? <CheckCircle className="h-4 w-4 mt-0.5" /> : <AlertCircle className="h-4 w-4 mt-0.5" />}
              <div>
                {importResult.success ? (
                  <>
                    <p>Importado: <strong>{importResult.agent.name}</strong></p>
                    <p className="text-xs text-zinc-500">ID: {importResult.agent.id}</p>
                  </>
                ) : (
                  <p>{importResult.error}</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
