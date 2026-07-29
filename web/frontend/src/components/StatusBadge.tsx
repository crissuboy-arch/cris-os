import { clsx } from 'clsx'

interface Props {
  status: string
  className?: string
}

const labels: Record<string, string> = {
  draft: 'Rascunho',
  published: 'Publicado',
  deactivated: 'Desativado',
  archived: 'Arquivado',
}

const styles: Record<string, string> = {
  draft: 'badge-zinc',
  published: 'badge-green',
  deactivated: 'badge-yellow',
  archived: 'badge-zinc',
}

export default function StatusBadge({ status, className }: Props) {
  return (
    <span className={clsx(styles[status] || 'badge-zinc', 'whitespace-nowrap', className)}>
      {labels[status] || status}
    </span>
  )
}