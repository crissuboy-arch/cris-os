"""
TelegramClient — client compartilhado para o Telegram.

Fornece uma interface unificada para enviar mensagens via API do Telegram.
Usado tanto pelo TelegramChannel (bot) quanto pelo StudioNotifier.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


class TelegramClient:
    """Client compartilhado para API do Telegram.

    Gerencia token, chat_id e envio de mensagens.
    Thread-safe para uso em multiplos contextos.
    """

    def __init__(self, token: str = "", chat_id: str = "") -> None:
        self._token = token or settings.TELEGRAM_BOT_TOKEN
        self._chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self._enabled = bool(self._token and self._chat_id)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def token(self) -> str:
        return self._token

    @property
    def chat_id(self) -> str:
        return self._chat_id

    def configure(self, token: str, chat_id: str) -> None:
        """Configura token e chat_id."""
        self._token = token
        self._chat_id = chat_id
        self._enabled = bool(token and chat_id)

    def send_message(
        self,
        text: str,
        chat_id: str = "",
        parse_mode: str = "Markdown",
        reply_markup: dict | None = None,
        timeout: int = 10,
    ) -> dict[str, Any]:
        """Envia uma mensagem via API do Telegram.

        Args:
            text: Texto da mensagem.
            chat_id: Chat de destino (usa self._chat_id se vazio).
            parse_mode: Modo de parse (Markdown, HTML).
            reply_markup: Teclado inline (opcional).
            timeout: Timeout em segundos.

        Returns:
            Dict com resultado (ok, result, error).
        """
        if not self._enabled:
            return {"ok": False, "error": "Telegram not configured"}

        target_chat = chat_id or self._chat_id
        if not target_chat:
            return {"ok": False, "error": "No chat_id configured"}

        payload: dict[str, Any] = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        data = json.dumps(payload).encode("utf-8")

        try:
            url = f"{TELEGRAM_API}/bot{self._token}/sendMessage"
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode())
                if not result.get("ok"):
                    logger.warning("Telegram API error: %s", result.get("description"))
                return result
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode() if exc.fp else str(exc)
            logger.error("Telegram HTTP error %d: %s", exc.code, error_body)
            return {"ok": False, "error": f"HTTP {exc.code}: {error_body}"}
        except Exception as exc:
            logger.error("Telegram send failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def send_message_with_keyboard(
        self,
        text: str,
        buttons: list[list[dict[str, str]]],
        chat_id: str = "",
        parse_mode: str = "Markdown",
    ) -> dict[str, Any]:
        """Envia mensagem com teclado inline.

        Args:
            text: Texto da mensagem.
            buttons: Matriz de botoes [[{text, callback_data}]].
            chat_id: Chat de destino.
            parse_mode: Modo de parse.

        Returns:
            Dict com resultado.
        """
        keyboard = {"inline_keyboard": buttons}
        return self.send_message(
            text=text,
            chat_id=chat_id,
            parse_mode=parse_mode,
            reply_markup=keyboard,
        )

    def answer_callback(
        self,
        callback_query_id: str,
        text: str = "",
        show_alert: bool = False,
    ) -> dict[str, Any]:
        """Responde a um callback query (botao inline).

        Args:
            callback_query_id: ID do callback.
            text: Texto de resposta (vazio = sem notificacao).
            show_alert: Se True, mostra alerta em vez de toast.

        Returns:
            Dict com resultado.
        """
        if not self._enabled:
            return {"ok": False, "error": "Telegram not configured"}

        payload = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert,
        }

        data = json.dumps(payload).encode("utf-8")

        try:
            url = f"{TELEGRAM_API}/bot{self._token}/answerCallbackQuery"
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:
            logger.error("Telegram callback answer failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def get_chat_id_from_update(self, user_id: str) -> str:
        """Retorna o chat_id para envio proativo.

        Se self._chat_id estiver configurado, usa ele.
        Caso contrario, retorna vazio (notificacao impossivel).
        """
        return self._chat_id


# Singleton compartilhado
_client: TelegramClient | None = None


def get_telegram_client() -> TelegramClient:
    """Retorna a instancia singleton do TelegramClient."""
    global _client
    if _client is None:
        _client = TelegramClient()
    return _client
