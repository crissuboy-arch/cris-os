"""
Tool — uma ferramenta executavel por um agente especialista.

Cada Tool tem:
  - name: identificador unico (ex.: "criar_legenda")
  - description: descricao para o usuario
  - keywords: palavras que disparam esta ferramenta
  - fn: funcao que executa a ferramenta (recebe string, retorna string)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    keywords: list[str]
    fn: Callable[[str], str]

    def execute(self, input_text: str) -> str:
        logger.info(
            "=== [TOOL '%s'] Executando com entrada: '%s' ===",
            self.name, input_text[:120],
        )
        return self.fn(input_text)

    def matches(self, text: str) -> bool:
        palavras = set(text.lower().split())
        for kw in self.keywords:
            if kw in palavras:
                return True
        texto_lower = text.lower()
        for kw in self.keywords:
            if kw in texto_lower:
                return True
        return False
