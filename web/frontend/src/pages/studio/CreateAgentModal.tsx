import { useState, useEffect, useCallback } from 'react'
import { X, Loader2 } from 'lucide-react'
import { studioApi } from '../../lib/api'

interface Props {
  onClose: () => void
  onCreated: (id: string) => void
}

export default function CreateAgentModal({ onClose, onCreated }: Props) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose()
  }, [onClose])

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    setError('')
    try {
      const agent = await studioApi.create(name.trim(), description.trim())
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
      <div className="w-full max-w-md rounded-lg border border-zinc-800 bg-zinc-900 p-6 shadow-xl">
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
            <label className="label mb-1 block" htmlFor="agent-description">Descrição</label>
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
              {saving ? 'Criando...' : 'Criar Rascunho'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}