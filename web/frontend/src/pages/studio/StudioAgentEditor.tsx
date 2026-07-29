import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Activity, AlertCircle, ArrowLeft, CheckCircle, FileJson, ListChecks,
  Play, Rocket, Save, Undo2, Eye,
} from 'lucide-react'
import { clsx } from 'clsx'
import {
  studioApi, type StudioAgent, type StudioCapability, type StudioPlugin, type StudioToolType,
} from '../../lib/api'
import StatusBadge from '../../components/StatusBadge'
import SectionNav, { SECTIONS, type SectionId } from './editor/SectionNav'
import SectionGeneral, { AgentIcon } from './editor/sections/SectionGeneral'
import SectionInstructions from './editor/sections/SectionInstructions'
import SectionCapabilities from './editor/sections/SectionCapabilities'
import SectionPlugins from './editor/sections/SectionPlugins'
import SectionTools from './editor/sections/SectionTools'
import SectionMemory from './editor/sections/SectionMemory'
import SectionBindings from './editor/sections/SectionBindings'
import SectionPermissions from './editor/sections/SectionPermissions'
import ManifestPreview from './editor/ManifestPreview'
import ValidationPanel from './editor/ValidationPanel'
import PromptPreview from './editor/PromptPreview'
import AgentPlayground from './editor/AgentPlayground'
import { emptyForm, formToManifest, formToPayload, type AgentForm } from './editor/types'
import { hasErrors, issuesBySection, validateForm, type ValidationIssue } from './editor/validation'

type RightTab = 'manifest' | 'prompt' | 'validacao' | 'resumo'

export default function StudioAgentEditor() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [agent, setAgent] = useState<StudioAgent | null>(null)
  const [capabilities, setCapabilities] = useState<StudioCapability[]>([])
  const [plugins, setPlugins] = useState<StudioPlugin[]>([])
  const [toolTypes, setToolTypes] = useState<StudioToolType[]>([])
  const [otherSlugs, setOtherSlugs] = useState<string[]>([])

  const [form, setForm] = useState<AgentForm | null>(null)
  const [snapshot, setSnapshot] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [section, setSection] = useState<SectionId>('geral')
  const [rightTab, setRightTab] = useState<RightTab>('manifest')
  const [saving, setSaving] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [apiError, setApiError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')
  const [showPlayground, setShowPlayground] = useState(false)

  const formRef = useRef<HTMLElement>(null)

  // ---------------------------------------------------------------
  // Carga inicial
  // ---------------------------------------------------------------
  useEffect(() => {
    if (!id) return
    setLoading(true)
    setLoadError('')
    Promise.all([
      studioApi.get(id),
      studioApi.capabilities().catch(() => [] as StudioCapability[]),
      studioApi.plugins().catch(() => [] as StudioPlugin[]),
      studioApi.tools().catch(() => ({ types: [] as StudioToolType[] })),
      studioApi.list().catch(() => [] as StudioAgent[]),
    ])
      .then(([a, caps, plugs, tools, all]) => {
        setAgent(a)
        setCapabilities(caps)
        setPlugins(plugs)
        setToolTypes(tools.types)
        setOtherSlugs(
          all.filter(x => x.agent_id !== a.agent_id)
            .map(x => x.metadata?.slug)
            .filter(Boolean) as string[],
        )
        const f = emptyForm(a)
        setForm(f)
        setSnapshot(JSON.stringify(f))
      })
      .catch(() => setLoadError('Agente não encontrado'))
      .finally(() => setLoading(false))
  }, [id])

  // ---------------------------------------------------------------
  // Derivados
  // ---------------------------------------------------------------
  const dirty = useMemo(
    () => form !== null && JSON.stringify(form) !== snapshot,
    [form, snapshot],
  )

  const issues: ValidationIssue[] = useMemo(
    () => (form ? validateForm(form, capabilities, otherSlugs) : []),
    [form, capabilities, otherSlugs],
  )
  const errorCount = issues.filter(i => i.level === 'error').length
  const bySection = useMemo(() => issuesBySection(issues), [issues])

  const manifest = useMemo(
    () => (form ? formToManifest(form, agent) : {}),
    [form, agent],
  )

  // ---------------------------------------------------------------
  // Aviso de alterações não salvas
  // ---------------------------------------------------------------
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) { e.preventDefault(); e.returnValue = '' }
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [dirty])

  const goBack = () => {
    if (dirty && !confirm('Existem alterações não salvas. Descartar e sair?')) return
    navigate('/studio/agentes')
  }

  // ---------------------------------------------------------------
  // Ações
  // ---------------------------------------------------------------
  const flashSuccess = (msg: string) => {
    setSuccessMsg(msg)
    setTimeout(() => setSuccessMsg(''), 4000)
  }

  const applyUpdated = (updated: StudioAgent) => {
    setAgent(updated)
    const f = emptyForm(updated)
    setForm(f)
    setSnapshot(JSON.stringify(f))
  }

  const handleSave = async (): Promise<boolean> => {
    if (!id || !form || errorCount > 0) return false
    setSaving(true)
    setApiError('')
    try {
      const updated = await studioApi.update(id, formToPayload(form))
      applyUpdated(updated)
      return true
    } catch (err: any) {
      setApiError(err.message || 'Erro ao salvar')
      return false
    } finally {
      setSaving(false)
    }
  }

  const handlePublish = async () => {
    if (!id || !form || errorCount > 0) return
    if (dirty) {
      if (!confirm('Existem alterações não salvas. Salvar e publicar agora?')) return
      const saved = await handleSave()
      if (!saved) return
    }
    setPublishing(true)
    setApiError('')
    try {
      const published = await studioApi.publish(id)
      applyUpdated(published)
      flashSuccess(`Publicado: v${published.version} registrada no AgentRegistry`)
    } catch (err: any) {
      setApiError(err.message || 'Erro ao publicar')
    } finally {
      setPublishing(false)
    }
  }

  const handleSaveDraft = async () => {
    const saved = await handleSave()
    if (saved) flashSuccess('Rascunho salvo com sucesso')
  }

  const handleCancel = () => {
    if (!dirty) return
    if (!confirm('Descartar todas as alterações não salvas?')) return
    setForm(JSON.parse(snapshot) as AgentForm)
    setApiError('')
  }

  const goToSection = (s: string) => {
    if (SECTIONS.some(sec => sec.id === s)) setSection(s as SectionId)
    formRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // ---------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------
  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Activity className="h-8 w-8 animate-pulse text-cris-500" />
      </div>
    )
  }

  if (loadError || !form || !agent) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3">
        <AlertCircle className="h-8 w-8 text-red-400" />
        <p className="text-sm text-zinc-500">{loadError || 'Erro ao carregar agente'}</p>
        <button onClick={() => navigate('/studio/agentes')} className="btn-secondary">Voltar</button>
      </div>
    )
  }

  const isPublished = agent.status === 'published'

  /** setForm tipado como não-nulo (após os guards acima, form sempre existe). */
  const updateForm: React.Dispatch<React.SetStateAction<AgentForm>> = (action) => {
    setForm(prev => {
      if (prev === null) return prev
      return typeof action === 'function' ? (action as (p: AgentForm) => AgentForm)(prev) : action
    })
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <header className="flex flex-wrap items-center gap-3 border-b border-zinc-800 pb-4">
        <button onClick={goBack} className="btn-ghost p-1" aria-label="Voltar para lista de agentes">
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span className="text-cris-400"><AgentIcon name={form.icone} className="h-6 w-6" /></span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="truncate text-lg font-bold">{form.name || '(sem nome)'}</h1>
              <StatusBadge status={agent.status} />
              <span className="badge-zinc font-mono">v{form.version}</span>
              {dirty && <span className="badge-yellow">não salvo</span>}
            </div>
            <p className="truncate text-xs text-zinc-500">{agent.agent_id}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {successMsg && (
            <span className="flex items-center gap-1 text-xs text-cris-400" role="status">
              <CheckCircle className="h-3.5 w-3.5" /> {successMsg}
            </span>
          )}
          <button
            onClick={handleCancel}
            disabled={!dirty}
            className="btn-ghost flex items-center gap-1 text-xs"
            aria-label="Cancelar alterações"
          >
            <Undo2 className="h-3.5 w-3.5" /> Cancelar
          </button>
          <button
            onClick={handleSaveDraft}
            disabled={!dirty || saving || errorCount > 0}
            className="btn-secondary flex items-center gap-2"
            title={errorCount > 0 ? 'Corrija os erros antes de salvar' : undefined}
          >
            {saving ? <Activity className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Salvar rascunho
          </button>
          <button
            onClick={() => setShowPlayground(true)}
            disabled={!agent}
            className="btn-ghost flex items-center gap-2"
            title={!agent ? 'Salve o agente antes de testar' : 'Testar agente'}
          >
            <Play className="h-4 w-4" /> Testar
          </button>
          <button
            onClick={handlePublish}
            disabled={publishing || errorCount > 0 || form.bindings.length === 0}
            className="btn-primary flex items-center gap-2"
            title={
              errorCount > 0
                ? 'Corrija os erros antes de publicar'
                : form.bindings.length === 0
                  ? 'Adicione pelo menos um binding para publicar'
                  : isPublished ? 'Republicar agente' : 'Publicar agente'
            }
          >
            {publishing ? <Activity className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
            {isPublished ? 'Republicar' : 'Publicar'}
          </button>
        </div>
      </header>

      {apiError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400" role="alert">
          <AlertCircle className="h-4 w-4 shrink-0" /> {apiError}
        </div>
      )}

      {/* Nav mobile */}
      <div className="flex gap-1 overflow-x-auto lg:hidden" role="tablist" aria-label="Seções do editor">
        {SECTIONS.map(s => (
          <button
            key={s.id}
            role="tab"
            aria-selected={section === s.id}
            onClick={() => setSection(s.id)}
            className={clsx(
              'flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs',
              section === s.id ? 'bg-cris-500/10 text-cris-400' : 'text-zinc-400',
            )}
          >
            <s.icon className="h-3 w-3" aria-hidden="true" /> {s.label}
            {(bySection.get(s.id)?.length ?? 0) > 0 && (
              <span className="badge-red px-1">{bySection.get(s.id)!.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Corpo: nav | editor | painel direito */}
      <div className="grid gap-4 lg:grid-cols-[180px_minmax(0,1fr)_340px]">
        {/* Nav esquerda */}
        <aside className="hidden lg:block">
          <SectionNav active={section} onChange={setSection} issues={issues} />
        </aside>

        {/* Centro */}
        <main ref={formRef} aria-live="polite" className="min-w-0">
          {section === 'geral' && <SectionGeneral form={form} setForm={updateForm} />}
          {section === 'instrucoes' && <SectionInstructions form={form} setForm={updateForm} />}
          {section === 'capabilities' && <SectionCapabilities form={form} setForm={updateForm} capabilities={capabilities} />}
          {section === 'plugins' && <SectionPlugins form={form} setForm={updateForm} plugins={plugins} />}
          {section === 'tools' && <SectionTools form={form} setForm={updateForm} toolTypes={toolTypes} />}
          {section === 'memory' && <SectionMemory form={form} setForm={updateForm} />}
          {section === 'bindings' && <SectionBindings form={form} setForm={updateForm} capabilities={capabilities} />}
          {section === 'permissoes' && <SectionPermissions form={form} setForm={updateForm} capabilities={capabilities} />}
          {section === 'manifest' && (
            <div>
              <h2 className="mb-1 text-lg font-semibold">Manifest</h2>
              <p className="mb-4 text-sm text-zinc-500">
                Preview em tempo real do manifesto gerado. Somente leitura — sincronizado com o formulário.
              </p>
              <ManifestPreview manifest={manifest} hasErrors={errorCount > 0} />
            </div>
          )}
          {section === 'validacao' && (
            <div>
              <h2 className="mb-1 text-lg font-semibold">Validação</h2>
              <p className="mb-4 text-sm text-zinc-500">
                Verificação em tempo real. Erros bloqueiam salvar e publicar; avisos são recomendações.
              </p>
              <ValidationPanel issues={issues} onGoToSection={goToSection} />
            </div>
          )}
        </main>

        {/* Painel direito */}
        <aside className="hidden rounded-lg border border-zinc-800 bg-zinc-900/30 p-3 lg:block">
          <div className="mb-3 flex gap-1" role="tablist" aria-label="Painel lateral">
            {([
              { id: 'manifest', label: 'Manifest', icon: FileJson },
              { id: 'prompt', label: 'Prompt', icon: Eye },
              { id: 'validacao', label: 'Validação', icon: ListChecks },
              { id: 'resumo', label: 'Resumo', icon: CheckCircle },
            ] as Array<{ id: RightTab; label: string; icon: any }>).map(t => (
              <button
                key={t.id}
                role="tab"
                aria-selected={rightTab === t.id}
                onClick={() => setRightTab(t.id)}
                className={clsx(
                  'flex items-center gap-1 rounded-md px-2 py-1 text-xs transition-colors',
                  rightTab === t.id ? 'bg-cris-500/10 text-cris-400' : 'text-zinc-500 hover:text-zinc-100',
                )}
              >
                <t.icon className="h-3 w-3" aria-hidden="true" /> {t.label}
                {t.id === 'validacao' && issues.length > 0 && (
                  <span className={errorCount > 0 ? 'badge-red px-1' : 'badge-yellow px-1'}>{issues.length}</span>
                )}
              </button>
            ))}
          </div>
          <div className="max-h-[70vh] overflow-y-auto">
            {rightTab === 'manifest' && <ManifestPreview manifest={manifest} hasErrors={errorCount > 0} />}
            {rightTab === 'prompt' && <PromptPreview form={form} agentName={form.name} description={form.description} />}
            {rightTab === 'validacao' && <ValidationPanel issues={issues} onGoToSection={goToSection} />}
            {rightTab === 'resumo' && (
              <div className="space-y-2 text-sm">
                {([
                  ['Capabilities', form.selectedCapabilities.length],
                  ['Plugins', form.selectedPlugins.length],
                  ['Bindings', form.bindings.length],
                  ['Tools internas', form.tools.internal.length],
                  ['Memória', form.memoryMode],
                  ['Confirmações', form.requireConfirmation.length],
                  ['Timeout', `${form.config.timeout_ms}ms`],
                  ['Máx. iterações', form.config.max_iterations],
                ] as Array<[string, string | number]>).map(([k, v]) => (
                  <div key={k} className="flex justify-between border-b border-zinc-800/50 pb-1">
                    <span className="text-zinc-500">{k}</span>
                    <span className="text-zinc-300">{v}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      </div>

      {/* Agent Playground Modal */}
      {showPlayground && agent && (
        <AgentPlayground
          agentId={agent.agent_id}
          agentName={agent.name}
          onClose={() => setShowPlayground(false)}
        />
      )}
    </div>
  )
}
