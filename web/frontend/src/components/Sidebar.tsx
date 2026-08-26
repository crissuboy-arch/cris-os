import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Bot, MessageSquare, Brain, FolderKanban,
  Users, CheckSquare, FileText, BarChart3, Settings, ChevronLeft, Palette, Eye,
  Zap, Server, History, Download, Bell, LogOut, Calendar, Clock, AlertTriangle,
} from 'lucide-react'
import { useState } from 'react'
import { clsx } from 'clsx'
import { useAuth } from '../lib/auth'

const links = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/hoje', icon: Calendar, label: 'Hoje' },
  { to: '/tarefas', icon: CheckSquare, label: 'Tarefas' },
  { to: '/projetos', icon: FolderKanban, label: 'Projetos' },
  { to: '/agenda', icon: Clock, label: 'Agenda' },
  { to: '/aguardando', icon: Clock, label: 'Aguardando' },
  { to: '/bloqueados', icon: AlertTriangle, label: 'Bloqueados' },
  { to: '/revisao-semanal', icon: BarChart3, label: 'Revisão Semanal' },
  { to: '/agentes', icon: Bot, label: 'Agentes' },
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/memoria', icon: Brain, label: 'Memoria' },
  { to: '/clientes', icon: Users, label: 'Clientes' },
  { to: '/prompts', icon: FileText, label: 'Prompts' },
  { to: '/logs', icon: BarChart3, label: 'Logs' },
  { to: '/studio', icon: Palette, label: 'Studio' },
  { to: '/studio/executivo', icon: Zap, label: 'Executivo' },
  { to: '/studio/observabilidade', icon: Eye, label: 'Observabilidade' },
  { to: '/studio/mcp', icon: Server, label: 'MCP' },
  { to: '/studio/versioning', icon: History, label: 'Versionamento' },
  { to: '/studio/export', icon: Download, label: 'Export / Import' },
  { to: '/studio/notifications', icon: Bell, label: 'Notificacoes' },
  { to: '/configuracoes', icon: Settings, label: 'Configuracoes' },
]

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const { user, logout } = useAuth()

  return (
    <aside
      className={clsx(
        'flex flex-col border-r border-zinc-800 bg-zinc-900/50 transition-all duration-200',
        collapsed ? 'w-16' : 'w-56',
      )}
    >
      <div className="flex h-14 items-center border-b border-zinc-800 px-4">
        {!collapsed && (
          <span className="text-sm font-semibold text-cris-400">CRIS OS</span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={clsx(
            'ml-auto rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-100',
            collapsed && 'mx-auto',
          )}
        >
          <ChevronLeft className={clsx('h-4 w-4 transition-transform', collapsed && 'rotate-180')} />
        </button>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-cris-500/10 text-cris-400'
                  : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100',
                collapsed && 'justify-center px-2',
              )
            }
          >
            <link.icon className="h-4 w-4 shrink-0" />
            {!collapsed && <span>{link.label}</span>}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-zinc-800 p-3 space-y-2">
        {user && !collapsed && (
          <div className="text-xs text-zinc-500 truncate">
            {user.display_name || user.username} <span className="text-zinc-600">({user.role})</span>
          </div>
        )}
        <button
          onClick={logout}
          className={clsx(
            'flex items-center gap-2 rounded-md px-3 py-2 text-sm text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300 w-full',
            collapsed && 'justify-center px-2',
          )}
          title="Sair"
        >
          <LogOut className="h-4 w-4" />
          {!collapsed && <span>Sair</span>}
        </button>
        <div className={clsx('text-xs text-zinc-600', collapsed && 'text-center')}>
          {collapsed ? 'v1' : 'CRIS OS v1.0.0'}
        </div>
      </div>
    </aside>
  )
}
