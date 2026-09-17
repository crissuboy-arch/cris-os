# Roadmap de Agentes

## Pipeline final (visão, não implementado)

```
DESCOBRIR → VALIDAR → DECIDIR → CRIAR/AFILIAR/COMÉRCIO → PRODUZIR → PUBLICAR
→ ANUNCIAR → MEDIR → OTIMIZAR → ESCALAR
```

Onde estamos hoje: **DESCOBRIR** (`scalaflow_intel`, Marco 1), **VALIDAR +
DECIDIR** (`opportunity_analyst` + Decision Engine, Fase 2), e a partir da
Fase 3 o começo de **CRIAR** — `Product Architect` (propõe hipóteses de
formato + recomendação, com aprovação humana obrigatória) e `Product
Factory` (fundação: gate de aprovação + plano de produção + 1 artefato
textual real). Desde a Fase 2.5 esses agentes já têm **onde buscar
raciocínio real** quando precisam (`llm/openrouter.py`, ver
[CRIS-OS-ARCHITECTURE.md](CRIS-OS-ARCHITECTURE.md#roteamento-por-custo-fase-25)).
Todo o resto (`PRODUZIR` em diante, e a produção *completa* de `CRIAR`) é
só visão — nada além da fundação da Fase 3 foi implementado.

## Agentes futuros (documentação de intenção — NÃO implementar ainda)

| Agente | Papel no pipeline | Status |
|---|---|---|
| Product Architect | Propõe formato de produto (hipóteses + recomendação) | ✅ Implementado (Fase 3) |
| Product Factory | Produz o produto em si (ebook, curso, SaaS, etc.) | 🟡 Fundação implementada (Fase 3) — produção completa é futura |
| Brand Architect | Nome, slogan, cores, direção visual (`ProjectBrain.brand`) | Visão |
| Offer Architect | Estrutura da oferta/preço (`ProjectBrain.produto`) | Visão |
| Sales Page Architect | Landing page (`ProjectBrain.assets.landing_page`) | Visão |
| Creative Director | Direção de criativos (`ProjectBrain.assets.creatives`) | Visão |
| Video Agent | Produção de vídeo (`ProjectBrain.assets.videos`) | Visão |
| Business Builder | Monta o negócio ao redor do produto | Visão |
| Launch Architect | Plano de lançamento | Visão |
| Paid Traffic Architect | Estrutura de campanhas (`ProjectBrain.trafego`) | Visão |
| Performance Agent | Lê resultados de campanha (`ProjectBrain.trafego.results`) | Visão |
| Growth Intelligence | Otimização/escala | Visão |
| Máquina de Leads | Geração de leads | Visão |

Cada um desses, quando vier, deve seguir o mesmo padrão de
`scalaflow_intel`/`opportunity_analyst`: um `SpecialistAgent` +
`Tool`(s), lendo/escrevendo no `ProjectBrain` do projeto em questão via
`project_id` — nunca acoplado ao Telegram.

## Como adicionar um novo agente/Tool

Passo a passo, seguindo o padrão já usado por `scalaflow_intel` e
`opportunity_analyst`:

1. **Tool** em `tools/<nome>_tools.py`: função(ões) puras que fazem o
   trabalho real (consulta, cálculo, etc.) + `get_tools() -> list[Tool]`
   registrando nome, descrição, palavras-chave de match e a função.
2. **Prompt** em `agents/prompts.py`: uma constante `<NOME>_PROMPT` com
   regras explícitas de "nunca inventar dado" quando aplicável, e uma linha
   na lista `AGENTES DISPONIVEIS` do `ROUTING_PROMPT`.
3. **Agente** em `agents/<nome>.py`: `name`, `description`, `system_prompt`,
   `create(llm)` chamando `create_agent(..., tools=get_tools())`.
4. Registrar o módulo em `agents/__init__.py` (`AGENT_MODULES`).
5. Se o agente for **determinístico** (não precisa de LLM para decidir se é
   ele que deve responder), adicionar uma interceptação em
   `agents/orchestrator.py._escolher_agente` (um frozenset de palavras-chave
   + um método `_eh_comando_<nome>` + o `if` correspondente), **na ordem
   certa** em relação a outras interceptações que compartilhem palavras
   (ex.: `opportunity_analyst` é checado antes de `scalaflow_intel` porque
   "investigue... ofertas" contém palavra de ambos).
6. Testes: um arquivo `tests/test_<nome>.py` cobrindo a lógica pura (sem
   rede) + o roteamento determinístico (com um `FakeLLM` que lança exceção
   se for chamado, garantindo que o caminho determinístico nunca usa LLM).
7. Atualizar `tests/test_agent_orchestrator.py::test_discover_agents_carrega_todos`
   (contagem e nomes dos agentes).
8. Documentar em `docs/` seguindo o padrão desta fase.
9. Se o agente **precisar** de raciocínio/análise real (não é determinístico),
   use o provedor `OpenRouterProvider` (`llm/openrouter.py`) na camada de
   custo adequada (ECONÔMICO para classificação/resumo/extração,
   INTELIGENTE para raciocínio mais complexo, PREMIUM só com justificativa) —
   nunca chame uma API de IA nova sem essa camada existente já cobrir o caso.

### Otimização pendente (registrada, não implementada)

O `AgentOrchestrator` usa **o mesmo** LLM para classificar o roteamento
(`_rotear`) e para gerar a resposta do agente geral (`_gerar_com_llm`) — ao
contrário do `Orchestrator` clássico, que já separa os dois papéis via
`llm.for_role("routing")` / `llm.for_role("generation")`. Isso significa que,
quando o OpenRouter está ativo, a classificação de roteamento (que deveria
ser uma tarefa ECONÔMICA e barata) acaba usando o tier INTELIGENTE (mais
caro) — confirmado num teste real na Fase 2.5, onde a chamada de
classificação sozinha gastou 764 tokens de saída. Uma fase futura pode
separar esses dois papéis no `AgentOrchestrator` (igual ao `Orchestrator`
clássico) para plugar o tier ECONÔMICO especificamente na classificação.

## Multi-tenant (visão futura — NÃO construir agora)

Ver a seção "VISÃO FUTURA" em
[MARCO-01-TELEGRAM-SCALAFLOW.md](MARCO-01-TELEGRAM-SCALAFLOW.md) — cada
cliente do ScalaFlow com conta própria, dados isolados, agente próprio,
permissões próprias, memória/contexto próprios, limites de uso, planos de
assinatura, controle de consumo de IA, auditoria multi-tenant. O
`ProjectBrain` já foi desenhado por `project_id` pensando nisso (nenhum
campo assume "existe só uma pessoa usando o sistema"), mas isolar de verdade
por cliente (banco separado ou `tenant_id` em toda consulta,
`TELEGRAM_ALLOWED_USER_ID` por cliente, etc.) é trabalho de uma fase futura
inteira, não desta.

**Passo concreto dado na Fase 3**: o contexto de conversa (qual oportunidade
está em foco) já é isolado por `session` (canal+usuário), persistido via
`UserFocusStore` — não existe mais um único "projeto atual" global
compartilhado. Isso é o alicerce, não a solução completa: `user_id`/
`tenant_id` do `ProductBlueprint` continuam vazios, e não há isolamento de
credenciais/custos por cliente. Ver
[PRODUCT-ARCHITECT.md](PRODUCT-ARCHITECT.md#persistência-por-usuáriochat).

## O que está explicitamente FORA desta fase

- Product Factory / criação de produto **de fato** (a fundação — gate,
  plano, 1 artefato textual — já existe; gerar os ativos completos
  continua fora de escopo).
- Tráfego pago / campanhas reais.
- Conexão com Google Drive.
- Conexão com contas de anúncio (Meta/TikTok/Google Ads).
- Qualquer LLM/API de IA paga **além do OpenRouter** (adicionado na Fase 2.5;
  ver [CRIS-OS-ARCHITECTURE.md](CRIS-OS-ARCHITECTURE.md#roteamento-por-custo-fase-25)).
- Instalação/configuração do Ollama.
- Mudanças visuais ou de schema no ScalaFlow/Supabase.
- Uso automático do tier PREMIUM do OpenRouter em qualquer fluxo (implementado,
  mas não plugado em lugar nenhum — só com justificativa/autorização futura).
