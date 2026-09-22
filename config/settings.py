"""
Configurações centrais do CRIS OS.

Tudo que é "ajustável" (tokens, modelo, caminhos) vive aqui.
Os valores são lidos do arquivo .env para não deixar segredos no código.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Pasta raiz do projeto (a pasta que contém este "config/").
BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega o arquivo .env (se existir) para dentro das variáveis de ambiente.
load_dotenv(BASE_DIR / ".env")


def _get_bool(name: str, default: bool = False) -> bool:
    """Lê uma variável de ambiente como booleano (1/true/yes)."""
    valor = os.getenv(name, str(default)).strip().lower()
    return valor in ("1", "true", "yes", "sim", "on")


def _get_int(name: str, default: int) -> int:
    """Lê uma variável de ambiente como inteiro, com valor padrão seguro."""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _get_int_or_none(name: str) -> int | None:
    """Inteiro opcional: vazio/ausente -> None (deixa a decisão para o Ollama)."""
    valor = os.getenv(name, "").strip()
    try:
        return int(valor) if valor != "" else None
    except ValueError:
        return None


class Settings:
    """Agrupa todas as configurações em um único objeto fácil de importar."""

    # --- Caminhos importantes ---
    BASE_DIR: Path = BASE_DIR
    AGENTS_DIR: Path = BASE_DIR / "agents"
    SKILLS_DIR: Path = BASE_DIR / "skills"
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = BASE_DIR / "data" / "cris_os.db"  # fonte única da verdade (SQLite)
    LOGS_DIR: Path = BASE_DIR / "logs"
    ORCHESTRATOR_PROMPT_FILE: Path = BASE_DIR / "agents" / "orchestrator" / "SYSTEM.md"

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_ALLOWED_USER_ID: str = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()

    # --- NVIDIA AI ---
    NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "").strip()
    NVIDIA_BASE_URL: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
    NVIDIA_MODEL: str = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct").strip()
    NVIDIA_ROUTER_MODEL: str = os.getenv("NVIDIA_ROUTER_MODEL", "meta/llama-3.1-8b-instruct").strip()
    NVIDIA_GENERATION_MODEL: str = os.getenv("NVIDIA_GENERATION_MODEL", "meta/llama-3.1-70b-instruct").strip()
    ROUTER_CONTEXT_MESSAGES: int = _get_int("ROUTER_CONTEXT_MESSAGES", 3)

    # --- Ollama ---
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1").strip()
    OLLAMA_TIMEOUT: int = _get_int("OLLAMA_TIMEOUT", 120)
    # Controle de GPU: vazio = automático; 0 = força CPU; N = N camadas na GPU.
    # Mesmo com automático, há fallback para CPU se ocorrer "CUDA out of memory".
    OLLAMA_NUM_GPU: int | None = _get_int_or_none("OLLAMA_NUM_GPU")

    # --- CRIS OS ---
    DEFAULT_AGENT: str = os.getenv("DEFAULT_AGENT", "auto").strip()
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    MEMORY_CONTEXT_MESSAGES: int = _get_int("MEMORY_CONTEXT_MESSAGES", 12)

    # Se False, o startup NAO exige um LLM (Ollama/NVIDIA/OpenAI) respondendo:
    # so registra WARNING e segue. O Telegram sobe normalmente; agentes com
    # ferramenta deterministica (ex.: scalaflow_intel) funcionam sem LLM, e o
    # roteamento cai no fallback por palavra-chave. Default True preserva o
    # comportamento atual (falha cedo se nenhum provedor responder).
    REQUIRE_LLM_ON_STARTUP: bool = _get_bool("REQUIRE_LLM_ON_STARTUP", True)

    # Tempo de vida do "lease" de líder (eleição p/ 2ª máquina / failover).
    LEASE_TTL_SECONDS: int = _get_int("LEASE_TTL_SECONDS", 60)

    # Token estático compartilhado com o ScalaFlow (Fase 9 -- receptor HTTP
    # de MarketIntelligenceHandoff em web/backend/routes/market_intelligence.py).
    # NUNCA um JWT de usuário da Studio -- autenticação service-to-service.
    # Vazio = endpoint responde 503 (integração não configurada), nunca abre
    # sem token.
    CRIS_OS_INTEGRATION_TOKEN: str = os.getenv("CRIS_OS_INTEGRATION_TOKEN", "").strip()

    # --- PageForge (executor PAGEFORGE -- core/pageforge_adapter.py) ---
    # Bridge já validado em produção do lado PageForge (repo
    # crissuboy-arch/forge-sales-page-skill). PAGEFORGE_BRIDGE_TOKEN
    # precisa ter EXATAMENTE o mesmo valor configurado na Vercel do
    # PageForge como CRIS_OS_BRIDGE_TOKEN. Vazio = adapter recusa despachar
    # (nunca finge sucesso, nunca chama sem autenticação).
    PAGEFORGE_API_URL: str = os.getenv("PAGEFORGE_API_URL", "https://pageforge-ai-woad.vercel.app").rstrip("/")
    PAGEFORGE_BRIDGE_TOKEN: str = os.getenv("PAGEFORGE_BRIDGE_TOKEN", "").strip()
    PAGEFORGE_TIMEOUT: int = _get_int("PAGEFORGE_TIMEOUT", 30)

    # --- ODS (Osmantic Deployment System) ---
    ODS_ENABLED: bool = _get_bool("ODS_ENABLED", True)
    ODS_BASE_URL: str = os.getenv("ODS_BASE_URL", "http://localhost:11434").rstrip("/")
    ODS_FALLBACK_URL: str = os.getenv("ODS_FALLBACK_URL", "http://localhost:8080").rstrip("/")
    ODS_WEBUI_URL: str = os.getenv("ODS_WEBUI_URL", "http://localhost:3000").rstrip("/")
    ODS_TIMEOUT: int = _get_int("ODS_TIMEOUT", 120)
    ODS_MODEL: str = os.getenv("ODS_MODEL", "auto").strip()

    # --- Fallback: OpenAI (API compatível) ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    OPENAI_TIMEOUT: int = _get_int("OPENAI_TIMEOUT", 120)

    # --- OpenRouter (IA remota, Fase 2.5) ---
    # So usado para tarefas que precisam de raciocinio/analise/geracao.
    # Consultas deterministicas (scalaflow_intel, filtros do Supabase) NUNCA
    # passam por aqui. Ver llm/openrouter.py.
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "").strip()
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    OPENROUTER_TIMEOUT: int = _get_int("OPENROUTER_TIMEOUT", 60)
    # Modelos por camada de custo (verificados no catalogo real do
    # OpenRouter -- ver llm/openrouter.py para como foram escolhidos e
    # quando isso foi conferido). Vazio = usa o padrao do codigo.
    OPENROUTER_MODEL_ECONOMICO: str = os.getenv("OPENROUTER_MODEL_ECONOMICO", "").strip()
    OPENROUTER_MODEL_INTELIGENTE: str = os.getenv("OPENROUTER_MODEL_INTELIGENTE", "").strip()
    OPENROUTER_MODEL_PREMIUM: str = os.getenv("OPENROUTER_MODEL_PREMIUM", "").strip()

    # --- ScalaFlow (Supabase) ---
    # SERVICE_KEY, nao a "anon key": a tabela produtos_minerados tem RLS
    # (auth.uid() = user_id) e o CRIS OS nao loga como usuario nenhum.
    # Com a anon key o resultado viria sempre vazio, sem erro aparecer.
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

    # --- Fallback: Google Gemini ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()

    # --- Provedor de fallback quando ODS está offline ---
    # Valores: "nvidia", "openai", "gemini", "anthropic"
    ODS_FALLBACK_PROVIDER: str = os.getenv("ODS_FALLBACK_PROVIDER", "nvidia").strip().lower()

    # --- Camada de cognição (autonomia) ---
    # Falso por padrão: a camada é CONSTRUÍDA (faz parte da arquitetura) mas fica
    # INATIVA; o atendimento segue pelo pipeline v3 até a próxima revisão.
    COGNITION_ENABLED: bool = _get_bool("COGNITION_ENABLED", False)
    EXECUTION_DEFAULT_TIMEOUT: int = _get_int("EXECUTION_DEFAULT_TIMEOUT", 120)
    EXECUTION_MAX_RETRIES: int = _get_int("EXECUTION_MAX_RETRIES", 1)
    QUALITY_MIN_SCORE: float = float(os.getenv("QUALITY_MIN_SCORE", "0.7"))
    MAX_REVISIONS: int = _get_int("MAX_REVISIONS", 2)

    def validate(self) -> list[str]:
        """
        Retorna uma lista de problemas de configuração.
        Lista vazia = tudo certo para rodar.
        """
        problemas: list[str] = []
        if not self.TELEGRAM_BOT_TOKEN:
            problemas.append(
                "TELEGRAM_BOT_TOKEN está vazio. Crie um bot no @BotFather e preencha o .env."
            )
        if not self.OLLAMA_HOST:
            problemas.append("OLLAMA_HOST está vazio.")
        if not self.OLLAMA_MODEL:
            problemas.append("OLLAMA_MODEL está vazio.")

        # Se ODS estiver habilitado, verifica configuracao basica
        if self.ODS_ENABLED:
            if not self.ODS_BASE_URL:
                problemas.append("ODS_BASE_URL está vazio.")

        return problemas


# Instância única usada em todo o projeto: "from config.settings import settings"
settings = Settings()
