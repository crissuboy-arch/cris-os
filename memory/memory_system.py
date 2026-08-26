"""
MemorySystem — servico central de memoria do CRIS OS.

Fornece operacoes de alto nivel:
  - lembrar (criar memoria com parsing de linguagem natural)
  - esquecer (excluir com confirmacao)
  - pesquisar (busca textual + filtros)
  - atualizar
  - fundir duplicadas
  - estatisticas
  - backup/restore

Toda operacao respeita isolamento por user_id e workspace.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from core.models import MemoryItem
from storage.sqlite_memory_store import SQLiteMemoryStore

logger = logging.getLogger(__name__)

# Palavras que indicam saudacao — nao salvar
_SAUDACOES = {"ola", "oi", "hey", "bom dia", "boa tarde", "boa noite", "tudo bem",
              "como vai", "td bem", "opa", "e ai", "fala"}

# Padroes para extrair informacoes de linguagem natural
_RE_LEMBRE = re.compile(
    r"(?:lembre|guarde|salve|anote|memorize|grave|nao esqueca)"
    r"(?:[-se\s]+(?:que|de|o|a|do|da|dos|das))?"
    r"\s*(?:que\s+)?"
    r"(?:o\s+)?(?:preco\s+(?:do|da|de)\s+)?"
    r"(?:que\s+)?"
    r"(.+)",
    re.IGNORECASE,
)

_RE_LEMBRE_PROJETO = re.compile(
    r"(?:lembre|guarde|salve|anote)"
    r"(?:[-se\s]+(?:que|de|o|a|do|da|dos|das))?"
    r"\s*(?:que\s+)?"
    r"(.+?)"
    r"\s+pertence\s+(?:ao|a)\s+(?:projeto\s+)?([^\s]+)",
    re.IGNORECASE,
)

_RE_ESQUECA = re.compile(
    r"(?:esqueca|apague|delete|remova|delete|remover)"
    r"(?:[-se\s]+(?:o|a|do|da|de))?"
    r"\s*(?:que\s+)?"
    r"(.+)",
    re.IGNORECASE,
)

_RE_QUE_VOCE_SABE = re.compile(
    r"(?:o\s+)?(?:que\s+)?voce\s+(?:sabe|lembra|sabia|conhece)"
    r"(?:\s+sobre)?\s*(.+)",
    re.IGNORECASE,
)

_RE_O_QUE_TEM = re.compile(
    r"(?:o\s+)?(?:que\s+)(?:tem|ha|existe|sabe)"
    r"(?:\s+sobre)?\s*(.+)",
    re.IGNORECASE,
)

_RE_PROJETO = re.compile(r"projeto\s+(\w+)", re.IGNORECASE)

_RE_CLIENTE = re.compile(
    r"(?:do|da|sobre)\s+(?:cliente\s+)?([^\s?,.]+)",
    re.IGNORECASE,
)


class MemorySystem:
    """Servico central de memoria com parsing NL e operacoes seguras."""

    def __init__(self, store: SQLiteMemoryStore) -> None:
        self.store = store

    # ------------------------------------------------------------------
    #  Deteccao de intencao
    # ------------------------------------------------------------------

    def detect_intent(self, text: str) -> str:
        """Detecta a intencao da mensagem: remember, forget, query, greeting, other."""
        t = text.strip().lower()
        if any(t.startswith(s) or t == s for s in _SAUDACOES):
            return "greeting"
        if _RE_LEMBRE_PROJETO.match(t):
            return "remember_project"
        if _RE_LEMBRE.match(t):
            return "remember"
        if _RE_ESQUECA.match(t):
            return "forget"
        if _RE_QUE_VOCE_SABE.match(t) or _RE_O_QUE_TEM.match(t):
            return "query"
        return "other"

    # ------------------------------------------------------------------
    #  Lembrar
    # ------------------------------------------------------------------

    def _extrair_preco(self, text: str) -> bool:
        """Detecta mencao a preco/valor no texto."""
        import re
        padroes = [
            r"(?:€|eur|euros?|r\$\s*|us\$\s*|\$\s*|euros?)\s*([\d,.]+)",
            r"([\d,.]+)\s*(?:€|eur|euros?|r\$|us\$|\$|euros?)",
            r"(?:pre[cç]o|valor|custa|custou|vai\s+custar|paguei|cobrei|cobra)\s*(?:de\s+)?(?:R?\$?\s*)?([\d,.]+)",
            r"(?:de|por)\s*(?:R?\$?\s*)?([\d,.]+)\s*(?:reais?|eur|euros?|d[óo]lares?)",
        ]
        for pat in padroes:
            if re.search(pat, text, re.IGNORECASE):
                return True
        return False

    def _extrair_projeto(self, text: str) -> str:
        """Extrai nome de projeto do texto."""
        import re
        padroes = [
            r"(?:do|no|sobre\s+o)\s+(?:projeto\s+)?([a-zA-Z][a-zA-Z0-9_.]+)",
            r"(?:pertence\s+(?:ao|a)\s+(?:projeto\s+)?([a-zA-Z][a-zA-Z0-9_.]+))",
        ]
        for pat in padroes:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return ""

    def remember(self, text: str, user_id: str, workspace: str = "default",
                 origin: str = "telegram", agent: str = "") -> MemoryItem:
        """Cria um item de memoria a partir de texto em linguagem natural."""
        t = text.strip()
        project = ""
        client = ""
        importance = 3

        match_proj = _RE_LEMBRE_PROJETO.match(t.lower())
        if match_proj:
            content = match_proj.group(1).strip()
            project = match_proj.group(2).strip()
        else:
            match = _RE_LEMBRE.match(t.lower())
            if match:
                content = match.group(1).strip()
            else:
                content = t

        # Detectar projeto inline mesmo sem "pertence a"
        if not project:
            project = self._extrair_projeto(content)

        # Extrair preco/valor numerico para definir importancia e tipo
        if self._extrair_preco(content):
            importance = 5
            type_ = "fact"
        elif project:
            importance = 4
            type_ = "project_info"
        else:
            type_ = "note"

        match_cli = _RE_CLIENTE.match(content.lower())
        if match_cli and not client:
            client = match_cli.group(1)

        now = datetime.now(timezone.utc).isoformat()
        item = MemoryItem(
            id="",
            user_id=user_id,
            workspace=workspace,
            client=client,
            importance=importance,
            origin=origin,
            date=now[:10],
            agent=agent,
            type=type_,
            title=content[:80],
            content=content,
            tags=[type_, "auto"],
            project=project,
        )
        return self.store.create(item)

    def remember_raw(self, item: MemoryItem) -> MemoryItem:
        """Salva um MemoryItem ja montado."""
        return self.store.create(item)

    # ------------------------------------------------------------------
    #  Esquecer
    # ------------------------------------------------------------------

    def forget(self, text: str, user_id: str) -> list[MemoryItem]:
        """Busca itens para esquecer. Retorna candidatos (confirmacao necessaria)."""
        t = text.strip().lower()
        match = _RE_ESQUECA.match(t)
        if match:
            query = match.group(1).strip()
        else:
            query = t

        # Remove palavras de comando do query
        for prefix in ["que", "o", "a", "do", "da", "de", "dos", "das"]:
            if query.startswith(prefix + " ") and len(query) > len(prefix) + 1:
                query = query[len(prefix) + 1:]

        candidates = self.store.search(
            query=query, user_id=user_id, limit=10,
        )

        # Sempre tenta palavras-chave individuais para achar matches adicionais
        palavras = [w for w in query.split() if len(w) >= 3]
        palavras.sort(key=len, reverse=True)
        for palavra in palavras:
            alt = self.store.search(
                query=palavra, user_id=user_id, limit=10,
            )
            if alt:
                existing_ids = {c.id for c in candidates}
                for a in alt:
                    if a.id not in existing_ids:
                        candidates.append(a)
                        existing_ids.add(a.id)

        # Se ainda nao achou, busca tudo e filtra por conteudo
        if not candidates:
            candidates = self.store.search(
                query="", user_id=user_id, limit=50,
            )
            candidates = [
                c for c in candidates
                if query in c.content.lower() or query in c.title.lower()
            ][:10]

        return candidates

    def confirm_forget(self, item_id: str, user_id: str) -> bool:
        """Confirma e executa a exclusao."""
        found = self.store.get(item_id, user_id)
        if found is None:
            logger.warning("Tentativa de esquecer item inexistente: id=%s user=%s", item_id, user_id)
            return False
        return self.store.delete(item_id, user_id)

    # ------------------------------------------------------------------
    #  Pesquisar
    # ------------------------------------------------------------------

    def query(self, text: str, user_id: str, workspace: str = "",
              project: str = "", client: str = "", limit: int = 20) -> list[MemoryItem]:
        """Pesquisa memoria por texto natural."""
        t = text.strip().lower()

        # Extrair projeto do texto
        proj_match = _RE_PROJETO.search(t)
        if proj_match and not project:
            project = proj_match.group(1)

        match_q = _RE_QUE_VOCE_SABE.match(t) or _RE_O_QUE_TEM.match(t)
        search_query = match_q.group(1).strip() if match_q else t

        # Limpar query de palavras comuns
        for prefix in ["sobre", "do", "da", "de", "o", "a", "no", "na", "que"]:
            if search_query.startswith(prefix + " ") and len(search_query) > len(prefix) + 1:
                search_query = search_query[len(prefix) + 1:]

        results = self.store.search(
            query=search_query, user_id=user_id, workspace=workspace,
            project=project, client=client, limit=limit,
        )

        if not results:
            # Tenta com palavras-chave individuais (exclui stopwords)
            palavras = [w for w in search_query.split() if len(w) >= 3]
            palavras.sort(key=len, reverse=True)
            for palavra in palavras:
                alt_results = self.store.search(
                    query=palavra, user_id=user_id, workspace=workspace,
                    project=project, client=client, limit=limit,
                )
                if alt_results:
                    # Merge resultados
                    existing_ids = {r.id for r in results}
                    for a in alt_results:
                        if a.id not in existing_ids:
                            results.append(a)
                            existing_ids.add(a.id)

        if not results:
            # Fallback: lista tudo do usuario
            results = self.store.search(
                query="", user_id=user_id, workspace=workspace,
                project=project, client=client, limit=limit,
            )

        return results

    def search(self, query: str, user_id: str = "", workspace: str = "",
               project: str = "", client: str = "", tag: str = "",
               type_filter: str = "", limit: int = 20) -> list[MemoryItem]:
        """Busca estruturada com filtros."""
        return self.store.search(
            query=query, user_id=user_id, workspace=workspace,
            project=project, client=client, tag=tag,
            type_filter=type_filter, limit=limit,
        )

    # ------------------------------------------------------------------
    #  Atualizar
    # ------------------------------------------------------------------

    def update(self, item_id: str, user_id: str, **fields) -> MemoryItem | None:
        return self.store.update(item_id, user_id, **fields)

    # ------------------------------------------------------------------
    #  Utilitarios
    # ------------------------------------------------------------------

    def merge_duplicates(self, user_id: str) -> int:
        return self.store.merge_duplicates(user_id)

    def stats(self, user_id: str = "") -> dict:
        return self.store.stats(user_id)

    def list_by_user(self, user_id: str, workspace: str = "",
                     limit: int = 50) -> list[MemoryItem]:
        return self.store.list_by_user(user_id, workspace, limit)

    def list_by_project(self, project: str, user_id: str = "",
                        limit: int = 50) -> list[MemoryItem]:
        return self.store.list_by_project(project, user_id, limit)

    def count(self, user_id: str = "", workspace: str = "") -> int:
        return self.store.count(user_id, workspace)

    def should_save(self, text: str) -> bool:
        """Verifica se o texto deve ser salvo (filtra saudacoes e comandos)."""
        t = text.strip().lower()
        if any(t.startswith(s) or t == s for s in _SAUDACOES):
            return False
        if t.startswith("/"):
            return False
        if len(t) < 3:
            return False
        return True
