import { useState } from 'react'
import {
  Bot, Brain, Mail, FileText, Calendar, ShoppingCart, Wrench, Sparkles, X,
} from 'lucide-react'
import { clsx } from 'clsx'
import { slugify, type AgentForm } from '../types'

const ICONS = { Bot, Brain, Mail, FileText, Calendar, ShoppingCart, Wrench, Sparkles }
export type IconName = keyof typeof ICONS

export function AgentIcon({ name, className }: { name: string; className?: string }) {
  const Icon = ICONS[name as IconName] ?? Bot
  return <Icon className={className ?? 'h-5 w-5'} aria-hidden="true" />
}

interface Props {
  form: AgentForm
  setForm: React.Dispatch<React.SetStateAction<AgentForm>>
}

export default function SectionGeneral({ form, setForm }: Props) {
  const [tagInput, setTagInput] = useState('')
  const [slugTouched, setSlugTouched] = useState(false)

  const set = <K extends keyof AgentForm>(key: K, value: AgentForm[K]) =>
    setForm(prev => ({ ...prev, [key]: value }))

  const addTag = () => {
    const tag = tagInput.trim().toLowerCase()
    if (tag && !form.tags.includes(tag)) {
      set('tags', [...form.tags, tag])
    }
    setTagInput('')
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Geral</h2>
        <p className="text-sm text-zinc-500">Dados básicos de identificação do agente</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className="label mb-1 block" htmlFor="f-name">Nome *</label>
          <input
            id="f-name"
            className="input"
            value={form.name}
            onChange={e => {
              set('name', e.target.value)
              if (!slugTouched) set('slug', slugify(e.target.value))
            }}
            placeholder="ex: Assistente de Notas"
          />
        </div>

        <div className="sm:col-span-2">
          <label className="label mb-1 block" htmlFor="f-desc">Descrição</label>
          <textarea
            id="f-desc"
            className="input min-h-[80px] resize-y"
            value={form.description}
            onChange={e => set('description', e.target.value)}
            placeholder="O que este agente faz?"
          />
        </div>

        <div>
          <label className="label mb-1 block" htmlFor="f-slug">Slug *</label>
          <input
            id="f-slug"
            className="input font-mono text-xs"
            value={form.slug}
            onChange={e => { setSlugTouched(true); set('slug', e.target.value) }}
            placeholder="assistente-de-notas"
          />
          <p className="mt-1 text-xs text-zinc-600">Identificador único: letras minúsculas, números e hífens</p>
        </div>

        <div>
          <label className="label mb-1 block" htmlFor="f-version">Versão *</label>
          <input
            id="f-version"
            className="input font-mono text-xs"
            value={form.version}
            onChange={e => set('version', e.target.value)}
            placeholder="1.0.0"
          />
        </div>

        <div>
          <label className="label mb-1 block" htmlFor="f-categoria">Categoria</label>
          <input
            id="f-categoria"
            className="input"
            value={form.categoria}
            onChange={e => set('categoria', e.target.value)}
            placeholder="ex: produtividade, vendas"
          />
        </div>

        <div>
          <span className="label mb-1 block">Ícone</span>
          <div className="flex flex-wrap gap-1" role="radiogroup" aria-label="Ícone do agente">
            {Object.keys(ICONS).map(name => (
              <button
                key={name}
                type="button"
                role="radio"
                aria-checked={form.icone === name}
                aria-label={`Ícone ${name}`}
                onClick={() => set('icone', name)}
                className={clsx(
                  'rounded-md border p-2 transition-colors',
                  form.icone === name
                    ? 'border-cris-500 bg-cris-500/10 text-cris-400'
                    : 'border-zinc-800 text-zinc-500 hover:border-zinc-700 hover:text-zinc-300',
                )}
              >
                <AgentIcon name={name} className="h-4 w-4" />
              </button>
            ))}
          </div>
        </div>

        <div className="sm:col-span-2">
          <label className="label mb-1 block" htmlFor="f-tags">Tags</label>
          <div className="flex flex-wrap items-center gap-1 rounded-md border border-zinc-800 bg-zinc-900 p-2">
            {form.tags.map(tag => (
              <span key={tag} className="badge-zinc flex items-center gap-1">
                {tag}
                <button
                  type="button"
                  onClick={() => set('tags', form.tags.filter(t => t !== tag))}
                  aria-label={`Remover tag ${tag}`}
                  className="rounded hover:text-zinc-100"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
            <input
              id="f-tags"
              className="min-w-[120px] flex-1 bg-transparent px-1 py-0.5 text-sm outline-none placeholder:text-zinc-600"
              value={tagInput}
              onChange={e => setTagInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag() }
              }}
              onBlur={addTag}
              placeholder={form.tags.length === 0 ? 'Digite e pressione Enter' : ''}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
