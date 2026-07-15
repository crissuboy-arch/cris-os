"""
MemoryFacade — monta o AgentContext ESCOPADO para cada agente.

Este é o ponto onde a filosofia "nenhum agente conhece tudo" vira realidade de
arquitetura: cada agente recebe apenas
  - sua memória de projeto (L2) conforme o ESCOPO declarado no manifest;
  - a memória permanente (L3) sobre a Cris;
  - os trechos relevantes da base de conhecimento (L4) para a mensagem atual;
  - os itens do dia (L1 temporária) e o histórico do diálogo (L1 conversa).

Escopo de projeto do agente:
  - lista de projetos  -> só esses;
  - ["*"]              -> todos os projetos (agentes transversais, ex.: financeiro);
  - []                 -> nenhum projeto (ex.: secretária) — usa só L1/L3/L4.
"""

from __future__ import annotations

from core.contracts.agent import AgentContext


class MemoryFacade:
    def __init__(self, conversation, temporary, project, permanent, knowledge_base) -> None:
        self.conversation = conversation
        self.temporary = temporary
        self.project = project
        self.permanent = permanent
        self.knowledge_base = knowledge_base

    def build_context(self, scope: list[str], session: str, query: str) -> AgentContext:
        """Monta o contexto de memória respeitando o escopo de projetos do agente."""
        if scope == ["*"]:
            project_items = self.project.recall_many(self.project.all_projects())
        elif scope:
            project_items = self.project.recall_many(scope)
        else:
            project_items = []

        return AgentContext(
            session=session,
            conversation=self.conversation.recent(session),
            temporary=self.temporary.today(session),
            project_memory=project_items,
            permanent=self.permanent.recall(),
            knowledge=self.knowledge_base.search(query),
        )
