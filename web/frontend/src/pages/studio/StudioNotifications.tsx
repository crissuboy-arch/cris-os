import { useEffect, useState } from 'react'
import { Bell, Send, CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react'
import { studioApi } from '../../lib/api'

export default function StudioNotifications() {
  const [config, setConfig] = useState<any>(null)
  const [token, setToken] = useState('')
  const [chatId, setChatId] = useState('')
  const [history, setHistory] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    try {
      const [c, h, s] = await Promise.all([
        studioApi.notificationConfig(),
        studioApi.notificationHistory(50),
        studioApi.notificationStats(),
      ])
      setConfig(c)
      setHistory(h)
      setStats(s)
    } catch { /* */ }
  }

  useEffect(() => { load() }, [])

  const handleSave = async () => {
    if (!token || !chatId) return
    setSaving(true)
    try {
      await studioApi.configureNotifications(token, chatId)
      await load()
    } catch (e: any) {
      alert(e.message)
    }
    setSaving(false)
  }

  const typeIcon = (type: string) => {
    switch (type) {
      case 'confirmation_pending': return <Clock className="h-4 w-4 text-yellow-400" />
      case 'approval': return <CheckCircle className="h-4 w-4 text-emerald-400" />
      case 'rejection': return <XCircle className="h-4 w-4 text-red-400" />
      case 'execution_complete': return <Bell className="h-4 w-4 text-cris-400" />
      default: return <AlertTriangle className="h-4 w-4 text-zinc-400" />
    }
  }

  const configured = config?.configured

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Notificacoes</h1>
        <p className="text-sm text-zinc-500">Alertas via Telegram para eventos do Studio</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <div className="card space-y-3">
            <h2 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
              <Bell className="h-4 w-4" /> Configuracao Telegram
            </h2>
            {configured ? (
              <div className="rounded bg-emerald-500/10 p-3 text-sm text-emerald-400">
                Notificacoes configuradas para chat {config.chat_id}
              </div>
            ) : (
              <div className="rounded bg-yellow-500/10 p-3 text-sm text-yellow-400">
                Notificacoes nao configuradas
              </div>
            )}
            <div className="space-y-2">
              <input
                className="input w-full"
                type="password"
                placeholder="Bot Token Telegram"
                value={token}
                onChange={e => setToken(e.target.value)}
              />
              <input
                className="input w-full"
                placeholder="Chat ID"
                value={chatId}
                onChange={e => setChatId(e.target.value)}
              />
            </div>
            <button onClick={handleSave} disabled={!token || !chatId || saving} className="btn-primary w-full">
              {saving ? 'Salvando...' : 'Salvar Configuracao'}
            </button>
          </div>

          {stats && (
            <div className="card space-y-3">
              <h2 className="text-sm font-medium text-zinc-400">Estatisticas</h2>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div>
                  <p className="text-2xl font-bold text-cris-400">{stats.total_sent}</p>
                  <p className="text-xs text-zinc-500">Enviadas</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-emerald-400">{stats.delivered}</p>
                  <p className="text-xs text-zinc-500">Entregues</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-red-400">{stats.failed}</p>
                  <p className="text-xs text-zinc-500">Falhas</p>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="space-y-3">
          <h2 className="text-sm font-medium text-zinc-400">Historico ({history.length})</h2>
          {history.length === 0 ? (
            <div className="card py-8 text-center text-sm text-zinc-500">Nenhuma notificacao enviada</div>
          ) : (
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {history.map((n: any, i: number) => (
                <div key={i} className="card flex items-start gap-3">
                  {typeIcon(n.notification_type)}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="badge-cyan text-xs">{n.notification_type}</span>
                      <span className="text-xs text-zinc-500">
                        {new Date(n.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-zinc-400 truncate">{n.message}</p>
                  </div>
                  <span className={n.success ? 'text-emerald-400' : 'text-red-400'}>
                    {n.success ? 'ok' : 'falha'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
