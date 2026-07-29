import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { clsx } from 'clsx'

interface Props {
  manifest: Record<string, any>
  hasErrors: boolean
}

export default function ManifestPreview({ manifest, hasErrors }: Props) {
  const [copied, setCopied] = useState(false)
  const json = JSON.stringify(manifest, null, 2)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(json)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard indisponível — ignora silenciosamente
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">Manifest</h3>
        <button
          type="button"
          onClick={copy}
          className="btn-ghost flex items-center gap-1 text-xs"
          aria-label="Copiar manifest JSON"
        >
          {copied ? <Check className="h-3 w-3 text-cris-400" /> : <Copy className="h-3 w-3" />}
          {copied ? 'Copiado' : 'Copiar'}
        </button>
      </div>
      <pre
        className={clsx(
          'flex-1 overflow-auto rounded-lg border bg-zinc-950 p-3 font-mono text-[11px] leading-relaxed text-zinc-300',
          hasErrors ? 'border-red-500/40' : 'border-zinc-800',
        )}
        aria-label="Preview do manifest (somente leitura)"
        aria-readonly="true"
      >
        {json}
      </pre>
      {hasErrors && (
        <p className="mt-2 text-xs text-red-400">
          O manifesto contém erros — veja a aba Validação
        </p>
      )}
    </div>
  )
}
