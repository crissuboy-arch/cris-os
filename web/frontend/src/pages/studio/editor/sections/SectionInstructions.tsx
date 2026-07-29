import type { AgentForm } from '../types'

interface Props {
  form: AgentForm
  setForm: React.Dispatch<React.SetStateAction<AgentForm>>
}

const FIELDS: Array<{
  key: keyof AgentForm['instrucoes']
  label: string
  hint: string
  rows: number
}> = [
  { key: 'prompt', label: 'Prompt principal', hint: 'Instrução central que define o comportamento do agente', rows: 5 },
  { key: 'papel', label: 'Papel do agente', hint: 'Quem o agente é (ex.: "Você é um assistente de vendas...")', rows: 3 },
  { key: 'objetivo', label: 'Objetivo', hint: 'O que o agente deve alcançar em cada interação', rows: 3 },
  { key: 'regras', label: 'Regras', hint: 'Regras que o agente deve sempre seguir (uma por linha)', rows: 4 },
  { key: 'restricoes', label: 'Restrições', hint: 'O que o agente nunca deve fazer (uma por linha)', rows: 4 },
  { key: 'formato_saida', label: 'Formato de saída esperado', hint: 'Como as respostas devem ser estruturadas', rows: 3 },
]

export default function SectionInstructions({ form, setForm }: Props) {
  const setField = (key: keyof AgentForm['instrucoes'], value: string) =>
    setForm(prev => ({ ...prev, instrucoes: { ...prev.instrucoes, [key]: value } }))

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Instruções</h2>
        <p className="text-sm text-zinc-500">
          Defina o comportamento do agente. Estas instruções ficam salvas no manifesto
          e serão usadas pelo runtime na execução.
        </p>
      </div>

      {FIELDS.map(f => (
        <div key={f.key}>
          <label className="label mb-1 block" htmlFor={`inst-${f.key}`}>
            {f.label}
            {f.key === 'prompt' && <span className="text-cris-400"> *</span>}
          </label>
          <textarea
            id={`inst-${f.key}`}
            className="input resize-y font-mono text-xs"
            style={{ minHeight: `${f.rows * 1.6}rem` }}
            value={form.instrucoes[f.key]}
            onChange={e => setField(f.key, e.target.value)}
            placeholder={f.hint}
          />
          <p className="mt-1 text-xs text-zinc-600">{f.hint}</p>
        </div>
      ))}
    </div>
  )
}
