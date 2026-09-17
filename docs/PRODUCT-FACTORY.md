# Product Factory (Fundação)

Recebe **somente** um `ProductBlueprint` com `decision_status == "APPROVED"`
e monta o plano inicial de produção. Implementado em `core/product_factory.py`.

Esta fase entrega a **fundação**: contrato de entrada/saída, planejamento
de produção, execução de um artefato textual real, persistência e o gate de
aprovação. Não gera os ativos completos (imagem, vídeo, mini-app, landing
page) — isso é trabalho de fases futuras (ver
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

## Plano de produção

`PlanoProducao` lista os passos previstos de um lançamento completo — cada
um mapeado para uma capability do [Tool Registry](TOOL-REGISTRY.md):

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
nunca `concluido` às cegas.

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

- 8 das 9 capabilities previstas estão registradas mas **indisponíveis** de
  propósito — isso é o estado esperado desta fase, não um bug.
- `MINI_APP_BUILDER`: a Cris já tem um criador próprio de mini-apps (prompt
  → mini sistema/app/protótipo, conectável a Supabase/Firebase). **Não
  integrado ainda** — falta interface/API definida (explicitamente fora de
  escopo desta correção).
