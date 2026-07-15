# Substrate — Compêndio (compendium.md)

> **Camada 2, a "cozinha limpa":** o conhecimento **destilado** que o CRIS OS
> realmente usa. Espelha o que [`memory/seed.py`](../memory/seed.py) semeia no
> runtime — **se editar aqui, atualize lá** (e vice-versa). Mantê-los sincronizados
> é a tarefa contínua do substrate.

## Quem é a Cris
Empreendedora multitarefa, toca vários projetos em paralelo. Comunicação humana,
direta, carinhosa e organizada. Cuida da saúde no dia a dia (caminhada, água,
descanso). Quer foco, prioridade e o próximo passo claro.

## Estilo de trabalho (preferências)
- Português do Brasil, direto, sem robotês.
- Resumir → priorizar → sugerir a próxima ação.
- Separar pessoal de negócio.

## Projetos principais (9)
| Projeto | Em uma linha | Agente dono |
|---|---|---|
| Zavix.online | loja online: produtos, estoque, links, categorias, pedidos | `zavix` |
| Produtos 3D | criação e venda de impressos 3D | secretária / geral |
| VitrinePro | solução para negócios locais | `vitrinepro` |
| ScalaFlow | mineração de produtos vencedores, anúncios, nichos, funis | `scalaflow` |
| PinkLogic | SaaS: sistemas, automações, IA | `pinklogic` |
| Criação de Sites | serviço de criação de sites | secretária / geral |
| Marketing Digital | divulgação, tráfego, conteúdo | `social-media` |
| mkVideos | roteiro, voz, vídeo, legenda, thumbnail | `mkvideos` |
| Currículo Gratuito | ferramenta/produto de currículo | `curriculo` |

## A equipe (agentes) e seus domínios
- **Orquestrador** (gerente): único que fala com a Cris; identifica intenção, delega, entrega uma resposta.
- **secretary** (Secretária IA — **Fase 1**): agenda, rotina, prioridades, lembretes, saúde, produtividade.
- **Transversais** (veem todos os projetos): `atendimento`, `pesquisador`, `social-media`, `financeiro`.
- **Por projeto** (cada um só no seu domínio): `zavix`, `vitrinepro`, `scalaflow`, `pinklogic`, `curriculo`, `mkvideos`.

## Como o CRIS OS responde (resumo)
Cris fala (Telegram) → Orquestrador identifica a intenção → delega ao(s)
agente(s) certo(s) → cada agente recebe a memória **escopada** ao seu domínio +
permanente + base de conhecimento relevante → o Orquestrador compõe **uma**
resposta. Detalhes técnicos: [../ARQUITETURA.md](../ARQUITETURA.md).
