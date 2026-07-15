"""
ResponseComposer — entrega UMA resposta final para a Cris.

Responsabilidade única: pegar o(s) resultado(s) dos agentes e produzir uma única
resposta. Um agente -> repassa direto (ele já escreveu bem). Vários -> sintetiza
em uma resposta calorosa e organizada, sem citar nomes internos.
"""

from __future__ import annotations

import logging
import time

from core.models import ExecutionResult

logger = logging.getLogger(__name__)

_COMPOSE_PROMPT = (
    "Você é o Cris OS, o gerente que fala com a Cris. Vários especialistas "
    "responderam partes de um pedido. Junte tudo em UMA resposta única, calorosa, "
    "direta e organizada, em português do Brasil. Não cite os nomes internos dos "
    "agentes; fale como se fosse você entregando o resultado."
)


class ResponseComposer:
    def __init__(self, llm) -> None:
        self.llm = llm

    def compose(self, question: str, results: list) -> str:
        if not results:
            logger.warning("=== [COMPOSER] Nenhum resultado para compor ===")
            return "Desculpa, Cris, não consegui processar isso agora. Pode repetir?"

        results = [ExecutionResult.of(r) for r in results]
        logger.info("=== [COMPOSER] Compondo %d resultado(s): sources=%s ===",
                    len(results), [r.source for r in results])

        if len(results) == 1:
            saida = results[0].output
            logger.info("=== [COMPOSER] Resultado unico (%d chars) ===", len(saida))
            return saida

        juntos = "\n\n".join(f"[{r.source}]\n{r.output}" for r in results)
        mensagens = [
            {"role": "system", "content": _COMPOSE_PROMPT},
            {"role": "user", "content": f"Pedido da Cris: {question}\n\nRespostas:\n{juntos}"},
        ]
        logger.info("=== [COMPOSER] Sintetizando %d respostas via provider ===", len(results))
        try:
            t0 = time.perf_counter()
            sintese = self.llm.chat(mensagens).content.strip()
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info("=== [COMPOSER] Sintese em %.0fms (%d chars)", elapsed_ms, len(sintese))
            return sintese or juntos
        except Exception:  # noqa: BLE001 - se a síntese falhar, devolve o cru
            logger.warning("=== [COMPOSER] Falha ao sintetizar, devolvendo respostas cruas ===")
            return juntos
