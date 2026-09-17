"""
Tool — uma ferramenta executavel por um agente especialista.

Cada Tool tem:
  - name: identificador unico (ex.: "criar_legenda")
  - description: descricao para o usuario
  - keywords: palavras que disparam esta ferramenta
  - fn: funcao que executa a ferramenta (recebe string, retorna string)
  - matcher: (opcional) predicado extra p/ padroes que palavra-chave nao
    cobre (ex.: reconhecer um ID/URL da Meta Ads Library em qualquer texto,
    sem precisar enumerar palavras). Fase 3 -- ver tools/opportunity_tools.py.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    keywords: list[str]
    fn: Callable[..., str]
    matcher: Callable[[str], bool] | None = None

    def execute(self, input_text: str, session: str = "") -> str:
        """`session` (Fase 3): identifica canal+usuario (ex.:
        "telegram:123"). So e repassado a `fn` quando a propria funcao
        aceita um segundo parametro (introspeccao via `inspect.signature`) --
        as dezenas de Tools existentes (coding_tools.py, copy_tools.py,
        sales_tools.py, etc.) continuam recebendo so `input_text`, sem
        precisar mudar. So as poucas Tools que realmente precisam de
        contexto por usuario/canal (ex.: opportunity_analyst,
        product_architect -- "oportunidade em foco") declaram o segundo
        parametro e passam a recebe-lo."""
        logger.info(
            "=== [TOOL '%s'] Executando com entrada: '%s' ===",
            self.name, input_text[:120],
        )
        if self._aceita_session():
            return self.fn(input_text, session)
        return self.fn(input_text)

    def _aceita_session(self) -> bool:
        try:
            parametros = inspect.signature(self.fn).parameters
        except (TypeError, ValueError):
            return False
        return len(parametros) >= 2

    def matches(self, text: str) -> bool:
        if self.matcher is not None and self.matcher(text):
            return True
        palavras = set(text.lower().split())
        for kw in self.keywords:
            if kw in palavras:
                return True
        texto_lower = text.lower()
        for kw in self.keywords:
            if kw in texto_lower:
                return True
        return False
