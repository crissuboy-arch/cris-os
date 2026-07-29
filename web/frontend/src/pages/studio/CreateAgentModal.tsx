import { useState, useEffect, useCallback } from 'react'
import { X, Loader2, ChevronDown, Bot, Megaphone, Headphones, ShoppingCart, Code } from 'lucide-react'
import { studioApi, type StudioAgentTemplate } from '../../lib/api'

interface Props {
  onClose: () => void
  onCreated: (id: string) => void
}

const ICON_MAP: Record<string, any> = {
  Bot, Megaphone, Headphones, ShoppingCart, Code,
}

export default function CreateAgentModal({ onClose, onCreated }: Props) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const [templates, setTemplates] = useState<StudioAgentTemplate[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<StudioAgentTemplate | null>(null)
  const [loadingTemplates, setLoadingTemplates] = useState(true)

  useEffect(() => {
    studioApi.templates()
      .then(setTemplates)
      .catch(() => {})
      .finally(() => setLoadingTemplates(false))
  }, [])

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose()
  }, [onClose])

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  const selectTemplate = (template: StudioAgentTemplate) => {
    setSelectedTemplate(template)
    setName(template.name)
    setDescription(template.description)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    setError('')
    try {
      // Create the agent
      const agent = await studioApi.create(name.trim(), description.trim())

      // If a template was selected, apply its configuration
      if (selectedTemplate) {
        const payload: any = {
          name: name.trim(),
          description: description.trim(),
          instructions: selectedTemplate.instructions,
          memory: selectedTemplate.memory,
          permissions: selectedTemplate.permissions,
          tools: selectedTemplate.tools,
          bindings: selectedTemplate.bindings,
        }
        await studioApi.update(agent.agent_id, payload)
      }

      onCreated(agent.agent_id)
    } catch (err: any) {
      setError(err.message || 'Erro ao criar agente')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      role="dialog"
      aria-modal="true"
      aria-label="Criar novo agente"
    >
      <div className="w-full max-w-lg rounded-lg border border-zinc-800 bg-zinc-900 p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Novo Agente</h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-100"
            aria-label="Fechar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Template selector */}
          <div>
            <label className="label mb-1 block">Template</label>
            {loadingTemplates ? (
              <p className="text-xs text-zinc-500">Carregando templates...</p>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {templates.map(t => {
                  const Icon = ICON_MAP[t.icon] || Bot
                  const isSelected = selectedTemplate?.id === t.id
                  return (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => selectTemplate(t)}
                      className={`flex items-start gap-2 rounded-lg border p-2.5 text-left text-xs transition-colors ${
                        isSelected
                          ? 'border-cris-500/50 bg-cris-500/10 text-cris-400'
                          : 'border-zinc-800 bg-zinc-800/30 text-zinc-400 hover:border-zinc-700 hover:text-zinc-300'
                      }`}
                    >
                      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
                      <div>
                        <p className="font-medium">{t.name}</p>
                        <p className="mt-0.5 text-[10px] text-zinc-500 line-clamp-2">{t.description}</p>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
            {selectedTemplate && (
              <button
                type="button"
                onClick={() => { setSelectedTemplate(null); setName(''); setDescription('') }}
                className="mt-1.5 text-[10px] text-zinc-500 hover:text-zinc-300"
              >
                Limpar selecao
              </button>
            )}
          </div>

          <div>
            <label className="label mb-1 block" htmlFor="agent-name">Nome *</label>
            <input
              id="agent-name"
              className="input"
              placeholder="ex: assistente-de-notas"
              value={name}
              onChange={e => setName(e.target.value)}
              autoFocus
            />
          </div>
          <div>
            <label className="label mb-1 block" htmlFor="agent-description">Descricao</label>
            <textarea
              id="agent-description"
              className="input min-h-[80px] resize-y"
              placeholder="O que este agente faz?"
              value={description}
              onChange={e => setDescription(e.target.value)}
            />
          </div>

          {error && (
            <div className="rounded bg-red-500/10 px-3 py-2 text-sm text-red-400" role="alert">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button type="button" onClick={onClose} className="btn-secondary">
              Cancelar
            </button>
            <button type="submit" className="btn-primary flex items-center gap-2" disabled={!name.trim() || saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {saving ? 'Criando...' : selectedTemplate ? 'Criar com Template' : 'Criar Rascunho'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
