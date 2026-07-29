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

from channels.telegram.client import TelegramClient, get_telegram_client
from core.contracts.channel import Handler
from core.models import IncomingMessage, OutgoingMessage

logger = logging.getLogger(__name__)

NAME = "telegram"


class TelegramChannel:
    """Canal Telegram. Recebe o `handler` (Gateway.handle) por injeção."""

    name = NAME

    def __init__(self, token: str, handler: Handler, ods_client=None,
                 agent_orchestrator=None, client: TelegramClient | None = None) -> None:
        self.token = token
        self.handler = handler
        self.ods_client = ods_client
        self.agent_orch = agent_orchestrator
        self._client = client or get_telegram_client()
        self._app: Application | None = None

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
            await update.message.reply_text(resposta)

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
        self._app = app
        app.add_handler(CommandHandler("start", self._on_start))
        app.add_handler(CommandHandler("ods", self._on_ods))
        app.add_handler(CommandHandler("agent", self._on_agent))
        app.add_handler(CommandHandler("agents", self._on_agents))
        app.add_handler(CommandHandler("use", self._on_use))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))

        logger.info("Canal Telegram iniciado. Aguardando mensagens...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

    def send(self, message: OutgoingMessage) -> bool:
        """Envia uma mensagem proativa para o canal.

        Implementa o protocolo Channel.send().
        """
        result = self._client.send_message(
            text=message.text,
            chat_id=message.recipient_id,
        )
        return result.get("ok", False)
