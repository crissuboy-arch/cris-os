# Product Factory

Recebe **somente** um `ProductBlueprint` com `decision_status == "APPROVED"`
e monta o plano inicial de produção. Implementado em `core/product_factory.py`.

A Fase 3 entregou a **fundação**: contrato de entrada/saída, planejamento de
produção (lista fixa de passos), execução de um artefato textual real,
persistência efêmera (só na resposta do Telegram) e o gate de aprovação. A
Fase 4 completou isso (sem duplicar): passos **específicos por tipo de
produto** (ver [PRODUCTION-PLAN.md](PRODUCTION-PLAN.md)), persistência real
no Project Brain (`ProjectBrain.production_plan`), um Artifact Manifest
derivado (ver [ARTIFACT-MANIFEST.md](ARTIFACT-MANIFEST.md)) e um agente
`product_factory` que expõe tudo isso sob demanda pelo Telegram (não só
automaticamente após aprovar). Não gera os ativos completos (imagem, vídeo,
mini-app, landing page publicada) — isso continua fora de escopo (ver
[ROADMAP-AGENTS.md](ROADMAP-AGENTS.md)).

## Gate de aprovação (nunca produz sem aprovação explícita)

```python
def criar_plano_inicial(brain, registry, llm_economico=None) -> PlanoProducao:
    if not brain.blueprint:
        raise ProductFactoryError(...)
    if brain.blueprint.decision_status != "APPROVED":
        raise ProductFactoryError(...)
    ...
```

Testado explicitamente (`tests/test_product_architect.py`): recusa
blueprint `PENDING_APPROVAL`, recusa `REJECTED`, recusa projeto sem
blueprint nenhum. Só aceita `APPROVED`.

## Plano de produção (específico por tipo desde a Fase 4)

`PlanoProducao` lista os passos previstos de um lançamento completo — desde
a Fase 4, a lista de passos depende do `product_type` aprovado (ver
[PRODUCTION-PLAN.md](PRODUCTION-PLAN.md) para a tabela completa por
categoria: mini-app, micro-SaaS, conteúdo digital, afiliado, comércio/revenda,
fallback genérico). Cada passo mapeia para uma capability do
[Tool Registry](TOOL-REGISTRY.md), por exemplo (categoria genérica/Fase 3):

| Passo | Capability | Executado nesta fase? |
|---|---|---|
| Brief/copy inicial do produto | `COPY_GENERATOR` | **Sim** |
| Identidade visual | `IMAGE_GENERATOR` | Não (indisponível de propósito) |
| Mini-app/protótipo | `MINI_APP_BUILDER` | Não (indisponível de propósito) |
| Landing page | `LANDING_PAGE_BUILDER` | Não |
| Código/integrações | `CODE_GENERATOR` | Não |
| Vídeo/criativos | `VIDEO_GENERATOR` | Não |
| Armazenamento de assets | `DRIVE_STORAGE` | Não |
| Repositório de código | `GITHUB` | Não |
| Publicação/deploy | `VERCEL` | Não |

Cada passo fica marcado `concluido`, `pendente` (capability existe mas não
foi executada neste passo) ou `indisponivel` (sem fornecedor definido) —
nunca `concluido` às cegas. Quando vários passos de um mesmo tipo mapeiam
pra `COPY_GENERATOR` (ex.: comércio/revenda), só o **primeiro** é executado
de verdade por chamada — nunca paga pelo mesmo artefato duas vezes.

## Persistência (Fase 4 — antes só existia na resposta do Telegram)

`core/product_factory.py:persistir_plano(brain, plano)` converte o
`PlanoProducao` (efêmero) num `ProductionPlan` guardado em
`ProjectBrain.production_plan` — sobrevive a restart/reboot como qualquer
outro campo do Project Brain (mesma infraestrutura desde a Fase 2). Um
Artifact Manifest (`core/artifact_manifest.py`) é derivado junto e guardado
em `ProjectBrain.artifact_manifest`.

## Único artefato real: `gerar_copy_simples`

Pedido explícito da Fase 3: "execução de pelo menos um artefato textual
simples". `gerar_copy_simples(blueprint, llm=None)`:

- Com OpenRouter (tier **ECONÔMICO**) disponível: pede um brief de até 4
  frases, usando **somente** os campos do blueprint — instruído
  explicitamente a nunca inventar preço/prazo/número ausente.
- Sem OpenRouter: monta um template determinístico direto dos campos do
  blueprint (`"Produto proposto: X. Conceito: Y. ..."`) — nunca trava, nunca
  inventa.

## Segurança

- Assets caros (imagem, vídeo) **não** são gerados automaticamente nesta
  fase — declarado explicitamente no Tool Registry (`observacao`).
- Nada aqui publica, compra domínio, envia e-mail ou executa campanha.
- Nenhuma chamada acontece antes do gate de aprovação passar.

## Limitações conhecidas

- A maioria das capabilities previstas estão registradas mas
  **indisponíveis** de propósito — isso é o estado esperado, não um bug (ver
  [TOOL-REGISTRY.md](TOOL-REGISTRY.md) para a lista completa).
- `MINI_APP_BUILDER`: a Cris já tem um criador próprio de mini-apps (prompt
  → mini sistema/app/protótipo, conectável a Supabase/Firebase). **Não
  integrado ainda** — falta interface/API definida. Marcado
  `AVAILABLE_MANUAL` desde a Fase 4 (disponível pra Cris usar por fora, mas
  a Product Factory não pode executá-la sozinha).
- O agente `product_factory` (Fase 4) só expõe o que já existia — nenhum
  ativo novo (imagem, vídeo, mini-app, landing page publicada) passou a ser
  gerado automaticamente.
