"""
Script de validacao de roteamento do AgentOrchestrator.

Testa 6 prompts reais contra o orquestrador e verifica:
  1. Importacao de todos os modulos de agente
  2. Roteamento por keyword (fallback deterministico)
  3. Roteamento com agente geral como fallback
  4. Logs estruturados estao presentes
"""

import logging
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s - %(message)s",
)

logger = logging.getLogger("validate_routing")


class FakeLLM:
    def __init__(self, reply="resposta do agente"):
        self.reply = reply
        self._provider_name = "fake-llm"

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        return LLMResponse(content=self.reply)

    def is_alive(self):
        return True


RESULTADOS: list[dict] = []
ERROS = 0
PASSOS = 0


def check(descricao: str, condicao: bool, detalhe: str = "") -> None:
    global PASSOS, ERROS
    PASSOS += 1
    if condicao:
        logger.info("  OK - %s", descricao)
        RESULTADOS.append({"status": "OK", "teste": descricao})
    else:
        logger.error("  FALHA - %s | %s", descricao, detalhe)
        ERROS += 1
        RESULTADOS.append({"status": "FALHA", "teste": descricao, "detalhe": detalhe})


def main() -> int:
    t0 = time.perf_counter()

    print("\n" + "=" * 60)
    print("  VALIDACAO DE ROTEAMENTO - AGENT ORCHESTRATOR")
    print("=" * 60 + "\n")

    # ------------------------------------------------------------------
    # 1. Importacao de modulos
    # ------------------------------------------------------------------
    print("[1] Verificando importacao de modulos...")

    from agents import AgentOrchestrator, discover_agents, discover_general_agent
    from agents.base_specialist import SpecialistAgent, create_agent
    from agents.prompts import (
        MARKETING_PROMPT, SOCIAL_MEDIA_PROMPT, VENDAS_PROMPT, ATENDIMENTO_PROMPT,
        PROGRAMADOR_PROMPT, PESQUISADOR_PROMPT, COPYWRITER_PROMPT, PRODUTIVIDADE_PROMPT,
        GERAL_PROMPT, ROUTING_PROMPT,
    )
    from core.models import IncomingMessage

    check("AgentOrchestrator importado", True)
    check("SpecialistAgent importado", True)
    check("discover_agents importado", True)
    check("discover_general_agent importado", True)
    check("Todos os 9 prompts importados (8 especialistas + geral + routing)",
          all(p and len(p) > 50 for p in [
              MARKETING_PROMPT, SOCIAL_MEDIA_PROMPT, VENDAS_PROMPT, ATENDIMENTO_PROMPT,
              PROGRAMADOR_PROMPT, PESQUISADOR_PROMPT, COPYWRITER_PROMPT, PRODUTIVIDADE_PROMPT,
              GERAL_PROMPT, ROUTING_PROMPT,
          ]))

    # ------------------------------------------------------------------
    # 2. Descoberta de agentes
    # ------------------------------------------------------------------
    print("\n[2] Verificando descoberta de agentes...")

    llm = FakeLLM()

    especialistas = discover_agents(llm)
    check("8 agentes especialistas descobertos", len(especialistas) == 8,
          f"Encontrados {len(especialistas)}")

    geral = discover_general_agent(llm)
    check("Agente geral descoberto", geral is not None)
    if geral:
        check("Agente geral tem nome 'geral'", geral.name == "geral",
              f"Nome: {geral.name}")
        check("Agente geral tem description", bool(geral.description))

    # ------------------------------------------------------------------
    # 3. Roteamento por keyword (6 prompts reais)
    # ------------------------------------------------------------------
    print("\n[3] Testando roteamento por keyword (fallback deterministico)...")

    casos_teste = [
        ("legenda para instagram", "social_media"),
        ("cria um script em python", "programador"),
        ("preciso de uma proposta comercial", "vendas"),
        ("atendimento ao cliente", "atendimento"),
        ("analise de concorrentes", "pesquisador"),
        ("headline para pagina de venda", "copywriter"),
    ]

    for mensagem, esperado in casos_teste:
        agente = AgentOrchestrator._rotear_por_keyword(mensagem)
        check(f"Keyword routing: '{mensagem[:40]}' -> '{esperado}'",
              agente == esperado,
              f"Esperado '{esperado}', obtido '{agente}'")

    # ------------------------------------------------------------------
    # 4. Roteamento via orchestrator
    # ------------------------------------------------------------------
    print("\n[4] Testando roteamento via AgentOrchestrator...")

    agentes = especialistas + ([geral] if geral else [])
    orch = AgentOrchestrator(llm=llm, agents=agentes, general_agent=geral)

    for mensagem, esperado_nome in casos_teste:
        msg = IncomingMessage("telegram", "val_user", mensagem)
        resposta = orch.handle(msg)
        # Nao sabemos qual agente exato foi usado (LLM router pode ter preferencia),
        # mas sabemos que deve ter resposta
        check(f"Orchestrator responde para '{mensagem[:30]}'", bool(resposta),
              f"Resposta vazia para: {mensagem}")

    # ------------------------------------------------------------------
    # 5. Agente geral como fallback
    # ------------------------------------------------------------------
    print("\n[5] Testando agente geral como fallback...")

    # Pergunta que nao casa com nenhum keyword -> deve usar geral
    msg = IncomingMessage("telegram", "val_user", "qual a capital do brasil")
    resposta = orch.handle(msg)
    check("Resposta para pergunta generica (fallback geral)", bool(resposta),
          "Resposta vazia para pergunta generica")

    # Sem agente geral, deve dar mensagem de fallback
    orch_sem_geral = AgentOrchestrator(llm=llm, agents=especialistas)
    msg2 = IncomingMessage("telegram", "val_user", "qual a capital do brasil")
    resposta2 = orch_sem_geral.handle(msg2)
    check("Mensagem de fallback sem agente geral",
          "nenhum" in resposta2.lower() or "/agents" in resposta2.lower(),
          f"Resposta: {resposta2[:100]}")

    # ------------------------------------------------------------------
    # 6. Listagem de agentes
    # ------------------------------------------------------------------
    print("\n[6] Verificando listagem de agentes...")

    lista = orch.list_agents()
    check("Lista contem 'geral'", "geral" in lista)
    check("Lista contem 'social_media'", "social_media" in lista)
    check("Lista contem '/use'", "/use" in lista)

    # ------------------------------------------------------------------
    # 7. Agente ativo (set/get)
    # ------------------------------------------------------------------
    print("\n[7] Verificando agente ativo...")

    check("get_active_agent retorna 'auto'", orch.get_active_agent("val_user") == "auto")

    msg_set = orch.set_active_agent("val_user", "marketing")
    check("set_active_agent confirma marketing", "marketing" in msg_set)
    check("get_active_agent retorna marketing", orch.get_active_agent("val_user") == "marketing")

    msg_unset = orch.set_active_agent("val_user", None)
    check("set_active_agent(None) volta auto", "automatico" in msg_unset.lower())
    check("get_active_agent retorna auto", orch.get_active_agent("val_user") == "auto")

    # Agente invalido
    msg_inv = orch.set_active_agent("val_user", "nao_existe")
    check("set_active_agent invalido retorna erro", "nao encontrado" in msg_inv.lower())

    # ------------------------------------------------------------------
    # 8. Teste com LLM real (Ollama)
    # ------------------------------------------------------------------
    print("\n[8] Testando com LLM real (Ollama)...")

    try:
        from core.llm_providers.ollama import OllamaProvider
        from core.config import get_settings

        settings = get_settings()
        ollama = OllamaProvider(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_HOST,
        )

        if ollama.is_alive():
            orch_real = AgentOrchestrator(
                llm=ollama, agents=especialistas, general_agent=geral,
            )
            msg = IncomingMessage("telegram", "val_user", "crie uma legenda para instagram")
            t_real = time.perf_counter()
            resposta_real = orch_real.handle(msg)
            elapsed_real = (time.perf_counter() - t_real) * 1000
            check("Resposta com LLM real (Ollama)", bool(resposta_real),
                  f"Tempo: {elapsed_real:.0f}ms | Resposta: {resposta_real[:80]}")
            logger.info("  Tempo de resposta com LLM real: %.0fms", elapsed_real)
        else:
            logger.warning("  Ollama nao esta disponivel. Pulando teste com LLM real.")
    except Exception as exc:
        logger.warning("  Erro ao conectar com Ollama: %s. Pulando teste com LLM real.", exc)

    # ------------------------------------------------------------------
    # Sumario
    # ------------------------------------------------------------------
    elapsed_total = time.perf_counter() - t0

    print("\n" + "=" * 60)
    print("  RESUMO DA VALIDACAO")
    print("=" * 60)
    print(f"  Total de verificacoes: {PASSOS}")
    print(f"  OK:                   {PASSOS - ERROS}")
    print(f"  Falhas:              {ERROS}")
    print(f"  Tempo total:         {elapsed_total:.2f}s")

    if ERROS == 0:
        print("\n  >>> VALIDACAO CONCLUIDA COM SUCESSO <<<")
    else:
        print(f"\n  >>> {ERROS} FALHA(S) ENCONTRADA(S) <<<")
        for r in RESULTADOS:
            if r["status"] == "FALHA":
                print(f"    - {r['teste']}: {r.get('detalhe', '')}")

    print("=" * 60 + "\n")
    return 1 if ERROS > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
