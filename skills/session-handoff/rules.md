# Regras — Session Handoff

> Regras específicas desta skill. Complementam (não substituem) as regras globais
> em [/rules/always.md](../../rules/always.md) e [/rules/never.md](../../rules/never.md).

## Always (sempre)
- Empacotar o handoff **por sessão** (tag = `session`), para o `resume` recuperar o pacote certo.
- Registrar evento no Event Log em todo `save`/`resume` (rastreabilidade).
- Gravar na **memória permanente local** (`data/cris_os.db`) — fica na máquina da Cris.

## Never (nunca)
- Nunca enviar o handoff para fora (nuvem, e-mail, terceiros) **sem confirmação da Cris** — é só leitura/escrita local.
- Nunca misturar o estado de **sessões diferentes** num mesmo handoff.
- Nunca inventar conteúdo: o pacote reflete só o que está na memória + o que foi informado em `notes`/`next_steps`.
- Nunca apagar handoffs antigos automaticamente (histórico é preservado).
