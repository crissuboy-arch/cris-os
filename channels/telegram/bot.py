"""
TelegramChannel — adaptador do Telegram (implementa a porta Channel).

Sua única responsabilidade é traduzir o Telegram <-> IncomingMessage e chamar o
`handler` (o Gateway). Ele NÃO conhece agentes, LLM nem memória — por isso trocar
ou adicionar canais não toca no núcleo.

A chamada ao núcleo é bloqueante (o modelo "pensa"), então roda em uma thread
separada para não travar o loop assíncrono do bot.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from core.contracts.channel import Handler
from core.models import IncomingMessage

logger = logging.getLogger(__name__)

NAME = "telegram"

# Limite real do Telegram e 4096 chars por mensagem; usamos uma margem de
# seguranca. Sem isso, uma resposta longa (ex.: Product Architect listando
# varias hipoteses de produto, Fase 3) faz `reply_text` levantar
# `telegram.error.BadRequest: Message is too long` e a resposta NUNCA chega
# -- bug real encontrado no teste da Fase 3.
_LIMITE_MENSAGEM_TELEGRAM = 4000


def _dividir_mensagem(texto: str, limite: int = _LIMITE_MENSAGEM_TELEGRAM) -> list[str]:
    """Quebra `texto` em pedacos <= `limite`, preferindo cortar em linhas
    em branco (paragrafos) e, se necessario, em quebras de linha simples --
    nunca no meio de uma palavra/emoji."""
    if len(texto) <= limite:
        return [texto]

    partes: list[str] = []
    atual = ""
    for linha in texto.split("\n"):
        candidato = f"{atual}\n{linha}" if atual else linha
        if len(candidato) <= limite:
            atual = candidato
            continue
        if atual:
            partes.append(atual)
        if len(linha) <= limite:
            atual = linha
        else:
            # linha unica gigante (raro): corta em blocos fixos
            for i in range(0, len(linha), limite):
                partes.append(linha[i : i + limite])
            atual = ""
    if atual:
        partes.append(atual)
    return partes


def enviar_mensagem_proativa(texto: str) -> bool:
    """
    Envia uma mensagem ao Telegram FORA do ciclo pergunta/resposta normal
    (ex.: notificar uma aprovação pendente criada por um handoff recebido
    via HTTP, sem nenhuma mensagem do usuário para responder).

    Usa a API HTTP do Telegram diretamente (mesmo princípio de
    `agent_builder/notifier.py`), mas reaproveita o MESMO
    `TELEGRAM_BOT_TOKEN`/`TELEGRAM_ALLOWED_USER_ID` já usados por todo o
    resto do bot (`config/settings.py`) -- nenhuma variável de ambiente
    nova, nenhum segundo bot/token. Funciona independente do processo
    `run_polling()` estar rodando (envio de mensagem é uma chamada HTTP
    stateless da API do Telegram, não depende do loop de polling).

    NUNCA lança exceção -- falha de rede/Telegram vira log + `False`,
    nunca interrompe quem chamou (a orquestração que gerou a notificação
    já persistiu o que precisava antes de notificar).
    """
    import urllib.error
    import urllib.request
    import json as _json

    from config.settings import settings

    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_ALLOWED_USER_ID
    if not token or not chat_id:
        logger.warning("=== [TELEGRAM] Notificação proativa sem TELEGRAM_BOT_TOKEN/TELEGRAM_ALLOWED_USER_ID configurados ===")
        return False

    sucesso = True
    for parte in _dividir_mensagem(texto):
        payload = _json.dumps({"chat_id": chat_id, "text": parte}).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=payload, method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resultado = _json.loads(resp.read().decode())
                sucesso = sucesso and bool(resultado.get("ok"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("=== [TELEGRAM] Falha ao enviar notificação proativa: %s ===", exc)
            sucesso = False
    return sucesso


class TelegramChannel:
    """Canal Telegram. Recebe o `handler` (Gateway.handle) por injeção."""

    name = NAME

    def __init__(self, token: str, handler: Handler, ods_client=None,
                 agent_orchestrator=None) -> None:
        self.token = token
        self.handler = handler
        self.ods_client = ods_client
        self.agent_orch = agent_orchestrator

    # ------------------------------------------------------------------
    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Oi, Cris! Aqui é o Cris OS. Me conta o que você precisa — eu organizo "
            "e aciono a equipe certa pra você. Pode escrever do seu jeito."
        )

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        incoming = IncomingMessage(
            channel=self.name,
            sender_id=str(update.effective_user.id),
            text=update.message.text or "",
        )

        # Mostra "digitando..." enquanto a equipe trabalha.
        await update.message.chat.send_action(ChatAction.TYPING)

        # O núcleo é bloqueante -> roda fora do event loop.
        resposta = await asyncio.to_thread(self.handler, incoming)

        if resposta:
            for parte in _dividir_mensagem(resposta):
                await update.message.reply_text(parte)

    async def _on_agent(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /agent: mostra o agente ativo."""
        if not self.agent_orch:
            await update.message.reply_text(
                "Sistema de agentes especialistas nao esta ativo.\n"
                "Configure DEFAULT_AGENT=auto no .env para ativar."
            )
            return
        user_id = str(update.effective_user.id)
        agente = self.agent_orch.get_active_agent(user_id)
        if agente == "auto":
            await update.message.reply_text(
                "Modo: automatico\n"
                "O orquestrador escolhe o melhor agente para cada mensagem.\n"
                "Use /use <nome> para fixar um agente."
            )
        else:
            agent_obj = self.agent_orch.agents.get(agente)
            desc = agent_obj.description if agent_obj else ""
            await update.message.reply_text(
                f"Agente ativo: {agente}\n{desc}\n\n"
                f"Use /use auto para voltar ao modo automatico."
            )

    async def _on_agents(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /agents: lista todos os agentes disponiveis."""
        if not self.agent_orch:
            await update.message.reply_text(
                "Sistema de agentes especialistas nao esta ativo.\n"
                "Configure DEFAULT_AGENT=auto no .env para ativar."
            )
            return
        texto = self.agent_orch.list_agents()
        await update.message.reply_text(f"```\n{texto}\n```")

    async def _on_use(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /use <agente>: define o agente ativo."""
        if not self.agent_orch:
            await update.message.reply_text(
                "Sistema de agentes especialistas nao esta ativo.\n"
                "Configure DEFAULT_AGENT=auto no .env para ativar."
            )
            return

        args = context.args or []
        if not args:
            await update.message.reply_text(
                "Uso: /use <nome_do_agente>\n"
                "Exemplo: /use marketing\n"
                "Para voltar ao automatico: /use auto\n\n"
                "Agentes disponiveis: " + ", ".join(sorted(self.agent_orch.agents))
            )
            return

        nome = args[0].strip().lower()
        user_id = str(update.effective_user.id)

        if nome in ("auto", "automatico", "automatic"):
            resposta = self.agent_orch.set_active_agent(user_id, None)
        else:
            resposta = self.agent_orch.set_active_agent(user_id, nome)

        await update.message.reply_text(resposta)

    async def _on_ods(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /ods: exibe status do ODS."""
        if not self.ods_client:
            await update.message.reply_text(
                "ODS nao esta configurado neste CRIS OS.\n"
                "Adicione ODS_ENABLED=true ao .env para ativar."
            )
            return

        args = context.args or []
        if args and args[0] in ("check", "testar", "teste"):
            texto = self.ods_client.to_check_text()
        elif args and args[0] in ("on", "ativar", "1", "true"):
            self.ods_client.enabled = True
            texto = "ODS ativado. Use /ods para ver o status."
        elif args and args[0] in ("off", "desativar", "0", "false"):
            self.ods_client.enabled = False
            texto = "ODS desativado. Use /ods on para reativar."
        elif args and args[0] in ("reset", "limpar"):
            self.ods_client._cache(None)  # noqa
            texto = "Cache de status limpo. Use /ods para verificar novamente."
        else:
            texto = self.ods_client.to_status_text()

        await update.message.reply_text(f"```\n{texto}\n```")

    # ------------------------------------------------------------------
    def run(self) -> None:
        """Inicia o canal em long-polling (bloqueante)."""
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start", self._on_start))
        app.add_handler(CommandHandler("ods", self._on_ods))
        app.add_handler(CommandHandler("agent", self._on_agent))
        app.add_handler(CommandHandler("agents", self._on_agents))
        app.add_handler(CommandHandler("use", self._on_use))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))

        logger.info("Canal Telegram iniciado. Aguardando mensagens...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
