import { useEffect, useState } from 'react'
import {
  Activity, Bot, CheckCircle, Users, FolderKanban, CheckSquare,
  Brain, Clock, Cpu, Wifi, WifiOff,
} from 'lucide-react'
import { api } from '../lib/api'

interface Status {
  status: string
  modelo_ativo: string
  ods_online: boolean
  ollama_online: boolean
  agentes: number
  projetos: number
  clientes: number
  tarefas_pendentes: number
  conversas: number
  prompts: number
  tempo_resposta_ms: number
}

export default function Dashboard() {
  const [data, setData] = useState<Status | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.status()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Activity className="h-8 w-8 animate-pulse text-cris-500" />
      </div>
    )
  }

  const cards = [
    {
      title: 'Modelo Ativo',
      value: data?.modelo_ativo || '—',
      icon: Cpu,
      color: 'text-blue-400',
    },
    {
      title: 'ODS',
      value: data?.ods_online ? 'Online' : 'Offline',
      icon: data?.ods_online ? Wifi : WifiOff,
      color: data?.ods_online ? 'text-cris-400' : 'text-red-400',
    },
    {
      title: 'Ollama',
      value: data?.ollama_online ? 'Online' : 'Offline',
      icon: data?.ollama_online ? Wifi : WifiOff,
      color: data?.ollama_online ? 'text-cris-400' : 'text-red-400',
    },
    {
      title: 'Agentes',
      value: String(data?.agentes ?? 0),
      icon: Bot,
      color: 'text-purple-400',
    },
    {
      title: 'Projetos',
      value: String(data?.projetos ?? 0),
      icon: FolderKanban,
      color: 'text-orange-400',
    },
    {
      title: 'Clientes',
      value: String(data?.clientes ?? 0),
      icon: Users,
      color: 'text-blue-400',
    },
    {
      title: 'Tarefas Pendentes',
      value: String(data?.tarefas_pendentes ?? 0),
      icon: CheckSquare,
      color: 'text-yellow-400',
    },
    {
      title: 'Conversas',
      value: String(data?.conversas ?? 0),
      icon: Brain,
      color: 'text-cris-400',
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-sm text-zinc-500">Visão geral do CRIS OS</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <div key={card.title} className="card">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-zinc-500">{card.title}</p>
                <p className="mt-1 text-2xl font-bold">{card.value}</p>
              </div>
              <card.icon className={`h-5 w-5 ${card.color}`} />
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card">
          <h3 className="mb-3 text-sm font-medium text-zinc-400">Status do Sistema</h3>
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">API</span>
              <span className="flex items-center gap-1 text-cris-400">
                <CheckCircle className="h-3 w-3" /> Online
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">ODS</span>
              <span className={`flex items-center gap-1 ${data?.ods_online ? 'text-cris-400' : 'text-red-400'}`}>
                {data?.ods_online ? <CheckCircle className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
                {data?.ods_online ? 'Online' : 'Offline'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Ollama</span>
              <span className={`flex items-center gap-1 ${data?.ollama_online ? 'text-cris-400' : 'text-red-400'}`}>
                {data?.ollama_online ? <CheckCircle className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
                {data?.ollama_online ? 'Online' : 'Offline'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Banco de Dados</span>
              <span className="flex items-center gap-1 text-cris-400">
                <CheckCircle className="h-3 w-3" /> SQLite
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Versão</span>
              <span className="text-zinc-400">1.0.0</span>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 className="mb-3 text-sm font-medium text-zinc-400">Recursos</h3>
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Prompts Salvos</span>
              <span className="text-zinc-400">{data?.prompts ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Conversas</span>
              <span className="text-zinc-400">{data?.conversas ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Projetos Ativos</span>
              <span className="text-zinc-400">{data?.projetos ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Clientes</span>
              <span className="text-zinc-400">{data?.clientes ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Tarefas Pendentes</span>
              <span className="text-zinc-400">{data?.tarefas_pendentes ?? 0}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
