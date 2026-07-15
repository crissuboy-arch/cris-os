# 🧩 SKILL — Session Handoff

> Arquivo principal da Skill (o "verbo"). Categoria: `workflow` · Versão: `1.0.0` · Status: **production**.

## O que faz
Empacota o estado da sessão atual (conversa recente, itens do dia, notas e
**próximos passos**) num "handoff" salvo na memória permanente — para a Cris
**retomar depois** ou **em outra máquina** (a memória é o `data/cris_os.db`,
replicável). Também **retoma** a partir do último handoff salvo.

## Quando usar
- A Cris vai parar e quer continuar depois ("salva onde paramos", "handoff").
- Trocar de máquina/sessão e retomar o contexto ("retoma de onde parei").
- Um agente quer registrar um ponto de continuação antes de encerrar uma tarefa longa.

## Entradas (inputs)
- `action`: `"save"` (empacotar) ou `"resume"` (retomar). Padrão: `save`.
- `notes` (opcional): observações livres sobre o ponto atual.
- `next_steps` (opcional): lista de próximos passos.
- Do **contexto** (`SkillContext`): `session`, `memory` (MemoryFacade), `publish`
  (Event Log), `caller` (quem chamou).

## Passos (procedimento)
**save:** 1) lê conversa recente (L1) e itens do dia (L1 temporária); 2) monta o
pacote com notas + próximos passos; 3) grava na memória permanente (L3,
`type="handoff"`, tag = sessão); 4) publica `skill.session_handoff.created` no
Event Log; 5) devolve `handoff_id` + resumo.
**resume:** 1) recupera o último handoff da sessão (L3); 2) publica
`skill.session_handoff.resumed`; 3) devolve o pacote + resumo de retomada.

## Saída (output)
- `ok`, `action`, `handoff_id`, `summary` (texto), `data` (pacote completo),
  e, no resume, `found`.

## Como sei que ficou bom (definição de pronto)
- O `save` persiste um item de `type="handoff"` recuperável depois.
- O `resume` reconstrói o último pacote da **mesma sessão** (e diz quando não há).
- Ambos registram evento no Event Log.
- Funciona acionada por **qualquer agente** ou pelo Orquestrador (via `SkillContext`).
