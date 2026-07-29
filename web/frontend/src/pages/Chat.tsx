import { useEffect, useRef, useState } from 'react'
import { Send, Trash2, Bot, User } from 'lucide-react'
import { api } from '../lib/api'

interface Mensagem {
  papel: string
  conteudo: string
  agente?: string
}

export default function Chat() {
  const [mensagens, setMensagens] = useState<Mensagem[]>([])
  const [input, setInput] = useState('')
  const [agente, setAgente] = useState('auto')
  const [agents, setAgents] = useState<string[]>([])
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.agents().then((a) => setAgents(a.map((x: any) => x.nome)))
    api.historico().then((h) => setMensagens(h.reverse())).catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensagens])

  const enviar = async () => {
    if (!input.trim() || sending) return
    setSending(true)
    const msg = input.trim()
    setInput('')
    setMensagens((prev) => [...prev, { papel: 'user', conteudo: msg, agente }])

    try {
      const res = await api.chat(msg, agente)
      setMensagens((prev) => [
        ...prev,
        { papel: 'assistant', conteudo: res.resposta, agente: res.agente },
      ])
    } catch (e: any) {
      setMensagens((prev) => [
        ...prev,
        { papel: 'assistant', conteudo: `Erro: ${e.message}` },
      ])
    }
    setSending(false)
  }

  const limpar = async () => {
    await api.limparHistorico()
    setMensagens([])
  }

  return (
    <div className="flex h-[calc(100vh-6rem)] flex-col">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Chat</h1>
          <p className="text-sm text-zinc-500">Converse com os agentes</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="input w-40"
            value={agente}
            onChange={(e) => setAgente(e.target.value)}
          >
            <option value="auto">Auto (Orquestrador)</option>
            {agents.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
          <button className="btn-ghost" onClick={limpar} title="Limpar conversa">
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
        {mensagens.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-zinc-600">Inicie uma conversa com os agentes do CRIS OS</p>
          </div>
        )}
        {mensagens.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.papel === 'user' ? 'justify-end' : ''}`}>
            <div className={`flex max-w-[80%] gap-3 ${m.papel === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`flex h-8 w-8 items-center justify-center rounded-full ${
                m.papel === 'user' ? 'bg-cris-500/20' : 'bg-zinc-800'
              }`}>
                {m.papel === 'user' ? (
                  <User className="h-4 w-4 text-cris-400" />
                ) : (
                  <Bot className="h-4 w-4 text-zinc-400" />
                )}
              </div>
              <div>
                <div className={`rounded-lg px-4 py-2 text-sm ${
                  m.papel === 'user'
                    ? 'bg-cris-600 text-white'
                    : 'bg-zinc-800 text-zinc-200'
                }`}>
                  <p className="whitespace-pre-wrap">{m.conteudo}</p>
                </div>
                {m.agente && m.papel === 'assistant' && (
                  <p className="mt-1 text-xs text-zinc-600">via {m.agente}</p>
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="mt-4 flex gap-2">
        <input
          className="input flex-1"
          placeholder="Digite sua mensagem..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && enviar()}
          disabled={sending}
        />
        <button className="btn-primary" onClick={enviar} disabled={sending || !input.trim()}>
          <Send className="mr-1 h-4 w-4" />
          {sending ? '...' : 'Enviar'}
        </button>
      </div>
    </div>
  )
}
