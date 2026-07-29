import { useRef, useState } from 'react'
import {
  AlertTriangle, ArrowDown, ArrowUp, ChevronDown, ChevronUp, GripVertical,
  Plus, Trash2,
} from 'lucide-react'
import { clsx } from 'clsx'
import type { StudioCapability } from '../../../../lib/api'
import { isSensitive, type AgentForm, type BindingForm, type ParamMapping, type ParamSource } from '../types'

interface Props {
  form: AgentForm
  setForm: React.Dispatch<React.SetStateAction<AgentForm>>
  capabilities: StudioCapability[]
}

const SOURCE_LABELS: Record<ParamSource, string> = {
  fixed: 'Valor fixo',
  instruction: 'Da entrada do usuário',
  context: 'Do contexto',
}

function newBinding(): BindingForm {
  return { keyword: '', capability: '', description: '', priority: 50, params: [] }
}

export default function SectionBindings({ form, setForm, capabilities }: Props) {
  const [expanded, setExpanded] = useState<number | null>(form.bindings.length === 0 ? null : 0)
  const dragIndex = useRef<number | null>(null)
  const [dragOver, setDragOver] = useState<number | null>(null)

  const setBindings = (bindings: BindingForm[]) =>
    setForm(prev => ({ ...prev, bindings }))

  const update = (index: number, patch: Partial<BindingForm>) =>
    setBindings(form.bindings.map((b, i) => (i === index ? { ...b, ...patch } : b)))

  const remove = (index: number) => {
    setBindings(form.bindings.filter((_, i) => i !== index))
    setExpanded(null)
  }

  const move = (index: number, dir: -1 | 1) => {
    const target = index + dir
    if (target < 0 || target >= form.bindings.length) return
    const next = [...form.bindings]
    ;[next[index], next[target]] = [next[target], next[index]]
    setBindings(next)
    setExpanded(target)
  }

  const onDrop = (index: number) => {
    const from = dragIndex.current
    dragIndex.current = null
    setDragOver(null)
    if (from === null || from === index) return
    const next = [...form.bindings]
    const [moved] = next.splice(from, 1)
    next.splice(index, 0, moved)
    setBindings(next)
    setExpanded(index)
  }

  const capOptions = form.selectedCapabilities.length > 0
    ? capabilities.filter(c => form.selectedCapabilities.includes(c.name))
    : capabilities

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Bindings</h2>
        <p className="text-sm text-zinc-500">
          Ligue entradas do usuário (keywords) a capabilities. Arraste para reordenar —
          bindings no topo têm prioridade de resolução.
        </p>
      </div>

      {form.selectedCapabilities.length === 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-blue-500/30 bg-blue-500/10 p-3 text-sm text-blue-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p className="text-xs">
            Nenhuma capability selecionada na seção Capabilities. O seletor abaixo mostra
            todas as disponíveis — mas o recomendado é selecionar primeiro as capabilities do agente.
          </p>
        </div>
      )}

      {form.bindings.length === 0 ? (
        <div className="card flex flex-col items-center py-10 text-center">
          <GripVertical className="mb-2 h-8 w-8 text-zinc-600" aria-hidden="true" />
          <p className="text-sm text-zinc-500">Nenhum binding ainda</p>
          <p className="mb-4 text-xs text-zinc-600">Bindings conectam o que o usuário diz às ações do agente</p>
          <button
            type="button"
            onClick={() => { setBindings([newBinding()]); setExpanded(0) }}
            className="btn-primary flex items-center gap-2"
          >
            <Plus className="h-4 w-4" /> Criar primeiro binding
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {form.bindings.map((b, i) => (
            <BindingCard
              key={i}
              index={i}
              binding={b}
              expanded={expanded === i}
              dragOver={dragOver === i}
              capOptions={capOptions}
              allCapabilities={capabilities}
              onToggleExpand={() => setExpanded(expanded === i ? null : i)}
              onUpdate={patch => update(i, patch)}
              onRemove={() => remove(i)}
              onMove={dir => move(i, dir)}
              isFirst={i === 0}
              isLast={i === form.bindings.length - 1}
              dragProps={{
                draggable: true,
                onDragStart: () => { dragIndex.current = i },
                onDragOver: e => { e.preventDefault(); setDragOver(i) },
                onDragLeave: () => setDragOver(cur => (cur === i ? null : cur)),
                onDrop: () => onDrop(i),
                onDragEnd: () => { dragIndex.current = null; setDragOver(null) },
              }}
            />
          ))}
          <button
            type="button"
            onClick={() => { setBindings([...form.bindings, newBinding()]); setExpanded(form.bindings.length) }}
            className="btn-secondary flex w-full items-center justify-center gap-2"
          >
            <Plus className="h-4 w-4" /> Adicionar binding
          </button>
        </div>
      )}
    </div>
  )
}

// ----------------------------------------------------------------------

interface CardProps {
  index: number
  binding: BindingForm
  expanded: boolean
  dragOver: boolean
  capOptions: StudioCapability[]
  allCapabilities: StudioCapability[]
  isFirst: boolean
  isLast: boolean
  onToggleExpand: () => void
  onUpdate: (patch: Partial<BindingForm>) => void
  onRemove: () => void
  onMove: (dir: -1 | 1) => void
  dragProps: React.HTMLAttributes<HTMLDivElement> & { draggable: boolean }
}

function BindingCard({
  index, binding, expanded, dragOver, capOptions, allCapabilities,
  isFirst, isLast, onToggleExpand, onUpdate, onRemove, onMove, dragProps,
}: CardProps) {
  const cap = allCapabilities.find(c => c.name === binding.capability)
  const capMissing = binding.capability && !cap
  const schemaProps = cap?.input_schema?.properties ?? {}
  const required = cap?.input_schema?.required ?? []

  const setParam = (pIndex: number, patch: Partial<ParamMapping>) =>
    onUpdate({ params: binding.params.map((p, i) => (i === pIndex ? { ...p, ...patch } : p)) })

  const addParam = (key = '') =>
    onUpdate({ params: [...binding.params, { key, source: 'instruction', value: '' }] })

  const removeParam = (pIndex: number) =>
    onUpdate({ params: binding.params.filter((_, i) => i !== pIndex) })

  const unmappedRequired = required.filter(r => !binding.params.some(p => p.key === r))

  return (
    <div
      {...dragProps}
      className={clsx(
        'rounded-lg border bg-zinc-900/40 transition-colors',
        dragOver ? 'border-cris-500' : 'border-zinc-800',
      )}
    >
      <div className="flex items-center gap-2 p-3">
        <span className="cursor-grab text-zinc-600 active:cursor-grabbing" aria-hidden="true">
          <GripVertical className="h-4 w-4" />
        </span>
        <span className="w-6 text-center text-xs font-bold text-zinc-500">{index + 1}</span>
        <div className="min-w-0 flex-1">
          <span className="font-mono text-sm">{binding.keyword || <span className="text-zinc-600">(sem keyword)</span>}</span>
          <span className="mx-2 text-zinc-700">→</span>
          <span className={clsx('font-mono text-sm', capMissing ? 'text-red-400' : 'text-cris-400')}>
            {binding.capability || <span className="text-zinc-600">(sem capability)</span>}
          </span>
        </div>
        <div className="flex items-center gap-0.5">
          <button type="button" onClick={() => onMove(-1)} disabled={isFirst} aria-label={`Mover binding ${index + 1} para cima`}
            className="rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-30">
            <ArrowUp className="h-3.5 w-3.5" />
          </button>
          <button type="button" onClick={() => onMove(1)} disabled={isLast} aria-label={`Mover binding ${index + 1} para baixo`}
            className="rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-30">
            <ArrowDown className="h-3.5 w-3.5" />
          </button>
          <button type="button" onClick={onRemove} aria-label={`Remover binding ${index + 1}`}
            className="rounded p-1 text-zinc-500 hover:bg-red-500/20 hover:text-red-400">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
          <button type="button" onClick={onToggleExpand} aria-expanded={expanded}
            aria-label={expanded ? `Recolher binding ${index + 1}` : `Expandir binding ${index + 1}`}
            className="rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-100">
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="space-y-4 border-t border-zinc-800 p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="label mb-1 block" htmlFor={`b-${index}-keyword`}>Keyword *</label>
              <input
                id={`b-${index}-keyword`}
                className="input font-mono text-xs"
                value={binding.keyword}
                onChange={e => onUpdate({ keyword: e.target.value })}
                placeholder='ex: criar nota'
              />
              <p className="mt-1 text-xs text-zinc-600">Texto na instrução do usuário que ativa este binding</p>
            </div>
            <div>
              <label className="label mb-1 block" htmlFor={`b-${index}-cap`}>Capability *</label>
              <select
                id={`b-${index}-cap`}
                className={clsx('input font-mono text-xs', capMissing && 'border-red-500/50')}
                value={binding.capability}
                onChange={e => onUpdate({ capability: e.target.value, params: [] })}
              >
                <option value="">— selecionar —</option>
                {capOptions.map(c => (
                  <option key={c.name} value={c.name}>{c.name} (v{c.version})</option>
                ))}
                {capMissing && <option value={binding.capability}>{binding.capability} (indisponível)</option>}
              </select>
              {capMissing && (
                <p className="mt-1 flex items-center gap-1 text-xs text-red-400">
                  <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                  Capability não existe no registry
                </p>
              )}
              {cap && isSensitive(cap.name) && (
                <p className="mt-1 text-xs text-yellow-500/80">Capability sensível — configure a confirmação na seção Permissões</p>
              )}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-[1fr_120px]">
            <div>
              <label className="label mb-1 block" htmlFor={`b-${index}-desc`}>Descrição</label>
              <input
                id={`b-${index}-desc`}
                className="input text-xs"
                value={binding.description}
                onChange={e => onUpdate({ description: e.target.value })}
                placeholder="O que este binding faz"
              />
            </div>
            <div>
              <label className="label mb-1 block" htmlFor={`b-${index}-prio`}>Prioridade</label>
              <input
                id={`b-${index}-prio`}
                type="number"
                min={0}
                max={100}
                className="input text-xs"
                value={binding.priority}
                onChange={e => onUpdate({ priority: Number(e.target.value) || 0 })}
              />
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="label">Mapeamento de parâmetros</span>
              <div className="flex gap-1">
                {unmappedRequired.length > 0 && (
                  <button
                    type="button"
                    onClick={() => onUpdate({
                      params: [
                        ...binding.params,
                        ...unmappedRequired.map(k => ({ key: k, source: 'instruction' as ParamSource, value: '' })),
                      ],
                    })}
                    className="btn-ghost text-xs text-blue-400"
                  >
                    + Mapear obrigatórios ({unmappedRequired.length})
                  </button>
                )}
                <button type="button" onClick={() => addParam()} className="btn-ghost text-xs" aria-label="Adicionar parâmetro">
                  <Plus className="h-3 w-3" /> Parâmetro
                </button>
              </div>
            </div>

            {Object.keys(schemaProps).length > 0 && (
              <p className="mb-2 text-xs text-zinc-600">
                Schema de {binding.capability}: {Object.entries(schemaProps).map(([k, v]) => (
                  <span key={k} className={clsx('mr-1 inline-block badge', required.includes(k) ? 'badge-blue' : 'badge-zinc')}>
                    {k}{v.type ? `: ${v.type}` : ''}{required.includes(k) ? ' *' : ''}
                  </span>
                ))}
              </p>
            )}

            {binding.params.length === 0 ? (
              <p className="rounded border border-dashed border-zinc-800 p-3 text-center text-xs text-zinc-600">
                Nenhum parâmetro mapeado. A capability receberá um objeto vazio.
              </p>
            ) : (
              <div className="space-y-2">
                {binding.params.map((p, pi) => (
                  <div key={pi} className="grid gap-2 rounded-md border border-zinc-800 p-2 sm:grid-cols-[140px_170px_1fr_32px]">
                    <input
                      className="input font-mono text-xs"
                      value={p.key}
                      onChange={e => setParam(pi, { key: e.target.value })}
                      placeholder="nome"
                      aria-label={`Nome do parâmetro ${pi + 1}`}
                      list={`b-${index}-props`}
                    />
                    <select
                      className="input text-xs"
                      value={p.source}
                      onChange={e => setParam(pi, { source: e.target.value as ParamSource, value: '' })}
                      aria-label={`Fonte do parâmetro ${pi + 1}`}
                    >
                      {Object.entries(SOURCE_LABELS).map(([v, l]) => (
                        <option key={v} value={v}>{l}</option>
                      ))}
                    </select>
                    {p.source === 'fixed' && (
                      <input
                        className="input font-mono text-xs"
                        value={p.value}
                        onChange={e => setParam(pi, { value: e.target.value })}
                        placeholder={schemaProps[p.key]?.type ? `valor (${schemaProps[p.key].type})` : 'valor fixo'}
                        aria-label={`Valor fixo do parâmetro ${pi + 1}`}
                      />
                    )}
                    {p.source === 'instruction' && (
                      <span className="flex items-center rounded bg-zinc-800/50 px-2 font-mono text-xs text-zinc-400">
                        {'{instruction}'}
                      </span>
                    )}
                    {p.source === 'context' && (
                      <input
                        className="input font-mono text-xs"
                        value={p.value}
                        onChange={e => setParam(pi, { value: e.target.value })}
                        placeholder="campo (ex.: user_id)"
                        aria-label={`Campo de contexto do parâmetro ${pi + 1}`}
                      />
                    )}
                    <button type="button" onClick={() => removeParam(pi)} aria-label={`Remover parâmetro ${pi + 1}`}
                      className="rounded p-1 text-zinc-500 hover:bg-red-500/20 hover:text-red-400">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
                <datalist id={`b-${index}-props`}>
                  {Object.keys(schemaProps).map(k => <option key={k} value={k} />)}
                </datalist>
              </div>
            )}

            {binding.params.some(p => p.source === 'context') && (
              <p className="mt-2 flex items-start gap-1 text-xs text-yellow-500/80">
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                Valores de contexto são salvos no manifesto, mas o runtime atual só interpola
                {'{instruction}'} — resolução de {'{context.*}'} será suportada em fase futura.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
