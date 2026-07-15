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
    DEFAULT_AGENT: str = os.getenv("DEFAULT_AGENT", "secretary").strip()
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    MEMORY_CONTEXT_MESSAGES: int = _get_int("MEMORY_CONTEXT_MESSAGES", 12)

    # Tempo de vida do "lease" de líder (eleição p/ 2ª máquina / failover).
    LEASE_TTL_SECONDS: int = _get_int("LEASE_TTL_SECONDS", 60)

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
        return problemas


# Instância única usada em todo o projeto: "from config.settings import settings"
settings = Settings()
