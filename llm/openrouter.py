"""
OpenRouterProvider — provedor de IA remota via OpenRouter (Fase 2.5).

Isolado/reutilizavel: implementa a mesma porta `LLMProvider` (is_alive/chat)
que Ollama/NVIDIA/OpenAICompatProvider ja implementam, entao pode ser
injetado em qualquer lugar que espere um provedor de LLM, sem o resto do
CRIS OS saber que e o OpenRouter por baixo.

Principio (pedido explicito da Cris): OpenRouter e usado SOMENTE quando uma
tarefa precisa de raciocinio/analise/geracao. Consultas deterministicas
(scalaflow_intel, filtros do Supabase) NUNCA passam por aqui -- isso e
garantido em `agents/orchestrator.py` (interceptacao por palavra-chave
acontece ANTES de qualquer chamada de LLM) e permanece inalterado nesta fase.

Modelos por camada de custo (verificados no catalogo publico e real do
OpenRouter, https://openrouter.ai/api/v1/models, em 2026-09-17 -- NAO fixados
de memoria):

  ECONOMICO   openai/gpt-4o-mini                  ~$0.15 / $0.60 por 1M tokens
  INTELIGENTE openai/gpt-5-mini                   ~$0.25 / $2.00 por 1M tokens
  PREMIUM     anthropic/claude-opus-4.5           ~$5.00 / $25.00 por 1M tokens

Todos configuraveis via .env (OPENROUTER_MODEL_ECONOMICO/INTELIGENTE/PREMIUM)
sem precisar mexer no codigo.
"""

from __future__ import annotations

import logging
import time

try:
    # Mesma correcao de TLS usada em tools/scalaflow_tools.py e
    # tools/opportunity_tools.py: nesta maquina o Avast (Web/Mail Shield)
    # intercepta HTTPS com uma CA propria que o certifi (bundle publico) nao
    # confia. truststore faz o ssl/urllib3 confiarem no CA store do sistema
    # operacional (o mesmo que o curl/Windows ja usam) -- NAO desativa
    # verificacao de certificado. Precisa estar aqui tambem (nao so nos
    # tools/scalaflow_*) porque core/runtime.py pode chamar este modulo
    # ANTES de importar tools/scalaflow_tools.py (ordem de inicializacao).
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

import requests

from core.contracts.llm import LLMResponse, ToolCall

logger = logging.getLogger(__name__)

# Modelos-padrao por camada -- usados so se a variavel de ambiente
# correspondente estiver vazia. Ver docstring do modulo sobre como foram
# escolhidos (catalogo real, nao fixados de memoria).
MODELO_PADRAO_ECONOMICO = "openai/gpt-4o-mini"
MODELO_PADRAO_INTELIGENTE = "openai/gpt-5-mini"
MODELO_PADRAO_PREMIUM = "anthropic/claude-opus-4.5"

TIER_DETERMINISTICO = "deterministico"  # nao usa este provider -- documentado por completude
TIER_ECONOMICO = "economico"
TIER_INTELIGENTE = "inteligente"
TIER_PREMIUM = "premium"


class OpenRouterError(Exception):
    """Erro ao falar com o OpenRouter -- sempre com uma causa classificada."""

    def __init__(self, mensagem: str, categoria: str) -> None:
        super().__init__(mensagem)
        self.categoria = categoria  # "timeout" | "indisponivel" | "rate_limit" | "saldo_insuficiente" | "erro_api" | "conexao"


class OpenRouterProvider:
    """
    Provedor LLM para o OpenRouter (API compativel com OpenAI:
    POST {base_url}/chat/completions).

    Uma instancia = um modelo (uma camada de custo). Para usar varias
    camadas, crie uma instancia por camada (ver `criar_providers_por_tier`).
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = 60,
        tier: str = TIER_ECONOMICO,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.tier = tier
        self._provider_name = f"openrouter:{tier}"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # Recomendado pelo OpenRouter para identificar a app nos logs
            # deles (nao e um segredo, so metadado do lado do cliente).
            "HTTP-Referer": "https://github.com/crissuboy-arch/cris-os",
            "X-Title": "CRIS OS",
        }

    def is_alive(self) -> bool:
        """True se a API responde (checagem barata: HEAD/GET em /models)."""
        try:
            r = requests.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=10,
            )
            return r.status_code == 200
        except requests.RequestException:
            return False

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        """Envia mensagens ao modelo e devolve a resposta. Nunca deixa uma
        excecao "crua" escapar: sempre `OpenRouterError` com `categoria`
        classificada, para quem chama decidir o que fazer (nunca derruba o
        processo -- ver `agents/orchestrator.py`/`base_specialist.py`, que
        ja capturam Exception ao redor de qualquer chamada de LLM)."""
        payload: dict = {"model": self.model, "messages": messages}
        if tools:
            payload["tools"] = tools

        t0 = time.perf_counter()
        tipo_tarefa = "chat"
        try:
            r = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            self._registrar_uso(tipo_tarefa, t0, sucesso=False, erro="timeout")
            raise OpenRouterError(
                f"OpenRouter ({self.model}) nao respondeu em {self.timeout}s.", "timeout",
            ) from exc
        except requests.ConnectionError as exc:
            self._registrar_uso(tipo_tarefa, t0, sucesso=False, erro="conexao")
            raise OpenRouterError(
                "Nao consegui conectar ao OpenRouter (rede/DNS).", "conexao",
            ) from exc

        if r.status_code == 429:
            self._registrar_uso(tipo_tarefa, t0, sucesso=False, erro="rate_limit")
            raise OpenRouterError(
                "OpenRouter recusou por rate limit (muitas requisicoes).", "rate_limit",
            )
        if r.status_code == 402:
            self._registrar_uso(tipo_tarefa, t0, sucesso=False, erro="saldo_insuficiente")
            raise OpenRouterError(
                "OpenRouter recusou por saldo/limite insuficiente na conta.", "saldo_insuficiente",
            )
        if r.status_code == 404:
            self._registrar_uso(tipo_tarefa, t0, sucesso=False, erro="modelo_indisponivel")
            raise OpenRouterError(
                f"Modelo '{self.model}' nao encontrado/indisponivel no OpenRouter.", "modelo_indisponivel",
            )
        if r.status_code >= 400:
            self._registrar_uso(tipo_tarefa, t0, sucesso=False, erro=f"http_{r.status_code}")
            raise OpenRouterError(
                f"OpenRouter respondeu com erro {r.status_code}.", "erro_api",
            )

        data = r.json()
        choice = (data.get("choices") or [{}])[0] or {}
        message = choice.get("message", {}) or {}
        content = (message.get("content") or "").strip()
        tool_calls = self._parse_tool_calls(message.get("tool_calls") or [])
        uso = data.get("usage") or {}

        self._registrar_uso(
            tipo_tarefa, t0, sucesso=True,
            tokens_entrada=uso.get("prompt_tokens"),
            tokens_saida=uso.get("completion_tokens"),
        )
        return LLMResponse(content=content, tool_calls=tool_calls)

    def _registrar_uso(
        self,
        tipo_tarefa: str,
        t0: float,
        sucesso: bool,
        erro: str | None = None,
        tokens_entrada: int | None = None,
        tokens_saida: int | None = None,
    ) -> None:
        """
        Log de uso SEGURO: modelo, camada, tipo de tarefa, tokens, duracao,
        sucesso/erro. NUNCA loga o prompt, a resposta nem a API key.
        """
        duracao_ms = (time.perf_counter() - t0) * 1000
        custo = self._estimar_custo(tokens_entrada, tokens_saida)
        logger.info(
            "=== [OPENROUTER] tier=%s modelo=%s tarefa=%s sucesso=%s "
            "tokens_in=%s tokens_out=%s custo_estimado_usd=%s duracao_ms=%.0f%s ===",
            self.tier, self.model, tipo_tarefa, sucesso,
            tokens_entrada, tokens_saida,
            f"{custo:.6f}" if custo is not None else "?",
            duracao_ms,
            f" erro={erro}" if erro else "",
        )

    def _estimar_custo(self, tokens_entrada: int | None, tokens_saida: int | None) -> float | None:
        """Estimativa best-effort (nao e a fatura oficial do OpenRouter)."""
        precos = _PRECOS_CONHECIDOS.get(self.model)
        if not precos or tokens_entrada is None or tokens_saida is None:
            return None
        preco_in, preco_out = precos
        return tokens_entrada * preco_in + tokens_saida * preco_out

    @staticmethod
    def _parse_tool_calls(brutos: list[dict]) -> list[ToolCall]:
        import json as _json

        chamadas: list[ToolCall] = []
        for c in brutos:
            fn = c.get("function", {}) or {}
            nome = fn.get("name")
            if not nome:
                continue
            args = fn.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = _json.loads(args or "{}")
                except _json.JSONDecodeError:
                    args = {}
            chamadas.append(ToolCall(name=nome, arguments=args or {}))
        return chamadas


# Precos por token (prompt, completion), em USD, dos modelos-padrao acima --
# usados so para a ESTIMATIVA de custo no log (best-effort). Conferidos no
# catalogo publico do OpenRouter em 2026-09-17; podem mudar sem aviso -- o
# log simplesmente omite o custo estimado (`?`) se o modelo nao estiver aqui.
_PRECOS_CONHECIDOS: dict[str, tuple[float, float]] = {
    "openai/gpt-4o-mini": (0.00000015, 0.0000006),
    "openai/gpt-5-mini": (0.00000025, 0.000002),
    "anthropic/claude-opus-4.5": (0.000005, 0.000025),
    "meta-llama/llama-3.1-8b-instruct": (0.00000005, 0.00000008),
}


def criar_provider(api_key: str, model: str, base_url: str, timeout: int, tier: str) -> OpenRouterProvider:
    return OpenRouterProvider(api_key=api_key, model=model, base_url=base_url, timeout=timeout, tier=tier)
