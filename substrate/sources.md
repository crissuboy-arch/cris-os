# Substrate — Fontes (sources.md)

> **Camada 2.** Onde está a matéria-prima de conhecimento do CRIS OS. O que já foi
> destilado vive em [compendium.md](compendium.md); o runtime guarda no banco
> `data/cris_os.db` (memória L2 projetos / L3 permanente / L4 base de conhecimento).

## Fontes de conhecimento
| Fonte | Onde | O que tem | Sensível? | Status |
|---|---|---|---|---|
| Ficha da Cris + projetos | `substrate/compendium.md`, `brain.md` | quem é a Cris, 9 projetos, estilo | não | reunido |
| Seed do runtime | `memory/seed.py` | semeia L3 (permanente) + L2 (projetos) no 1º boot | não | reunido |
| Cargos dos agentes | `agents/<nome>/SYSTEM.md` + `manifest.json` | domínio e escopo de cada agente | não | reunido |
| Arquitetura | `ARQUITETURA.md` | como o sistema funciona | não | reunido |
| Segredos | `.env` (**FORA do repo**) | token do Telegram, config do Ollama | **SIM** | fora do repo (correto) |
| Documentos/PDF/repos da Cris | (a reunir) | material bruto para a Base de Conhecimento (L4) | a definir | **pendente** |

## Pendente de reunir (para a L4 / Base de Conhecimento)
- Documentos, PDFs, prompts e repositórios que a Cris queira que os agentes
  consultem. A ingestão usa `KnowledgeBaseMemory.ingest()` — mas ainda **não há
  ferramenta de ingestão** pronta (ver [../tools.md](../tools.md)). Por isso a L4
  está vazia hoje; não é falha, é o próximo passo do substrate.

## Sensível
- Segredos **nunca** entram no repositório. O `.env` fica local (já está no
  `.gitignore`). Ver [../rules/never.md](../rules/never.md).
