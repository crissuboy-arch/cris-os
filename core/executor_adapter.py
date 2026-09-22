"""
Executor Adapter -- interface comum que QUALQUER executor especializado
(PageForge, Pink Logic, Criador-de-App, ForgeHub, NEXORA) implementa para
receber trabalho do Cris OS.

PAGEFORGE tem um adapter REAL (`core/pageforge_adapter.py:PageForgeAdapter`)
-- os demais continuam no stub seguro (`AdapterNaoConectado`), que PROVA a
forma do contrato sem nunca fingir produção concluída. NADA neste módulo
(nem em nenhum outro) chama `.dispatch()` automaticamente -- é preciso um
chamador explícito para qualquer envio real acontecer.

Quando um NOVO executor real for conectado:
  1. Implementar `ExecutorAdapter` para aquele executor específico.
  2. Registrar em `EXECUTOR_REGISTRY[<executor_type>]`.
  3. `core/production_orders.py` (ou quem despachar) passa a encontrar um
     adapter real em vez do stub -- nenhuma mudança de contrato necessária.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.pageforge_adapter import PageForgeAdapter
from memory.project_brain import ProductionWorkOrder


@runtime_checkable
class ExecutorAdapter(Protocol):
    """Contrato que todo executor especializado deve implementar."""

    def can_handle(self, work_order: ProductionWorkOrder) -> bool:
        """True se este adapter sabe processar `work_order.executor_type`."""
        ...

    def dispatch(self, work_order: ProductionWorkOrder) -> ProductionWorkOrder:
        """Envia a WorkOrder para o executor real. Só um adapter REAL pode
        avançar `status` para `DISPATCHED` -- nunca o stub."""
        ...

    def get_status(self, work_order: ProductionWorkOrder) -> str:
        """Consulta o status atual no executor (não usado enquanto nenhum
        adapter real existir)."""
        ...

    def collect_result(self, work_order: ProductionWorkOrder) -> ProductionWorkOrder:
        """Recolhe o resultado (`output_refs`) quando o executor concluir --
        só marca `COMPLETED` quando há evidência/output real correspondente
        (nunca conclusão sem artefato quando o contrato exige um)."""
        ...


class AdapterNaoConectado:
    """
    Stub seguro (Seção 7 da missão) -- prova a forma do `ExecutorAdapter`
    sem NUNCA fingir produção concluída. `can_handle` sempre responde True
    (aceita classificar qualquer executor_type conhecido), mas `dispatch`
    NUNCA avança o status da WorkOrder -- devolve exatamente a mesma
    WorkOrder, inalterada, porque não há nenhum executor real do outro lado
    para receber o trabalho.
    """

    def can_handle(self, work_order: ProductionWorkOrder) -> bool:
        return True

    def dispatch(self, work_order: ProductionWorkOrder) -> ProductionWorkOrder:
        # NUNCA marca DISPATCHED -- nenhum executor real recebeu isto.
        return work_order

    def get_status(self, work_order: ProductionWorkOrder) -> str:
        return work_order.status

    def collect_result(self, work_order: ProductionWorkOrder) -> ProductionWorkOrder:
        # Nunca inventa um resultado -- sem executor real, não há o que coletar.
        return work_order


# PAGEFORGE agora tem um adapter REAL (`core/pageforge_adapter.py`) -- mas
# ele próprio se recusa a despachar sem `PAGEFORGE_BRIDGE_TOKEN` configurado
# (nunca chama sem autenticação, nunca finge sucesso). NADA no resto do
# Cris OS chama `.dispatch()` automaticamente -- é preciso um chamador
# explícito (fora desta missão) para o primeiro envio real acontecer. Os
# demais executores continuam no stub seguro até terem seu próprio adapter
# real conectado -- ver PINK_LOGIC (intencionalmente não tocado nesta missão).
EXECUTOR_REGISTRY: dict[str, ExecutorAdapter] = {
    "APP_BUILDER": AdapterNaoConectado(),
    "PAGEFORGE": PageForgeAdapter(),
    "PINK_LOGIC": AdapterNaoConectado(),
    "FORGEHUB": AdapterNaoConectado(),
    "NEXORA": AdapterNaoConectado(),
}


def obter_adapter(executor_type: str) -> ExecutorAdapter | None:
    """Devolve o adapter registrado para este `executor_type`, ou `None`
    quando não há nenhum (ex.: `NEEDS_ROUTING`) -- nunca um adapter padrão
    genérico que finja saber processar qualquer coisa."""
    return EXECUTOR_REGISTRY.get(executor_type)
