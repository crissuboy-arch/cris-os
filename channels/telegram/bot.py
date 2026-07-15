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


class TelegramChannel:
    """Canal Telegram. Recebe o `handler` (Gateway.handle) por injeção."""

    name = NAME

    def __init__(self, token: str, handler: Handler) -> None:
        self.token = token
        self.handler = handler

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

    # ------------------------------------------------------------------
    def run(self) -> None:
        """Inicia o canal em long-polling (bloqueante)."""
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start", self._on_start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))

        logger.info("Canal Telegram iniciado. Aguardando mensagens...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
