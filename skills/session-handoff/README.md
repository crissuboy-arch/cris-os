# Session Handoff

**Skill:** `session-handoff` · **Categoria:** `workflow` · **Versão:** `1.0.0` · **Status:** 🟢 production

Empacota o estado da sessão atual (contexto, decisões e próximos passos) para
retomar depois ou em outra máquina. Primeira Skill **completa** do CRIS OS.

## Como é executada
A skill cumpre a porta `core.contracts.skill.SkillExecutor` (`execute(payload, context)`).
Qualquer chamador (um agente, o Orquestrador ou um teste) faz:
```python
from core.skills import SkillRegistry, SkillContext
skill = SkillRegistry().discover("skills").load_executor("session-handoff")
ctx = SkillContext(session=sessao, memory=facade, publish=event_bus.publish, caller="secretary")
skill.execute({"action": "save", "notes": "...", "next_steps": ["..."]}, ctx)
```
> O `manifest.json` traz `"agents": ["*"]` — **qualquer agente** pode usá-la — e
> `"executor": "handler:SessionHandoffSkill"`, que o Registry resolve em `load_executor`.

## Integrações
- **Memory:** lê L1 (conversa/dia) e grava/recupera o handoff em L3 (`type="handoff"`).
- **Event Log:** publica `skill.session_handoff.created` / `...resumed`.
- **Skill Registry:** descoberta + validação + versão + on/off + `load_executor`.

## Arquivos
`SKILL.md` · `manifest.json` · `rules.md` · `examples.md` · `tools.md` · `tests.md` · `version.json` · `handler.py` · `README.md`
