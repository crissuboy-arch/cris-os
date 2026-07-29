import { useState } from 'react'
import { Play, X, Clock, CheckCircle, AlertCircle, Copy, ChevronDown, ChevronUp } from 'lucide-react'
import { studioApi } from '../../../lib/api'

interface Props {
  agentId: string
  agentName: string
  onClose: () => void
}

interface ExecResult {
  success: boolean
  output: string
  execution_id: string
  duration_ms: number
  system_prompt: string
  metadata?: {
    bindings_attempted: any[]
    capabilities_called: any[]
    permissions_checked: any[]
    permissions_denied: any[]
    errors: string[]
  }
}

export default function AgentPlayground({ agentId, agentName, onClose }: Props) {
  const [instruction, setInstruction] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ExecResult | null>(null)
  const [error, setError] = useState('')
  const [showPrompt, setShowPrompt] = useState(false)
  const [showMeta, setShowMeta] = useState(false)

  const handleExecute = async () => {
    if (!instruction.trim()) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await studioApi.execute(agentId, instruction.trim())
      setResult(res)
    } catch (e: any) {
      setError(e.message || 'Erro ao executar')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      handleExecute()
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard?.writeText(text)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="flex w-full max-w-3xl flex-col rounded-xl border border-zinc-800 bg-zinc-900 shadow-2xl" style={{ maxHeight: '85vh' }}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-3">
          <div className="flex items-center gap-2">
            <Play className="h-4 w-4 text-cris-400" />
            <h2 className="text-sm font-semibold">Testar Agente</h2>
            <span className="text-xs text-zinc-500">— {agentName}</span>
          </div>
          <button onClick={onClose} className="rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-100">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Input */}
        <div className="border-b border-zinc-800 px-5 py-4">
          <label className="mb-1.5 block text-xs text-zinc-500">Instrucao</label>
          <textarea
            className="input h-20 w-full resize-none font-mono text-sm"
            placeholder="Digite o que o agente deve fazer..."
            value={instruction}
            onChange={e => setInstruction(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
          />
          <div className="mt-2 flex items-center justify-between">
            <span className="text-[10px] text-zinc-600">Ctrl+Enter para executar</span>
            <button
              onClick={handleExecute}
              disabled={loading || !instruction.trim()}
              className="btn-primary flex items-center gap-1.5 text-xs"
            >
              {loading ? (
                <>
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-zinc-400 border-t-transparent" />
                  Executando...
                </>
              ) : (
                <>
                  <Play className="h-3 w-3" /> Executar
                </>
              )}
            </button>
          </div>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {error && (
            <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-sm text-red-400">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          {result && (
            <div className="space-y-4">
              {/* Status bar */}
              <div className="flex items-center gap-4 text-xs">
                <span className={`flex items-center gap-1 ${result.success ? 'text-emerald-400' : 'text-red-400'}`}>
                  {result.success ? <CheckCircle className="h-3.5 w-3.5" /> : <AlertCircle className="h-3.5 w-3.5" />}
                  {result.success ? 'Sucesso' : 'Erro'}
                </span>
                <span className="flex items-center gap-1 text-zinc-500">
                  <Clock className="h-3.5 w-3.5" />
                  {result.duration_ms.toFixed(0)}ms
                </span>
                <span className="text-zinc-600">ID: {result.execution_id?.slice(0, 8)}</span>
                {result.output && (
                  <button
                    onClick={() => copyToClipboard(result.output)}
                    className="ml-auto flex items-center gap-1 text-zinc-500 hover:text-zinc-300"
                  >
                    <Copy className="h-3 w-3" /> Copiar
                  </button>
                )}
              </div>

              {/* Output */}
              <div>
                <h3 className="mb-1.5 text-xs font-medium text-zinc-400">Resposta</h3>
                <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-lg bg-zinc-950/80 p-3 font-mono text-sm leading-relaxed text-zinc-300 border border-zinc-800/50">
                  {result.output || '(sem saida)'}
                </pre>
              </div>

              {/* System Prompt toggle */}
              {result.system_prompt && (
                <div>
                  <button
                    onClick={() => setShowPrompt(!showPrompt)}
                    className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300"
                  >
                    {showPrompt ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                    System Prompt utilizado
                  </button>
                  {showPrompt && (
                    <pre className="mt-2 max-h-32 overflow-y-auto whitespace-pre-wrap rounded-lg bg-zinc-950/60 p-3 font-mono text-xs text-zinc-400 border border-zinc-800/30">
                      {result.system_prompt}
                    </pre>
                  )}
                </div>
              )}

              {/* Metadata toggle */}
              {result.metadata && (
                <div>
                  <button
                    onClick={() => setShowMeta(!showMeta)}
                    className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300"
                  >
                    {showMeta ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                    Detalhes da execucao
                  </button>
                  {showMeta && (
                    <div className="mt-2 space-y-2 rounded-lg bg-zinc-950/60 p-3 text-xs border border-zinc-800/30">
                      {result.metadata.bindings_attempted?.length > 0 && (
                        <div>
                          <span className="text-zinc-500">Bindings tentados:</span>{' '}
                          <span className="text-zinc-300">{result.metadata.bindings_attempted.join(', ')}</span>
                        </div>
                      )}
                      {result.metadata.capabilities_called?.length > 0 && (
                        <div>
                          <span className="text-zinc-500">Capabilities chamadas:</span>{' '}
                          <span className="text-zinc-300">{result.metadata.capabilities_called.join(', ')}</span>
                        </div>
                      )}
                      {result.metadata.permissions_denied?.length > 0 && (
                        <div>
                          <span className="text-zinc-500">Permissoes negadas:</span>{' '}
                          <span className="text-red-400">{result.metadata.permissions_denied.join(', ')}</span>
                        </div>
                      )}
                      {result.metadata.errors?.length > 0 && (
                        <div>
                          <span className="text-zinc-500">Erros:</span>{' '}
                          <span className="text-red-400">{result.metadata.errors.join('; ')}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {!result && !error && !loading && (
            <div className="py-8 text-center text-sm text-zinc-600">
              Digite uma instrucao e clique Executar para testar o agente.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
