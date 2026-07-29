import { useEffect, useState } from 'react'
import { Save, RotateCcw } from 'lucide-react'
import { api } from '../lib/api'

const FIELDS = [
  { key: 'modelo_padrao', label: 'Modelo Padrao', type: 'text' },
  { key: 'temperatura', label: 'Temperatura', type: 'text' },
  { key: 'idioma', label: 'Idioma', type: 'text' },
  { key: 'agente_padrao', label: 'Agente Padrao', type: 'text' },
  { key: 'memoria_ativa', label: 'Memoria Ativa', type: 'text' },
]

export default function Settings() {
  const [config, setConfig] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    api.configuracoes().then(setConfig)
  }, [])

  const save = async () => {
    for (const [key, value] of Object.entries(config)) {
      await api.definirConfig(key, value)
    }
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const reset = async () => {
    await api.resetarConfig()
    const c = await api.configuracoes()
    setConfig(c)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Configuracoes</h1>
        <p className="text-sm text-zinc-500">Preferencias do sistema</p>
      </div>

      <div className="card space-y-4">
        {FIELDS.map((field) => (
          <div key={field.key}>
            <label className="label mb-1 block">{field.label}</label>
            <input
              className="input"
              type={field.type}
              value={config[field.key] || ''}
              onChange={(e) =>
                setConfig((prev) => ({ ...prev, [field.key]: e.target.value }))
              }
            />
          </div>
        ))}

        <div className="flex gap-2 pt-2">
          <button className="btn-primary" onClick={save}>
            <Save className="mr-1 h-4 w-4" />
            {saved ? 'Salvo!' : 'Salvar'}
          </button>
          <button className="btn-secondary" onClick={reset}>
            <RotateCcw className="mr-1 h-4 w-4" /> Resetar
          </button>
        </div>
      </div>
    </div>
  )
}
