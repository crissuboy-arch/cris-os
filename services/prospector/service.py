"""
ProspectorService — fachada do modulo Prospector dentro do CRIS OS.

Toda a logica fica aqui (camada de servico). As funcoes da Maquina de Leads
(motor/engine) sao chamadas como biblioteca via adapter — nenhuma regra de
negocio e copiada. Depois de cada escrita, os leads sao espelhados no banco
principal do CRIS OS (migracao idempotente).

IA: AIsa primeiro (via motor.chat); se indisponivel, fallback automatico no
roteador LLM do CRIS OS (ProspectorLLM).
"""

from __future__ import annotations

import contextlib
import io
import logging
import sys

from services.prospector import migration
from services.prospector.config import ml_dir

logger = logging.getLogger(__name__)

_PREFIXOS_ERRO = ("❌", "⚠️", "Erro:")


class ProspectorService:
    """Fachada do Prospector para o CRIS OS (API, Telegram, CEO, agentes)."""

    def __init__(self, llm_router=None, simular=None) -> None:
        self.llm_router = llm_router
        self._simular = simular  # None = resolve automatico no primeiro uso
        self._motor = None
        self._engine = None
        self._seguranca = None

    # ------------------------------------------------------------------
    #  Internos
    # ------------------------------------------------------------------

    def _carregar(self):
        """Carrega a Maquina de Leads como biblioteca (lazy) e injeta o fallback."""
        if self._motor is None:
            from services.prospector.adapter import carregar
            from services.prospector.llm import ProspectorLLM

            motor, engine, seguranca = carregar()
            self._motor, self._engine, self._seguranca = motor, engine, seguranca

            if self.llm_router is None:
                from services.prospector.llm import build_cris_router
                self.llm_router = build_cris_router()

            llm = ProspectorLLM(
                motor_chat=motor.chat,
                cris_router=self.llm_router,
                chave_fn=seguranca.chave_aisa,
            )
            motor.chat = llm.chat  # fallback automatico sem mudar o motor
        return self._motor, self._engine, self._seguranca

    def _resolver_simular(self, simular: bool | None = None) -> bool:
        if simular is not None:
            return simular
        if self._simular is None:
            try:
                from services.prospector.adapter import seguranca as _seg
                self._simular = not _seg().chave_aisa()
            except Exception:
                self._simular = True
        return self._simular

    def _rodar(self, fn, *args, **kwargs):
        """Executa uma funcao do engine/motor e espelha os leads no CRIS OS."""
        try:
            resultado = fn(*args, **kwargs)
        except SystemExit as exc:
            return {"ok": False, "erro": "Busca encerrada: %s" % exc}
        try:
            migration.sincronizar()
        except Exception as exc:  # pragma: no cover
            logger.warning("Falha ao sincronizar leads: %s", exc)
        return resultado

    # ------------------------------------------------------------------
    #  API publica
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """Situacao do modulo: provedor, modo, pasta da ML e total de leads."""
        chave = False
        dir_ok = False
        try:
            from services.prospector.adapter import seguranca as _seg
            chave = bool(_seg().chave_aisa())
            dir_ok = ml_dir().exists()
        except Exception:
            pass
        return {
            "provedor": "aisa" if chave else ("criss" if self.llm_router else "simular"),
            "chave_aisa_definida": chave,
            "ml_dir": str(ml_dir()),
            "ml_dir_existe": dir_ok,
            "modo": "simulacao" if self._resolver_simular() else "real",
            "leads": migration.contar(),
            "provedor_ia": "AIsa (primario) + roteador LLM do CRIS OS (fallback)",
        }

    def leads(self, status: str | None = None) -> list[dict]:
        """Leads espelhados no banco do CRIS OS (delega o motor para criar)."""
        migration.sincronizar()
        return migration.listar(status)

    def contratos(self) -> list[dict]:
        """Leads com contrato gerado/enviado."""
        migration.sincronizar()
        return migration.listar_contratos()

    def financeiro(self) -> dict:
        """Resumo financeiro (fechados, recebido, a receber, MRR)."""
        migration.sincronizar()
        return migration.resumo_financeiro()

    def prospectar(self, nicho: str, cidade: str, quantos: int | None = None,
                   simular: bool | None = None) -> dict:
        """Roda a busca de leads (motor.main)."""
        _, engine, _ = self._carregar()
        comando = "prospectar"
        if quantos:
            comando += " %d" % int(quantos)
        comando += " %s em %s" % (nicho, cidade)

        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                saida = engine.assistente(comando, simular=self._resolver_simular(simular))
        except SystemExit as exc:
            return {"ok": False, "simular": self._resolver_simular(simular),
                    "saida": "Busca encerrada: %s" % exc}
        except Exception as exc:
            return {"ok": False, "simular": self._resolver_simular(simular),
                    "saida": "Erro na busca: %s" % exc}

        texto = saida or buf.getvalue()
        try:
            n = migration.sincronizar()
        except Exception as exc:  # pragma: no cover
            n = 0
            logger.warning("Falha ao sincronizar leads: %s", exc)
        return {"ok": not texto.strip().startswith(_PREFIXOS_ERRO),
                "simular": self._resolver_simular(simular),
                "saida": texto.strip(),
                "leads_sincronizados": n}

    def redesenhar(self, slug: str, simular: bool | None = None) -> dict:
        _, engine, _ = self._carregar()
        msg = engine.redesenhar(slug, simular=self._resolver_simular(simular))
        self._rodar(lambda: None)  # sincroniza
        return {"ok": not msg.startswith(_PREFIXOS_ERRO), "mensagem": msg}

    def publicar(self, slug: str, simular: bool | None = None) -> dict:
        _, engine, _ = self._carregar()
        msg = engine.publicar(slug, simular=self._resolver_simular(simular))
        self._rodar(lambda: None)
        return {"ok": not msg.startswith(_PREFIXOS_ERRO), "mensagem": msg}

    def marcar_publicado(self, slug: str) -> dict:
        _, engine, _ = self._carregar()
        msg = engine.marcar_publicado(slug)
        self._rodar(lambda: None)
        return {"ok": not msg.startswith(_PREFIXOS_ERRO), "mensagem": msg}

    def proposta(self, slug: str, simular: bool | None = None) -> dict:
        _, engine, _ = self._carregar()
        msg = engine.proposta(slug, simular=self._resolver_simular(simular))
        self._rodar(lambda: None)
        return {"ok": not msg.startswith(_PREFIXOS_ERRO), "mensagem": msg}

    def contrato(self, slug: str, simular: bool | None = None) -> dict:
        _, engine, _ = self._carregar()
        msg = engine.contrato(slug, simular=self._resolver_simular(simular))
        self._rodar(lambda: None)
        return {"ok": not msg.startswith(_PREFIXOS_ERRO), "mensagem": msg}

    def followups(self, simular: bool | None = None) -> dict:
        _, engine, _ = self._carregar()
        msg = engine.followups(simular=self._resolver_simular(simular))
        self._rodar(lambda: None)
        return {"ok": not msg.startswith(_PREFIXOS_ERRO), "mensagem": msg}

    def fechar(self, slug: str, valor: float, manutencao: float | None = None) -> dict:
        _, engine, _ = self._carregar()
        msg = engine.fechar(slug, valor, manutencao)
        self._rodar(lambda: None)
        return {"ok": not msg.startswith(_PREFIXOS_ERRO), "mensagem": msg}

    def listar(self) -> str:
        _, engine, _ = self._carregar()
        return engine.listar()

    def executar_comando(self, msg: str, simular: bool | None = None) -> str:
        """Delega uma mensagem de comando para o assistente da Maquina de Leads."""
        _, engine, _ = self._carregar()
        try:
            resultado = engine.assistente(msg, simular=self._resolver_simular(simular))
        except SystemExit as exc:
            return "Comando encerrado: %s" % exc
        try:
            migration.sincronizar()
        except Exception as exc:  # pragma: no cover
            logger.warning("Falha ao sincronizar leads: %s", exc)
        return resultado


_service: ProspectorService | None = None


def get_prospector_service(llm_router=None) -> ProspectorService:
    """Singleton da fachada. Aceita o router do CRIS OS no primeiro uso."""
    global _service
    if _service is None:
        _service = ProspectorService(llm_router=llm_router)
    return _service
