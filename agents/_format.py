"""
Formatação para prompt — camada de agentes.

Renderiza itens de memória (`KnowledgeItem`) em texto para o system prompt do
agente. Vive aqui (e não em `memory/`) para o agente NÃO depender da camada de
memória: o agente recebe os itens já recuperados (no `AgentContext`) e só os formata.
"""

from __future__ import annotations

from core.models import KnowledgeItem


def render_itens(itens: list[KnowledgeItem]) -> str:
    """Renderiza itens de memória como um bloco de texto para o prompt."""
    if not itens:
        return ""
    linhas = []
    for it in itens:
        tags = f" [{', '.join(it.tags)}]" if it.tags else ""
        linhas.append(f"- ({it.type}) {it.title}{tags}: {it.content}")
    return "\n".join(linhas)
