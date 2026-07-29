"""
ODSClient — Cliente para o Osmantic Deployment System (ODS).

Detecta e monitora os servicos do ODS:
  - Ollama (porta 11434) — inferencia local de LLM (Linux Docker)
  - llama-server (porta 8080) — servidor nativo Windows/macOS
  - Open WebUI (porta 3000) — interface web

Fornece health check, auto-detecao de porta e informacao do modelo carregado.
Usa a mesma API requests do resto do CRIS OS. Nao adiciona dependencias.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)


@dataclass
class ServiceInfo:
    status: str = "unknown"  # "online" | "offline" | "unknown" | "error"
    url: str = ""
    label: str = ""
    latency_ms: float = 0.0
    models: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class ODSStatus:
    enabled: bool = False
    ollama: ServiceInfo = field(default_factory=ServiceInfo)
    llama_server: ServiceInfo = field(default_factory=ServiceInfo)
    webui: ServiceInfo = field(default_factory=ServiceInfo)
    active_ollama_url: str = ""
    active_model: str = ""
    loaded_models: list[str] = field(default_factory=list)
    error: str = ""


class ODSClient:
    """
    Cliente central para deteccao e monitoramento do ODS.

    Uso tipico:
        ods = ODSClient(enabled=True, base_url="http://localhost:11434")
        status = ods.check_all()
        if status.active_ollama_url:
            print(f"ODS online: {status.active_model}")
    """

    def __init__(
        self,
        enabled: bool = True,
        base_url: str = "http://localhost:11434",
        fallback_url: str = "http://localhost:8080",
        webui_url: str = "http://localhost:3000",
        timeout: int = 120,
        model: str = "auto",
    ) -> None:
        self.enabled = enabled
        self.base_url = base_url.rstrip("/")
        self.fallback_url = fallback_url.rstrip("/")
        self.webui_url = webui_url.rstrip("/")
        self.timeout = timeout
        self.model = model

        self._last_status: ODSStatus | None = None
        self._last_check_time: float = 0.0
        self._check_ttl: float = 15.0  # recache a cada 15s

    # ------------------------------------------------------------------
    #  Metodos publicos
    # ------------------------------------------------------------------

    def check_all(self) -> ODSStatus:
        """Testa todos os endpoints e retorna status consolidado."""
        agora = time.time()
        if self._last_status and (agora - self._last_check_time) < self._check_ttl:
            return self._last_status

        status = ODSStatus(enabled=self.enabled)

        if not self.enabled:
            status.error = "ODS esta desabilitado (ODS_ENABLED=false)"
            self._cache(status)
            return status

        # 1) Testa Ollama na porta base (11434).
        ollama = self._check_ollama(self.base_url)
        status.ollama = ollama

        if ollama.status == "online":
            status.active_ollama_url = self.base_url
            status.loaded_models = ollama.models
            status.active_model = self._resolve_model(ollama.models)
        else:
            # 2) Fallback: tenta porta alternativa (8080 — nativo Windows/macOS).
            llama = self._check_ollama(self.fallback_url)
            status.llama_server = llama
            if llama.status == "online":
                status.active_ollama_url = self.fallback_url
                status.loaded_models = llama.models
                status.active_model = self._resolve_model(llama.models)

        # 3) Testa Open WebUI.
        status.webui = self._check_webui(self.webui_url)

        if not status.active_ollama_url:
            status.error = "Nenhum servico de LLM do ODS esta respondendo"

        self._cache(status)
        return status

    def is_online(self) -> bool:
        """True se pelo menos um servico de LLM do ODS esta acessivel."""
        s = self.check_all()
        return bool(s.active_ollama_url)

    def get_active_url(self) -> str:
        """Retorna a URL ativa do Ollama, ou a base_url se nada foi detectado."""
        s = self.check_all()
        return s.active_ollama_url or self.base_url

    def get_loaded_models(self) -> list[str]:
        """Lista os modelos carregados no servidor Ollama ativo."""
        s = self.check_all()
        return s.loaded_models

    def to_status_text(self) -> str:
        """Formata o status como texto viavel para Telegram."""
        s = self.check_all()

        linhas: list[str] = []
        linhas.append("ODS — Status dos Servicos")
        linhas.append("=" * 32)

        if not s.enabled:
            linhas.append("")
            linhas.append(" [!] Desabilitado (ODS_ENABLED=false)")
            linhas.append("")
            linhas.append("Use /ods on para ativar ou configure o .env.")
            return "\n".join(linhas)

        self._adicionar_linha_servico(linhas, "Ollama", s.ollama, "(porta 11434)")
        self._adicionar_linha_servico(linhas, "llama-server", s.llama_server, "(porta 8080)")
        self._adicionar_linha_servico(linhas, "Open WebUI", s.webui, "(porta 3000)")

        linhas.append("")
        linhas.append("-" * 32)

        if s.active_model:
            linhas.append(f"  Modelo ativo: {s.active_model}")
        elif s.loaded_models:
            linhas.append(f"  Modelos disponiveis: {', '.join(s.loaded_models)}")
        else:
            linhas.append("  Nenhum modelo carregado")

        if s.active_ollama_url:
            linhas.append(f"  Endpoint: {s.active_ollama_url}")

        if s.error:
            linhas.append("")
            linhas.append(f" [!] {s.error}")

        linhas.append("")
        linhas.append("Dica: /ods check para um teste detalhado.")
        return "\n".join(linhas)

    def to_check_text(self) -> str:
        """Formata um teste detalhado de conexao."""
        s = self.check_all()

        linhas: list[str] = []
        linhas.append("ODS — Teste de Conexao")
        linhas.append("=" * 32)

        if not s.enabled:
            linhas.append("")
            linhas.append(" [!] ODS esta desabilitado.")
            linhas.append("     Configure ODS_ENABLED=true no .env")
            return "\n".join(linhas)

        for info, label, porta in [
            (s.ollama, "Ollama", "11434"),
            (s.llama_server, "llama-server", "8080"),
            (s.webui, "Open WebUI", "3000"),
        ]:
            self._adicionar_linha_servico(linhas, label, info, f"(porta {porta})")

        linhas.append("")
        linhas.append("-" * 32)
        if s.error:
            linhas.append(f"  Resultado: FALHA — {s.error}")
        else:
            linhas.append("  Resultado: OK — ODS esta operacional")
            linhas.append(f"  Modelo ativo: {s.active_model}")

        return "\n".join(linhas)

    # ------------------------------------------------------------------
    #  Metodos internos
    # ------------------------------------------------------------------

    def _check_ollama(self, url: str) -> ServiceInfo:
        """Testa se o endpoint responde como servidor Ollama."""
        info = ServiceInfo(url=url, label="Ollama")

        try:
            t0 = time.perf_counter()
            r = requests.get(f"{url}/api/tags", timeout=5)
            elapsed = (time.perf_counter() - t0) * 1000
            info.latency_ms = round(elapsed, 1)

            if r.status_code == 200:
                info.status = "online"
                dados = r.json()
                models_raw = dados.get("models", [])
                info.models = [
                    m.get("name", "") for m in models_raw if m.get("name")
                ]
            else:
                info.status = "error"
                info.error = f"HTTP {r.status_code}"
        except requests.Timeout:
            info.status = "offline"
            info.error = "Timeout apos 5s"
        except requests.ConnectionError:
            info.status = "offline"
            info.error = "Conexao recusada"
        except Exception as exc:
            info.status = "error"
            info.error = str(exc)

        return info

    def _check_webui(self, url: str) -> ServiceInfo:
        """Testa se o Open WebUI esta acessivel."""
        info = ServiceInfo(url=url, label="Open WebUI")

        try:
            t0 = time.perf_counter()
            r = requests.get(url, timeout=5)
            elapsed = (time.perf_counter() - t0) * 1000
            info.latency_ms = round(elapsed, 1)

            if r.status_code in (200, 302, 304):
                info.status = "online"
            else:
                info.status = "error"
                info.error = f"HTTP {r.status_code}"
        except requests.Timeout:
            info.status = "offline"
            info.error = "Timeout apos 5s"
        except requests.ConnectionError:
            info.status = "offline"
            info.error = "Conexao recusada"
        except Exception as exc:
            info.status = "error"
            info.error = str(exc)

        return info

    def _resolve_model(self, models: list[str]) -> str:
        """Escolhe o modelo ativo com base na configuracao."""
        if not models:
            return ""
        if self.model == "auto":
            return models[0]
        if self.model in models:
            return self.model
        similar = [m for m in models if self.model in m]
        if similar:
            return similar[0]
        return models[0]

    def _adicionar_linha_servico(
        self, linhas: list[str], label: str, info: ServiceInfo, porta: str
    ) -> None:
        """Adiciona uma linha de status de servico formatada."""
        icone = self._icone_status(info.status)
        latencia = f"({info.latency_ms:.0f}ms)" if info.latency_ms > 0 else ""
        linhas.append(f"  {icone} {label} {porta}: {info.status.upper()} {latencia}")
        if info.models:
            linhas.append(f"       Modelos: {', '.join(info.models)}")
        if info.error:
            linhas.append(f"       Erro: {info.error}")

    @staticmethod
    def _icone_status(status: str) -> str:
        return {"online": "[OK]", "offline": "[--]", "error": "[!]", "unknown": "[?]"}.get(
            status, "[?]"
        )

    def _cache(self, status: ODSStatus) -> None:
        self._last_status = status
        self._last_check_time = time.time()
