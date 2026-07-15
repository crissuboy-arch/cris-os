# 🛠️ SDK.md — Como criar Skills no CRIS OS

Guia para criar **novas Skills** seguindo o template oficial. Visão geral em
[SKILLS.md](SKILLS.md) · catálogo em [SKILLS_INDEX.md](SKILLS_INDEX.md).

---

## 1. Criar uma Skill (1 comando)
```powershell
python scripts/new_skill.py minha-skill `
  --title "Minha Skill" `
  --description "O que ela faz, em uma frase." `
  --category geral `
  --agents secretary `
  --tools browser
```
Isso copia `skills/_template/` para `skills/minha-skill/`, preenche os placeholders
e o `manifest.json`. **Toda skill nasce idêntica ao template** (consistência garantida).

> `--agents` e `--tools` são opcionais (declaram a ligação skill↔agente↔tool).

## 2. Os 8 arquivos obrigatórios (template oficial)
Toda Skill tem **exatamente** estes arquivos — o Registry valida a presença deles:

| Arquivo | Para quê |
|---|---|
| `SKILL.md` | o "verbo": o que faz, quando usar, passos, saída, definição de pronto |
| `manifest.json` | metadados (nome, versão, categoria, status, on/off, agents, tools) |
| `README.md` | visão humana da skill |
| `rules.md` | regras always/never específicas da skill |
| `examples.md` | exemplos de uso (entrada → saída) |
| `tools.md` | quais tools/conexões a skill usa |
| `tests.md` | critérios de aceite / testes |
| `version.json` | versão + changelog |

## 3. Schema do `manifest.json`
```json
{
  "name": "minha-skill",        // kebab-case, único (= nome da pasta)
  "title": "Minha Skill",
  "description": "...",
  "version": "0.1.0",            // semver
  "status": "scaffold",          // scaffold | draft | production
  "enabled": false,              // o Registry só ativa se valid && enabled
  "category": "geral",
  "entry": "SKILL.md",
  "agents": [],                  // agentes que podem usá-la
  "tools": [],                   // tools que ela usa
  "inputs": [],                  // (futuro) entradas esperadas
  "outputs": []                  // (futuro) saídas
}
```

## 4. Validação (o que o Registry checa)
- os **8 arquivos** existem;
- `manifest.json` é JSON válido e tem **`name`** e **`version`**.

Skills inválidas continuam listadas, mas marcadas `valid=false` com os problemas
em `issues` (não entram em `registry.enabled()`).

## 5. Versão e ciclo de vida
- Suba a versão em `manifest.json` **e** `version.json` (e registre no `changelog`).
- Evolua o `status`: `scaffold` → `draft` → `production`.
- Habilite/desabilite via Registry: `registry.enable("minha-skill")` /
  `registry.disable(...)`. (Padrão vem do `enabled` do manifesto.)

## 6. Como será executada (fase futura — já preparado)
- A skill implementará a porta **`SkillExecutor`** (`core/contracts/skill.py`):
  `execute(payload, context) -> dict`.
- O **Orquestrador** receberá o `SkillRegistry` (seam já marcado em
  `core/runtime.py`) e acionará skills habilitadas via IntentRouter/WorkflowEngine.
- **Nada disso está implementado agora** — esta é a fundação.

## 7. Boas práticas
- Uma skill = **um job**. Se faz várias coisas, quebre em várias skills.
- Skill ≠ tool: a skill é o procedimento; a ação no mundo é a tool.
- **Read-only por padrão**; ação externa só com confirmação da Cris (ver `rules.md`).
- Escreva `examples.md` antes de implementar — viram os testes.
- Não invente integrações; declare tools planejadas e marque como pendentes.
