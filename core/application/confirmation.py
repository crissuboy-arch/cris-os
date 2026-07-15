"""
ConfirmationGate — proteção humana antes de ações externas/destrutivas.

Regra do CRIS OS: **read-only por padrão; ação externa só com confirmação da Cris**
(rules/never.md · CLAUDE.md). Este gate, consultado pelo ExecutionDispatcher antes
de executar cada passo:

  - passa direto tudo que é `Effect.READ_ONLY` (leitura/consulta);
  - BLOQUEIA `Effect.SENSITIVE` (write/delete/publish/buy/send externo) enquanto a
    Cris não confirmar (`DispatchContext.confirmed`), devolvendo um ExecutionResult
    que PEDE a confirmação — sem executar o alvo.

Implementação MÍNIMA (Bloco 6): apenas bloqueia e pede confirmação. O pause/resume
completo com estado persistido é de uma fase futura; o mecanismo de confirmação já
existe (o flag `confirmed`) para ligar o "confirmar" da Cris quando houver ação de
escrita real (ex.: Browser do Bloco 7).
"""

from __future__ import annotations

from core.domain.execution import Effect
from core.models import ExecutionResult


class ConfirmationGate:
    """Bloqueia passos sensíveis não confirmados; libera read-only e já confirmados."""

    def check(self, step, ctx) -> "ExecutionResult | None":
        """None = liberado para executar. ExecutionResult = bloqueado (pede confirmação)."""
        sensivel = getattr(step, "effect", Effect.READ_ONLY) == Effect.SENSITIVE
        if sensivel and not getattr(ctx, "confirmed", False):
            return ExecutionResult(
                source=step.name, type=step.type, success=False,
                output=(f"⚠️ A ação '{step.name}' altera algo externo e precisa da sua "
                        f"confirmação. Responda 'confirmar' para eu prosseguir."),
                error="confirmation_required",
                data={"confirmation_required": True, "step": step.name, "effect": str(Effect.SENSITIVE)},
            )
        return None
