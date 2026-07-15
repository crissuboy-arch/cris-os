# 📇 SKILLS_INDEX.md — Catálogo de Skills

Índice de todas as Skills registradas no CRIS OS. Gerado a partir dos
`skills/<nome>/manifest.json`. Visão geral do sistema em [SKILLS.md](SKILLS.md);
como criar em [SDK.md](SDK.md).

> Atualizado: 2026-06-30 · Total: **5** · Ativas: **1** (`session-handoff`).

| Skill | Versão | Status | Categoria | Agentes | Tools | Habilitada | Descrição |
|---|---|---|---|---|---|---|---|
| `session-handoff` | 1.0.0 | **production** | workflow | `*` | — | **sim** | Empacota/retoma o estado da sessão (contexto, decisões, próximos passos) — Memory + Event Log. |
| `roast` | 0.1.0 | scaffold | feedback | — | — | não | Análise crítica e bem-humorada de texto/ideia/projeto, com sugestões. |
| `browser-tool` | 0.1.0 | scaffold | web | pesquisador, scalaflow, zavix | browser | não | Navegação web (Playwright) leitura/extração: páginas, produtos, links, screenshots, imagens. |
| `curriculum-builder` | 0.1.0 | scaffold | curriculo | curriculo | — | não | Monta e revisa currículos (Currículo Gratuito): estrutura, clareza, resultados. |
| `zavix-product` | 0.1.0 | scaffold | zavix | zavix | — | não | Operações de produto da loja Zavix.online: produto, categorias, links, estoque. |

## Legenda de status
- **scaffold** — só estrutura (os 8 arquivos do template); sem execução.
- **draft** — em construção.
- **production** — pronta para uso.

> Para regenerar este índice no futuro, basta ler os manifests via
> `core.skills.SkillRegistry` (`registry.all()`).
