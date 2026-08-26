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
import time

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from channels.telegram.client import TelegramClient, get_telegram_client
from channels.telegram.conversation import ConfirmationGateway, ConversationManager
from channels.telegram.persistence import TelegramPersistenceService
from core.contracts.channel import Handler
from core.models import IncomingMessage, OutgoingMessage
from core.registry import AgentRegistry
from memory.memory_system import MemorySystem

logger = logging.getLogger(__name__)

NAME = "telegram"


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
        persistence_service: TelegramPersistenceService | None = None,
        agent_registry: AgentRegistry | None = None,
        memory_system: MemorySystem | None = None,
        ceo_mode=None,
    ) -> None:
        self.token = token
        self.handler = handler
        self.ods_client = ods_client
        self.agent_orch = agent_orchestrator
        self._client = client or get_telegram_client()
        self._conversation = conversation_manager
        self.confirmation_gateway = (
            conversation_manager.confirmation_gateway
            if conversation_manager
            else ConfirmationGateway()
        )
        self.persistence = persistence_service or TelegramPersistenceService()
        self._app: Application | None = None
        self.agent_registry = agent_registry
        self.memory = memory_system
        self.ceo_mode = ceo_mode

    # ------------------------------------------------------------------
    # Memoria — lembrar/esquecer/pesquisar
    # ------------------------------------------------------------------

    async def _on_memory_lembrar(self, text: str, user_id: str) -> str:
        """Processa 'lembre que X' e salva na memoria."""
        item = self.memory.remember(text, user_id)
        return (
            f"✅ Lembrei! ({item.type})\n"
            f"\"{item.title}\"\n"
            f"Importancia: {item.importance}/10 | Projeto: {item.project or '(nenhum)'}"
        )

    async def _on_memory_esquecer(self, text: str, user_id: str) -> str:
        """Processa 'esqueca X' e lista candidatos para confirmacao."""
        candidates = self.memory.forget(text, user_id)
        if not candidates:
            return (
                "Nao encontrei nenhuma informacao sobre isso na minha memoria.\n"
                "Pode descrever melhor o que deseja esquecer?"
            )
        if len(candidates) == 1:
            c = candidates[0]
            return (
                f"Deseja esquecer esta informacao?\n\n"
                f"\"{c.title}\"\n"
                f"  Projeto: {c.project or '-'} | Cliente: {c.client or '-'} | "
                f"Importancia: {c.importance}/10\n\n"
                f"Responda com /forget {c.id} para confirmar\n"
                f"Ou /cancel para cancelar."
            )
        lines = [
            "Encontrei estas informacoes. Qual delas deseja esquecer?",
            "",
        ]
        for i, c in enumerate(candidates[:5], 1):
            lines.append(f"{i}. \"{c.title}\"")
            lines.append(f"   Projeto: {c.project or '-'} | Cliente: {c.client or '-'}")
            lines.append(f"   /forget {c.id}")
            lines.append("")
        lines.append("Ou /cancel para cancelar.")
        return "\n".join(lines)

    async def _on_memory_query(self, text: str, user_id: str) -> str:
        """Processa 'o que voce sabe sobre X'."""
        results = self.memory.query(text, user_id)
        if not results:
            return "Nao encontrei nada na minha memoria sobre isso."
        lines = [f"Encontrei {len(results)} registro(s) na memoria:\n"]
        for r in results:
            acesso = f" (acessado {r.access_count}x)" if r.access_count else ""
            lines.append(
                f"📌 \"{r.title}\"{acesso}\n"
                f"   Projeto: {r.project or '-'} | Cliente: {r.client or '-'} | "
                f"Importancia: {r.importance}/10 | Origem: {r.origin}\n"
            )
        return "\n".join(lines)

    async def _on_forget(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/forget <id> — confirma e executa exclusao."""
        if not self.memory:
            await update.message.reply_text("Sistema de memoria nao esta ativo.")
            return
        args = context.args or []
        if not args:
            await update.message.reply_text("Uso: /forget <id_da_memoria>")
            return
        item_id = args[0]
        user_id = str(update.effective_user.id)
        ok = self.memory.confirm_forget(item_id, user_id)
        if ok:
            await update.message.reply_text("🗑 Informacao esquecida com sucesso.")
        else:
            await update.message.reply_text(
                "Nao encontrei essa informacao na sua memoria. O ID pode estar incorreto."
            )

    async def _on_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/cancel — cancela operacao atual."""
        await update.message.reply_text("Operacao cancelada.")

    async def _on_memory_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/memory — estatisticas da memoria."""
        if not self.memory:
            await update.message.reply_text("Sistema de memoria nao esta ativo.")
            return
        user_id = str(update.effective_user.id)
        stats = self.memory.stats(user_id)
        lines = ["*Minha Memoria — Estatisticas*", ""]
        lines.append(f"Total de registros: {stats['total']}")
        lines.append(f"Total de acessos: {stats['total_acessos']}")
        if stats.get("por_tipo"):
            lines.append("")
            lines.append("Por tipo:")
            for t, q in stats["por_tipo"].items():
                lines.append(f"  {t}: {q}")
        if stats.get("por_origem"):
            lines.append("")
            lines.append("Por origem:")
            for o, q in stats["por_origem"].items():
                lines.append(f"  {o}: {q}")
        lines.append("")
        lines.append("Comandos:")
        lines.append("  \"lembre que...\" — salva informacao")
        lines.append("  \"esqueca...\" — remove informacao")
        lines.append("  \"o que voce sabe sobre...\" — consulta")
        lines.append("  /forget <id> — confirma exclusao")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

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
            "/clear - limpar historico\n"
            "/approve <id> - aprovar confirmacao\n"
            "/reject <id> - rejeitar confirmacao\n"
            "/confirmations - listar confirmacoes pendentes\n"
            "/memory - ver estatisticas da memoria\n"
            "/forget <id> - esquecer informacao\n"
            "/prospectar <nicho> em <cidade> - buscar leads\n"
            "/redesenhar <slug> - redesenhar site de um lead\n"
            "/proposta <slug> - gerar proposta\n"
            "/publicar <slug> - publicar site\n"
            "/contrato <slug> - gerar contrato\n"
            "/followup - rodar follow-ups\n\n"
            "Memoria:\n"
            "\"lembre que...\" — salva informacao\n"
            "\"esqueca...\" — inicia exclusao\n"
            "\"o que voce sabe sobre...\" — consulta"
        )

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.message.text or ""
        user_id = str(update.effective_user.id)
        t_received = time.perf_counter()
        agent_name = None

        # PING fast-path — mede latencia pura do Telegram sem LLM
        if text.strip().upper() == "PING":
            await update.message.chat.send_action(ChatAction.TYPING)
            t_antes_envio = time.perf_counter()
            await update.message.reply_text("PONG")
            t_total = (time.perf_counter() - t_received) * 1000
            logger.info(
                "=== [PERF] PING-PONG: recebido=%.6f  enviado=%.6f  total=%.0fms ===",
                t_received, t_antes_envio, t_total,
            )
            return

        await update.message.chat.send_action(ChatAction.TYPING)

        # Memoria fast-path — processa sem LLM se detectado
        if self.memory and self.memory.should_save(text):
            intent = self.memory.detect_intent(text)
            if intent in ("remember", "remember_project"):
                response = await self._on_memory_lembrar(text, user_id)
                await update.message.reply_text(response)
                return
            if intent == "forget":
                response = await self._on_memory_esquecer(text, user_id)
                await update.message.reply_text(response)
                return
            if intent == "query":
                response = await self._on_memory_query(text, user_id)
                if "Nao encontrei" not in response:
                    await update.message.reply_text(response)
                    return

        if self._conversation:
            t_gateway_start = time.perf_counter()
            response, agent_name = await asyncio.to_thread(
                self._conversation.handle_message, user_id, text,
            )
            t_apos_llm = time.perf_counter()
            formatted = self._conversation.format_response(response, agent_name)
            await update.message.reply_text(formatted)
        else:
            incoming = IncomingMessage(
                channel=self.name,
                sender_id=user_id,
                text=text,
            )
            t_gateway_start = time.perf_counter()
            response = await asyncio.to_thread(self.handler, incoming)
            t_apos_llm = time.perf_counter()
            if response:
                await update.message.reply_text(response)

        t_sent = time.perf_counter()
        total_ms = (t_sent - t_received) * 1000
        llm_ms = (t_apos_llm - t_received) * 1000
        envio_ms = (t_sent - t_apos_llm) * 1000

        logger.info(
            "=== [PERF] on_message: recebido=%.6f  gateway=%.1fms  llm=%.1fms  envio=%.1fms  total=%.0fms ===",
            t_received, (t_gateway_start - t_received) * 1000, llm_ms, envio_ms, total_ms,
        )

        self.persistence.log_execution(
            user_id=user_id,
            agent=agent_name or "unknown",
            duration_ms=int(total_ms),
        )
        self.persistence.record_message_metric(
            agent_name=agent_name or "unknown",
            success=True,
            duration_ms=int(total_ms),
        )

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
        elif self.agent_registry:
            await update.message.reply_text(
                "Modo: automatico\n"
                "O roteamento usa o IntentRouter + LLM para escolher o agente.\n"
                "Use /agents para ver a equipe completa.\n"
                "Use /use <nome> para fixar um agente manualmente."
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
        elif self.agent_registry:
            lines = ["*Agentes Disponiveis*", ""]
            for a in self.agent_registry.all():
                lines.append(f"  {a.name} — {a.description}")
            lines.append("")
            lines.append(f"Total: {len(self.agent_registry.all())} agentes")
            await update.message.reply_text("\n".join(lines))
        else:
            await update.message.reply_text(
                "Nenhum agente registado."
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
        elif self.agent_registry:
            if nome in ("auto", "automatico", "automatic"):
                await update.message.reply_text(
                    "Modo automatico ja esta ativo por padrao.\n"
                    "Use /agent para ver o agente ativo.")
            elif self.agent_registry.get(nome):
                await update.message.reply_text(
                    f"Modo fixo nao disponivel sem AgentOrchestrator.\n"
                    f"Use /agents para ver a equipe.\n"
                    f"O roteamento continuara sendo automatico via IntentRouter.")
            else:
                await update.message.reply_text(
                    f"Agente '{nome}' nao encontrado.\n"
                    f"Use /agents para ver os agentes disponiveis.")
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
    # Confirmacao humana
    # ------------------------------------------------------------------

    async def _on_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        args = context.args or []
        if not args:
            await update.message.reply_text(
                "Uso: /approve <id_da_confirmacao>\n"
                "Use /confirmations para ver as confirmacoes pendentes."
            )
            return

        confirmation_id = args[0]
        user_id = str(update.effective_user.id)
        success, status, entry = self.confirmation_gateway.approve_confirmation(
            confirmation_id, user_id,
        )

        if success:
            await update.message.reply_text(
                f"✅ Confirmacao aprovada: `{confirmation_id}`",
                parse_mode="Markdown",
            )
            self.persistence.record_confirmation_metric(
                user_id, "approve", entry.step_name if entry else confirmation_id,
            )
        elif status == "already_approved":
            await update.message.reply_text("Essa confirmacao ja foi aprovada.")
        elif status == "already_rejected":
            await update.message.reply_text("Essa confirmacao ja foi rejeitada.")
        elif status == "already_expired":
            await update.message.reply_text("Essa confirmacao ja expirou.")
        elif status == "expired":
            await update.message.reply_text("⏰ Essa confirmacao expirou.")
        elif status == "confirmation_not_found":
            await update.message.reply_text(
                f"Confirmacao '{confirmation_id}' nao encontrada.",
            )
        elif status == "unauthorized":
            await update.message.reply_text(
                "Voce nao tem permissao para aprovar essa confirmacao.",
            )
        else:
            await update.message.reply_text(
                f"Nao foi possivel aprovar: {status}",
            )

    async def _on_reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        args = context.args or []
        if not args:
            await update.message.reply_text(
                "Uso: /reject <id_da_confirmacao>\n"
                "Use /confirmations para ver as confirmacoes pendentes."
            )
            return

        confirmation_id = args[0]
        user_id = str(update.effective_user.id)
        success, status, entry = self.confirmation_gateway.reject_confirmation(
            confirmation_id, user_id,
        )

        if success:
            await update.message.reply_text(
                f"❌ Confirmacao rejeitada: `{confirmation_id}`",
                parse_mode="Markdown",
            )
            self.persistence.record_confirmation_metric(
                user_id, "reject", entry.step_name if entry else confirmation_id,
            )
        elif status == "already_approved":
            await update.message.reply_text("Essa confirmacao ja foi aprovada.")
        elif status == "already_rejected":
            await update.message.reply_text("Essa confirmacao ja foi rejeitada.")
        elif status == "expired":
            await update.message.reply_text("⏰ Essa confirmacao expirou.")
        elif status == "confirmation_not_found":
            await update.message.reply_text(
                f"Confirmacao '{confirmation_id}' nao encontrada.",
            )
        elif status == "unauthorized":
            await update.message.reply_text(
                "Voce nao tem permissao para rejeitar essa confirmacao.",
            )
        else:
            await update.message.reply_text(
                f"Nao foi possivel rejeitar: {status}",
            )

    async def _on_confirmations(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = str(update.effective_user.id)
        pending = self.confirmation_gateway.get_user_pending_confirmations(user_id)
        if not pending:
            await update.message.reply_text(
                "Nenhuma confirmacao pendente.",
            )
            return

        lines = ["*Confirmacoes Pendentes:*", ""]
        for p in pending:
            lines.append(f"• `{p.confirmation_id}`")
            lines.append(f"  Ação: {p.step_name}")
            lines.append(f"  Criado: {p.created_at.strftime('%H:%M')}")
            lines.append("")
        lines.append("Use /approve <id> ou /reject <id> para responder.")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _on_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = str(query.from_user.id)
        callback_data = query.data

        success, status, entry = self.confirmation_gateway.handle_callback(
            user_id, callback_data,
        )

        if success:
            if status == "approved":
                await query.edit_message_text(
                    text=f"✅ Confirmacao aprovada: `{entry.confirmation_id}`",
                    parse_mode="Markdown",
                )
                self.persistence.record_confirmation_metric(
                    user_id, "approve", entry.step_name,
                )
            elif status == "rejected":
                await query.edit_message_text(
                    text=f"❌ Confirmacao rejeitada: `{entry.confirmation_id}`",
                    parse_mode="Markdown",
                )
                self.persistence.record_confirmation_metric(
                    user_id, "reject", entry.step_name,
                )
        else:
            if status == "already_approved":
                await query.edit_message_text("Essa confirmacao ja foi aprovada.")
            elif status == "already_rejected":
                await query.edit_message_text("Essa confirmacao ja foi rejeitada.")
            elif status == "already_expired":
                await query.edit_message_text("Essa confirmacao ja expirou.")
            elif status == "unauthorized":
                await query.answer("Voce nao tem permissao.", show_alert=True)
            elif status == "confirmation_not_found":
                await query.edit_message_text("Confirmacao nao encontrada.")
            else:
                await query.edit_message_text(f"Erro: {status}")

    # ------------------------------------------------------------------
    # CEO Mode
    # ------------------------------------------------------------------

    async def _on_ceo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/ceo <objetivo> — transforma um objetivo grande em plano executavel."""
        if not self.ceo_mode:
            await update.message.reply_text("O CEO Mode nao esta ativo neste build.")
            return
        user_id = str(update.effective_user.id)
        args = context.args or []
        if not args:
            await update.message.reply_text(
                "Uso: /ceo <objetivo>\n\n"
                "Exemplos:\n"
                "  /ceo Quero lancar o ScalaFlow\n"
                "  /ceo Quero vender 500 chaveiros em Portugal\n"
                "  /ceo Quero criar um SaaS para imobiliarias"
            )
            return
        objetivo = " ".join(args)
        await update.message.chat.send_action(ChatAction.TYPING)
        try:
            plano = await asyncio.to_thread(self.ceo_mode.executar, objetivo, user_id)
        except Exception as exc:
            logger.exception("CEO Mode falhou")
            await update.message.reply_text(f"Falha ao criar o plano: {exc}")
            return

        sensiveis = plano.get("confirmacoes_necessarias", [])
        linhas = [
            f"*CEO Mode — Plano criado*\n",
            f"*Objetivo:* {plano['objetivo']}",
            f"*Tipo:* {plano['tipo']} | *Projeto:* {plano['projeto']}",
            f"*Plano:* {plano['plano']}",
            "",
            "*Fases:*",
        ]
        for f in plano.get("fases", []):
            linhas.append(f"  {f['nome']}")
        linhas.append("")
        linhas.append("*Tarefas criadas:*")
        for t in plano.get("tarefas", []):
            if t.get("tarefa_id"):
                sens = " ⚠️ sensivel" if t.get("sensivel") else ""
                linhas.append(f"  - [{t['prioridade'].upper()}] {t['titulo']} → {t['agente']}{sens}")
        linhas.append("")
        linhas.append(f"*Riscos:*")
        for r in plano.get("riscos", []):
            linhas.append(f"  - {r}")
        linhas.append("")
        linhas.append(f"*Proxima acao:* {plano['proxima_acao']}")
        if sensiveis:
            linhas.append("")
            linhas.append("⚠️ Acoes sensiveis aguardando confirmacao:")
            for s in sensiveis:
                linhas.append(f"  - {s['titulo']}")

        await update.message.reply_text("\n".join(linhas), parse_mode="Markdown")

    # ------------------------------------------------------------------
    # Prospector (Máquina de Leads)
    # ------------------------------------------------------------------

    async def _on_prospector_prospectar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/prospectar <nicho> em <cidade> — busca novos leads."""
        from services.prospector.service import get_prospector_service

        args = context.args or []
        texto = " ".join(args).strip()
        if " em " not in texto.lower():
            await update.message.reply_text(
                "Uso: /prospectar <nicho> em <cidade>\n"
                "Exemplo: /prospectar impressao 3d em Lisboa"
            )
            return
        nicho, cidade = texto.split(" em ", 1)
        await update.message.chat.send_action(ChatAction.TYPING)
        try:
            res = await asyncio.to_thread(
                get_prospector_service().prospectar, nicho.strip(), cidade.strip(),
            )
        except Exception as exc:
            logger.exception("Prospector falhou")
            await update.message.reply_text(f"Falha na busca de leads: {exc}")
            return
        modo = "simulacao" if res.get("simular") else "real"
        base = f"*Prospecção ({modo})* — {res.get('saida') or res.get('erro', '')}"
        if res.get("leads_sincronizados"):
            base += f"\n\nLeads sincronizados: {res['leads_sincronizados']}"
        await update.message.reply_text(base, parse_mode="Markdown")

    async def _on_prospector_slug(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                  acao: str) -> None:
        from services.prospector.service import get_prospector_service

        args = context.args or []
        if not args:
            await update.message.reply_text(f"Uso: /{acao} <slug_do_lead>")
            return
        slug = args[0]
        await update.message.chat.send_action(ChatAction.TYPING)
        try:
            res = await asyncio.to_thread(
                getattr(get_prospector_service(), acao), slug,
            )
        except Exception as exc:
            logger.exception("Prospector %s falhou", acao)
            await update.message.reply_text(f"Falha em /{acao}: {exc}")
            return
        await update.message.reply_text(
            res.get("mensagem") or res.get("erro", ""), parse_mode="Markdown",
        )

    async def _on_prospector_followup(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/followup — roda os follow-ups de leads sem resposta."""
        from services.prospector.service import get_prospector_service

        await update.message.chat.send_action(ChatAction.TYPING)
        try:
            res = await asyncio.to_thread(get_prospector_service().followups)
        except Exception as exc:
            logger.exception("Prospector followup falhou")
            await update.message.reply_text(f"Falha no follow-up: {exc}")
            return
        await update.message.reply_text(
            res.get("mensagem") or res.get("erro", ""), parse_mode="Markdown",
        )

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
        app.add_handler(CommandHandler("approve", self._on_approve))
        app.add_handler(CommandHandler("reject", self._on_reject))
        app.add_handler(CommandHandler("confirmations", self._on_confirmations))
        app.add_handler(CommandHandler("forget", self._on_forget))
        app.add_handler(CommandHandler("cancel", self._on_cancel))
        app.add_handler(CommandHandler("memory", self._on_memory_stats))
        app.add_handler(CommandHandler("ceo", self._on_ceo))
        app.add_handler(CommandHandler("prospectar", self._on_prospector_prospectar))
        app.add_handler(CommandHandler("proposta",
            lambda u, c: self._on_prospector_slug(u, c, "proposta")))
        app.add_handler(CommandHandler("redesenhar",
            lambda u, c: self._on_prospector_slug(u, c, "redesenhar")))
        app.add_handler(CommandHandler("publicar",
            lambda u, c: self._on_prospector_slug(u, c, "publicar")))
        app.add_handler(CommandHandler("contrato",
            lambda u, c: self._on_prospector_slug(u, c, "contrato")))
        app.add_handler(CommandHandler("followup", self._on_prospector_followup))
        app.add_handler(CallbackQueryHandler(self._on_callback_query))
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
