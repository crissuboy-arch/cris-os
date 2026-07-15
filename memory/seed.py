"""
Semente das memórias permanente (L3) e de projetos (L2).

Na primeira execução, popula:
  - L3 (permanente): quem é a Cris, objetivos e forma de trabalhar;
  - L2 (projetos): uma entrada-base para cada projeto principal.

Idempotente: só semeia se a memória permanente estiver vazia.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# L3 — Permanente: (type, title, content)
PERMANENTE = [
    ("identity", "Quem é a Cris",
     "Empreendedora multitarefa, toca vários projetos em paralelo. Comunicação "
     "humana, direta, carinhosa e organizada. Cuida da saúde no dia a dia "
     "(caminhada, água, descanso)."),
    ("preference", "Estilo de resposta",
     "Português do Brasil, direto ao ponto, sem 'robotês'. Resumir o que entendeu, "
     "priorizar e sugerir a próxima ação. Nunca inventar dados."),
    ("objective", "Visão CRIS OS",
     "Construir um sistema operacional pessoal de agentes que automatize a vida "
     "pessoal e profissional da Cris e cresça por anos."),
]

# L2 — Projetos: (project, descrição-base)
PROJETOS = [
    ("Zavix.online", "Loja online: produtos, estoque, links, categorias, pedidos, pagamentos."),
    ("Produtos 3D", "Criação e venda de produtos impressos em 3D."),
    ("VitrinePro", "Solução para negócios locais: presença digital e vendas."),
    ("ScalaFlow", "Mineração de produtos vencedores, anúncios, nichos, concorrentes, funis."),
    ("PinkLogic", "SaaS: sistemas, automações e IA."),
    ("Criação de Sites", "Serviço de criação de sites."),
    ("Marketing Digital", "Divulgação, tráfego e conteúdo."),
    ("mkVideos", "Produção de vídeos: roteiro, voz, vídeo, legenda, thumbnail."),
    ("Currículo Gratuito", "Ferramenta/produto de currículo gratuito."),
]


def seed_if_empty(permanent, project) -> None:
    """Semeia L3 e L2 se a memória permanente ainda estiver vazia."""
    if not permanent.is_empty():
        return

    logger.info("Memoria vazia: semeando permanente (L3) e projetos (L2).")
    for type_, title, content in PERMANENTE:
        permanent.remember(type_, title, content, tags=["seed"])
    for nome, descricao in PROJETOS:
        project.remember(nome, "project", nome, descricao, tags=["seed"])
