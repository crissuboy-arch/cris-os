# 🧩 SKILLS.md — Sistema Oficial de Skills do CRIS OS

A camada de **Skills** do CRIS OS: a fundação para **centenas** de jobs repetíveis,
versionados e descobertos automaticamente — sem reescrever o núcleo.

> **Status desta fase:** apenas a **fundação** (SDK + Registry + 5 skills de
> estrutura). **Nenhuma skill executa lógica ainda.** A v3 permanece intacta
> (Event Bus, Memory, Plugins e Orquestrador **não** foram alterados).

---

## 1. O que é uma Skill (e o que NÃO é)
Três níveis distintos na arquitetura:

| Conceito | É… | Exemplo |
|---|---|---|
| **Tool** | uma **ação atômica** no mundo | clicar numa página, chamar uma API |
| **Skill** | um **job empacotado, repetível e versionado** | "montar um currículo", "navegar e extrair" |
| **Agent** | um **papel com julgamento** que orquestra | Secretária, Zavix, Pesquisador |

> Regra de ouro: **"Agentes orquestram Skills; Skills usam Tools."**

## 2. Onde a camada se encaixa (Clean Architecture / SOLID)
```
Agents (papéis)  ──orquestram──►  SKILLS (jobs)  ──usam──►  Tools (ações)
```
| Peça | Onde | Princípio |
|---|---|---|
| `Skill` (entidade do manifesto) | `core/skills/skill.py` | — |
| `SkillExecutor` (contrato de execução **futuro**) | `core/contracts/skill.py` | ISP, DIP |
| `SkillRegistry` (descobre/valida/lista/versão/on-off) | `core/skills/registry.py` | **SRP** |
| `skills/<nome>/` (pacotes do template) | infra/plugin-style | **OCP** (nova skill = nova pasta) |

A camada é **paralela** à descoberta de agentes — **não** usa nem altera o
PluginManager, o Event Bus, a Memory ou o Orquestrador.

## 3. O Skill Registry
Responsabilidades (uma só área — SRP): **descobrir** skills automaticamente,
**carregar** manifests, **validar** estrutura (os 8 arquivos), **listar**,
**habilitar/desabilitar** e **controlar versões**. **Não executa** skills.

Integração: o `core/runtime.py` monta o `SkillRegistry` na inicialização e o
**loga** (ex.: `Skills: 5 descobertas, 0 ativas`). Ele fica disponível em
`CrisOS.skills`, mas **não** é injetado no Orquestrador (preparação, sem alterar a v3).

## 4. As 5 Skills iniciais (estrutura, scaffold)
Catálogo completo em **[SKILLS_INDEX.md](SKILLS_INDEX.md)**.

| Skill | Categoria | Para quem | Status |
|---|---|---|---|
| `roast` | feedback | geral | scaffold |
| `session-handoff` | workflow | geral | scaffold |
| `browser-tool` | web | pesquisador, scalaflow, zavix | scaffold |
| `curriculum-builder` | curriculo | curriculo | scaffold |
| `zavix-product` | zavix | zavix | scaffold |

Todas vêm `enabled: false` e `status: scaffold` — estrutura pronta, execução não.

## 5. Ciclo de vida de uma Skill
`scaffold` (só estrutura) → `draft` (em construção) → `production` (pronta).
Cada skill tem versão (`version.json` + `manifest.json`) e pode ser
**habilitada/desabilitada** pelo registry. Só skills **válidas e habilitadas**
entram em `registry.enabled()`.

## 6. O que ficou preparado para a próxima fase
- **Porta `SkillExecutor`** (`core/contracts/skill.py`) — o contrato de execução
  que cada skill cumprirá; o Orquestrador já tem contra o que programar.
- **Seam no runtime** — um `TODO` marca onde o `SkillRegistry` será passado ao
  IntentRouter/WorkflowEngine para o Orquestrador **acionar** skills.
- **Manifestos** já declaram `agents`/`tools` — a ligação skill↔agente↔tool está
  registrada, pronta para a execução.

## 7. Criar novas Skills
Veja o guia **[SDK.md](SDK.md)**. Atalho:
```powershell
python scripts/new_skill.py minha-skill --title "Minha Skill" --description "Faz X." --category geral
```
