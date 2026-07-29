"""
TelegramChannel — adaptador do Telegram (implementa a porta Channel).

Suas responsabilidades:
  1. Traduzir Telegram <-> IncomingMessage e chamar o handler (Gateway)
  2. Gerenciar conversa natural com interpretacao de linguagem natural
  3. Suportar comandos (/agent, /use, etc.) e linguagem natural simultaneamente
  4. Manter contexto por utilizador (historico, agente ativo)

A chamada ao nucleo e bloqueante (o modelo "pensa"), entao roda em uma thread
separada para nao travar o loop assincrono do bot.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict

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
from channels.telegram.conversation import ConversationManager
from channels.telegram.utils import ConfirmationUtils
from core.contracts.channel import Handler
from core.models import IncomingMessage, OutgoingMessage

logger = logging.getLogger(__name__)

NAME = "telegram"


def _generate_confirmation_id() -> str:
    """Gera um ID único para confirmação."""
    return f"conf_{secrets.token_urlsafe(8)}"


def _generate_confirmation_id() -> str:
    """Gera um ID único para confirmação."""
    _confirmation_counter["value"] += 1
    return f"conf_{secrets.token_urlsafe(8)}"


class TelegramChannel:
    """Canal Telegram. Recebe o `handler` (Gateway.handle) por injecao.

    Suporta tanto comandos (/agent, /use) quanto linguagem natural.
    A ConversationManager gerencia interpretacao, selecao de agente e contexto.
    """

    name = NAME

    def __init__(
        self,
        token: str,
        handler: Handler,
        ods_client=None,
        agent_orchestrator=None,
        client: TelegramClient | None = None,
        conversation_manager: ConversationManager | None = None,
    ) -> None:
        self.token = token
        self.handler = handler
        self.ods_client = ods_client
        self.agent_orch = agent_orchestrator
        self._client = client or get_telegram_client()
        self._conversation = conversation_manager
        self._app: Application | None = None

    # ------------------------------------------------------------------
    # Comandos
    # ------------------------------------------------------------------

    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Ola! Aqui e o CRIS OS.\n\n"
            "Me conta o que voce precisa — eu organizo e aciono a equipe certa.\n"
            "Pode escrever do seu jeito, sem comandos.\n\n"
            "Comandos disponiveis:\n"
            "/agent - ver agente ativo\n"
            "/agents - listar agentes\n"
            "/use <nome> - fixar agente\n"
            "/status - ver status da conversa\n"
            "/clear - limpar historico"
        )

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.message.text or ""
        user_id = str(update.effective_user.id)

        await update.message.chat.send_action(ChatAction.TYPING)

        if self._conversation:
            response, agent_name = await asyncio.to_thread(
                self._conversation.handle_message, user_id, text,
            )
            formatted = self._conversation.format_response(response, agent_name)
            await update.message.reply_text(formatted)
        else:
            incoming = IncomingMessage(
                channel=self.name,
                sender_id=user_id,
                text=text,
            )
            response = await asyncio.to_thread(self.handler, incoming)
            if response:
                await update.message.reply_text(response)

    async def _on_agent(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = str(update.effective_user.id)

        if self._conversation:
            status = self._conversation.get_status(user_id)
            active = status.get("active_agent")
            last = status.get("last_agent")
            lines = ["*Status do Agente*", ""]
            if active:
                lines.append(f"Agente fixo: {active}")
            else:
                lines.append("Modo: automatico")
            if last:
                lines.append(f"Ultimo agente: {last}")
            lines.append("")
            lines.append("Use /use <nome> para fixar um agente.")
            lines.append("Use /use auto para voltar ao automatico.")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        elif self.agent_orch:
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
        else:
            await update.message.reply_text(
                "Sistema de agentes nao esta ativo.\n"
                "Configure DEFAULT_AGENT=auto no .env para ativar."
            )

    async def _on_agents(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self._conversation:
            agents = self._conversation.selector.list_agents()
            lines = ["*Agentes Disponiveis*", ""]
            for name in agents:
                display = name.replace("_", " ").title()
                lines.append(f"  {display}")
            lines.append("")
            lines.append("Use /use <nome> para fixar um agente.")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        elif self.agent_orch:
            texto = self.agent_orch.list_agents()
            await update.message.reply_text(f"```\n{texto}\n```")
        else:
            await update.message.reply_text(
                "Sistema de agentes nao esta ativo.\n"
                "Configure DEFAULT_AGENT=auto no .env para ativar."
            )

    async def _on_use(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        args = context.args or []
        user_id = str(update.effective_user.id)

        if not args:
            await update.message.reply_text(
                "Uso: /use <nome_do_agente>\n"
                "Exemplo: /use marketing\n"
                "Para voltar ao automatico: /use auto"
            )
            return

        nome = args[0].strip().lower()

        if self._conversation:
            if nome in ("auto", "automatico", "automatic"):
                resposta = self._conversation.set_active_agent(user_id, None)
            else:
                resposta = self._conversation.set_active_agent(user_id, nome)
            await update.message.reply_text(resposta)
        elif self.agent_orch:
            if nome in ("auto", "automatico", "automatic"):
                resposta = self.agent_orch.set_active_agent(user_id, None)
            else:
                resposta = self.agent_orch.set_active_agent(user_id, nome)
            await update.message.reply_text(resposta)
        else:
            await update.message.reply_text(
                "Sistema de agentes nao esta ativo.\n"
                "Configure DEFAULT_AGENT=auto no .env para ativar."
            )

    async def _on_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = str(update.effective_user.id)
        if not self._conversation:
            await update.message.reply_text("ConversationManager nao configurado.")
            return
        status = self._conversation.get_status(user_id)
        lines = ["*Status da Conversa*", ""]
        lines.append(f"Agente ativo: {status.get('active_agent', 'Nenhum')}")
        lines.append(f"Ultimo agente: {status.get('last_agent', 'Nenhum')}")
        lines.append(f"Mensagens no historico: {status.get('history_size', 0)}")
        agents = status.get("available_agents", [])
        lines.append(f"Agentes disponiveis: {len(agents)}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _on_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = str(update.effective_user.id)
        if self._conversation:
            self._conversation.context_manager.clear_history(user_id)
            await update.message.reply_text("Historico limpo com sucesso.")
        else:
            await update.message.reply_text("ConversationManager nao configurado.")

    async def _on_ods(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    # Lifecycle
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
        app.add_handler(CommandHandler("status", self._on_status))
        app.add_handler(CommandHandler("clear", self._on_clear))
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
