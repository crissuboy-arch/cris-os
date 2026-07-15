# Tools — Session Handoff

> Skill ≠ tool. A skill é o job; a tool é a ação no mundo externo.

| Tool | Para quê | Acesso | Status |
|---|---|---|---|
| (nenhuma) | — | — | — |

Esta skill **não usa nenhuma tool externa**. Ela opera **só com recursos internos**
recebidos pelo `SkillContext`:

- **Memory** (`context.memory`): conversa (L1), itens do dia (L1 temporária),
  memória permanente (L3) para gravar/recuperar o handoff. Tudo local.
- **Event Log** (`context.publish`): registra `skill.session_handoff.created` /
  `...resumed`.

Por isso `"tools": []` no `manifest.json`. Nenhuma ação sai para fora — read/write
local apenas (ver [rules.md](rules.md)).
