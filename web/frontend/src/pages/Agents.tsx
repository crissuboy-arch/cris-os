import { useEffect, useState } from 'react'
import { Bot, Wrench, Play, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '../lib/api'

interface Agent {
  nome: string
  descricao: string
  status: string
  ferramentas: string[]
}

export default function Agents() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [testMsg, setTestMsg] = useState('')
  const [testResult, setTestResult] = useState('')

  useEffect(() => {
    api.agents().then(setAgents).catch(() => setAgents([]))
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Agentes</h1>
        <p className="text-sm text-zinc-500">{agents.length} agentes disponiveis</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {agents.map((agent) => (
          <div key={agent.nome} className="card">
            <button
              onClick={() => setExpanded(expanded === agent.nome ? null : agent.nome)}
              className="flex w-full items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <Bot className="h-5 w-5 text-cris-400" />
                <div className="text-left">
                  <p className="font-medium">{agent.nome}</p>
                  <p className="text-xs text-zinc-500">{agent.descricao}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`badge ${agent.status === 'ativo' ? 'badge-green' : 'badge-red'}`}>
                  {agent.status}
                </span>
                {expanded === agent.nome ? (
                  <ChevronUp className="h-4 w-4 text-zinc-500" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-zinc-500" />
                )}
              </div>
            </button>

            {expanded === agent.nome && (
              <div className="mt-4 space-y-4 border-t border-zinc-800 pt-4">
                {agent.ferramentas.length > 0 && (
                  <div>
                    <p className="mb-2 flex items-center gap-1 text-xs text-zinc-500">
                      <Wrench className="h-3 w-3" /> Ferramentas ({agent.ferramentas.length})
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {agent.ferramentas.map((t) => (
                        <span key={t} className="badge-zinc">{t}</span>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <p className="mb-2 text-xs text-zinc-500">Teste rapido</p>
                  <div className="flex gap-2">
                    <input
                      className="input flex-1"
                      placeholder="Digite uma mensagem..."
                      value={testMsg}
                      onChange={(e) => setTestMsg(e.target.value)}
                    />
                    <button
                      className="btn-primary"
                      onClick={async () => {
                        if (!testMsg) return
                        try {
                          const res = await api.chat(testMsg, agent.nome)
                          setTestResult(res.resposta)
                        } catch (e: any) {
                          setTestResult(`Erro: ${e.message}`)
                        }
                      }}
                    >
                      <Play className="mr-1 h-3 w-3" /> Testar
                    </button>
                  </div>
                  {testResult && (
                    <div className="mt-2 rounded bg-zinc-800/50 p-3 text-sm text-zinc-300">
                      {testResult}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
