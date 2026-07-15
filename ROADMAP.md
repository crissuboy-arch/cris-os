# 🗺️ ROADMAP — CRIS OS

Roteiro de evolução do CRIS OS. **Documento de planejamento — nada é implementado
aqui.** Cada fase traz: objetivo, escopo, onde encaixa na arquitetura, **critérios
para começar (gate de entrada)**, **critérios de pronto (done)** e prioridade.

> Atualizado: 2026-06-30 · Arquitetura de referência: [ARQUITETURA.md](ARQUITETURA.md)
> · Regras que valem para tudo: [rules/always.md](rules/always.md) + [rules/never.md](rules/never.md)

---

## 📌 Princípios que valem em TODAS as fases
1. **Só o Orquestrador fala com a Cris.** Agentes/ferramentas nunca falam direto.
2. **Read-only por padrão.** Ação que muda o mundo (comprar, publicar, apagar,
   enviar, pagar) só com **confirmação explícita da Cris**.
3. **Tudo vira evento** no Event Log (auditoria + replicação + failover).
4. **Sem segredos no repositório** (ficam no `.env`).
5. **Não quebrar o que já roda** (v3). Cada fase é aditiva e plugável.
6. **Ganhar antes de promover:** não criar agente/skill para algo que ainda não
   foi feito à mão.

---

## 🧭 Visão geral (prioridade e dependências)

| Fase | Tema | Prioridade | Depende de | Status |
|---|---|---|---|---|
| 1 | Secretária + Telegram + Ollama + memória | P0 | — | ✅ Atual |
| 2 | Browser Tool (Playwright, leitura/extração) | **P1 (próxima)** | Fase 1 estável | 🔴 Planejada |
| 3 | Agenda e Lembretes | P2 | Fase 1 (parcial paralela à 2) | 🔴 Planejada |
| 4 | Agentes Especialistas (produção) | P2→P3 | Modelo com tool-calling; Browser ajuda Zavix/ScalaFlow | 🔴 Planejada |
| 5 | Atendimento | P3 | Fase 4 | 🔴 Planejada |
| 6 | Automação de Conteúdo | P3 | Fase 4 (social-media + mkVideos) | 🔴 Planejada |
| T | Transversais (cognição, L4, 2ª máquina, MCP) | conforme necessidade | — | 🔵 Contínuo |

---

## ✅ Fase 1 — Atual (base operacional)

**Objetivo:** a Cris conversa com a **Secretária IA** pelo Telegram, com IA local.

**Escopo:** Secretária IA · Telegram · Ollama local · Orquestrador · memória
SQLite (4 camadas) · Event Log.

**Onde está:** `core/` (orquestrador/eventos), `channels/telegram/`, `llm/ollama.py`,
`memory/` + `storage/`. Guia: [BOOTSTRAP_FASE1.md](BOOTSTRAP_FASE1.md).

**Critérios de pronto (done):** `python scripts/preflight.py` com token e modelo
`[OK]`; bot responde no Telegram; `Event Log: N>0` e memória persistindo.

---

## 🌐 Fase 2 — Browser Tool (Playwright) · **próxima**

**Objetivo:** dar ao CRIS OS olhos na web — começando **só por leitura e extração**.

**Escopo (apenas leitura no início):**
- abrir páginas · ler produtos · extrair links · capturar screenshots ·
  baixar imagens · organizar arquivos · (clicar em imagens apenas para navegar/ler).

**Regras da Browser Tool (obrigatórias):**
- **Modo seguro por padrão.**
- **Nunca** comprar, publicar, apagar ou enviar formulário **sem confirmação da Cris**.
- **Registrar toda ação no Event Log.**
- Salvar screenshots em **`logs/screenshots/`**.
- **Começar apenas com leitura e extração** (write/ações destrutivas ficam para depois,
  sempre atrás de confirmação).

**Onde encaixa na arquitetura:**
- É uma **Tool** (porta [core/contracts/tool.py](core/contracts/tool.py)) registrada
  no `ToolRegistry` ([core/registry.py](core/registry.py)) — **plugável, sem mexer no núcleo**.
- Usada pelos agentes via **tool-calling** (ex.: `pesquisador`, `scalaflow`, `zavix`).
- Nova dependência: `playwright` (em `requirements.txt`) + `playwright install`.
- Precisa de um **gate de confirmação** (mecanismo de aprovação humana antes de
  qualquer ação não-read-only) — a construir nesta fase. Alinha com
  [rules/never.md](rules/never.md) #2/#7.

**Critérios para COMEÇAR (gate de entrada):**
- Fase 1 rodando estável no Telegram.
- Modelo com **tool-calling** funcionando (ex.: `llama3.1`) — senão a ferramenta
  não é acionada pelos agentes (só pelo fallback manual).
- Decisão tomada sobre o **mecanismo de aprovação** (como a Cris confirma uma ação).

**Critérios de PRONTO (done):**
- Abrir página, ler conteúdo, extrair links e baixar imagem **funcionando em modo
  seguro**.
- Screenshots gravados em `logs/screenshots/`.
- Cada ação da ferramenta gera **evento no Event Log**.
- Qualquer ação fora de leitura **exige e respeita** a confirmação da Cris.

**Riscos:** sites mudam de layout; downloads/arquivos podem encher o disco; nunca
logar dados sensíveis em screenshots públicos. Manter tudo local.

---

## ⏰ Fase 3 — Agenda e Lembretes

**Objetivo:** a Secretária cuida do tempo da Cris de forma **proativa**.

**Escopo:** lembretes pessoais · tarefas com horário · rotina de água, caminhada,
reuniões e produção · (futuro) integração **read-only** com Google Calendar.

**Onde encaixa:**
- **Mensagens proativas:** hoje o canal só responde; será preciso um método
  `send()` na porta `Channel` para o sistema **enviar** sem a Cris perguntar.
- **Agendador/automações:** pasta `automations/` + “hooks” já previstos em
  [rules/always.md](rules/always.md).
- Persistência na **memória temporária (L1)** / tarefas. Google Calendar entra
  como **Tool read-only** mais tarde (não nesta fase).

**Critérios para COMEÇAR:** Fase 1 estável. (Pode andar **em paralelo parcial** com
a Fase 2 — baixo acoplamento.) Definir o agendador (ex.: APScheduler).

**Critérios de PRONTO:** um lembrete dispara no horário certo pelo Telegram; a
rotina diária (água/caminhada/reuniões) é configurável e persistida; cada disparo
vira evento no Event Log. **Google Calendar fica fora** (só desenho).

---

## 👥 Fase 4 — Agentes Especialistas (promover a produção)

**Objetivo:** tirar os especialistas do estado “rascunho” e colocá-los para
trabalhar de verdade, cada um no seu domínio.

**Escopo (agentes):** Zavix · Produtos 3D · Currículos · VitrinePro · ScalaFlow ·
PinkLogic · Social Media · mkVideos.

**Onde encaixa:**
- A maioria **já existe como `draft`** em `agents/` (zavix, vitrinepro, scalaflow,
  pinklogic, social-media, mkvideos, curriculo). Falta **refinar o `SYSTEM.md`**,
  preencher a **memória de projeto (L2)** e marcar `status: production` no manifest.
- **Produtos 3D** ainda não tem pasta própria → criar `agents/produtos-3d/` (plugin:
  só criar a pasta, núcleo intocado).
- Browser Tool (Fase 2) potencializa `pesquisador`/`scalaflow`/`zavix`.

**Critérios para COMEÇAR:** modelo com tool-calling sólido (delegação real do
Orquestrador); memória escopada por projeto validada; idealmente Browser Tool
pronta para os agentes de pesquisa.

**Critérios de PRONTO (por agente):** `SYSTEM.md` específico e testado · memória de
projeto (L2) preenchida no `compendium.md` + `seed.py` · ao menos **uma tarefa real**
executada de ponta a ponta · `status: production`.

---

## 💬 Fase 5 — Atendimento

**Objetivo:** apoio ao atendimento de clientes com tom **humano e natural**.

**Escopo:** atendimento de clientes de currículo, Produtos 3D, sites, Zavix e
VitrinePro · **WhatsApp no futuro**.

**Onde encaixa:**
- Agente `atendimento` (escopo `*`), já existente, promovido na linha da Fase 4.
- **Sempre com gate de aprovação:** rascunha respostas, **não envia** ao cliente
  sem a Cris aprovar ([rules/never.md](rules/never.md) #7).
- **WhatsApp** seria um novo `channel` — **fora desta fase** (só desenho).

**Critérios para COMEÇAR:** Fase 4 com os agentes de produto sólidos; mecanismo de
aprovação (da Fase 2) reutilizado para “enviar ao cliente”.

**Critérios de PRONTO:** o agente gera rascunhos de resposta corretos e no tom
certo, organizados por cliente/produto, **sempre exigindo aprovação** antes de
qualquer envio. WhatsApp permanece planejado.

---

## 🎬 Fase 6 — Automação de Conteúdo

**Objetivo:** transformar uma ideia em pacote de conteúdo pronto para revisão.

**Escopo:** criar roteiro · criar legenda · criar thumbnail · enviar para mkVideos
· preparar posts da semana.

**Onde encaixa:**
- Orquestra os agentes `social-media` + `mkvideos` (Fase 4) — caso clássico de
  **vários agentes numa tarefa** (a síntese do Orquestrador já suporta).
- Thumbnail/preparo de posts podem usar a Browser Tool (Fase 2) para referências.
- **Publicação NÃO é automática** — entrega pacote para a Cris aprovar e postar.

**Critérios para COMEÇAR:** `social-media` e `mkvideos` em produção (Fase 4);
pipeline de conteúdo definido (do briefing ao pacote).

**Critérios de PRONTO:** a partir de um tema, o sistema entrega roteiro + legenda +
sugestão de thumbnail + plano de posts da semana, **para aprovação** — sem publicar.

---

## 🔵 Transversais (entram quando fizer sentido, não são fases numeradas)

| Item | O que é | Quando começar |
|---|---|---|
| **Ativar a Cognição** | Implementar Strategic Planner / Execution Manager / Quality Supervisor (hoje esqueletos inativos) | **Revisar a arquitetura antes** — gate combinado. Bom antes de autonomia pesada (Fases 5–6). |
| **Ingestão na L4** | Ferramenta para indexar documentos/PDF/markdown/repos na Base de Conhecimento | Quando a Cris tiver material para os agentes consultarem (apoia Fases 4–6). |
| **2ª máquina** | Replicação real (Event Log + lease) + backup/snapshots automáticos | Quando o uso diário ficar crítico. Fundação (outbox/lease) já existe. |
| **MCP** | Adaptador para consumir/expor ferramentas via Model Context Protocol | Quando houver ferramentas externas que valham plugar. |

---

## 🧱 Como decidir “é hora da próxima fase?”
1. A fase atual passou nos **critérios de pronto**? (não “quase”.)
2. Os **critérios de entrada** da próxima estão satisfeitos?
3. A mudança é **aditiva e plugável** (não quebra a v3)?
4. As **ações que saem para fora** têm **gate de confirmação**?

Se as quatro respostas forem “sim”, pode começar a próxima. Caso contrário, o
maior ganho está em fechar a fase atual primeiro.
