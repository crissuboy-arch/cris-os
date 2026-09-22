"""
ScalaFlow Bridge -- a ORQUESTRACAO que faltava entre componentes JA
existentes (Fases 6-9), pedida explicitamente para fechar o caminho:

    MarketIntelligenceHandoff -> projeto -> BusinessPlan -> PendingApproval
    -> Telegram -> aprovacao/rejeicao -> ExecutionPlan -> Tasks

NAO reimplementa nenhum componente: reaproveita `core/product_architect.py`
(Fase 3), `core/business_builder.py` (Fase 4/7), `memory/project_brain.py`
(`PendingApprovalStore`, Fase 6) e `core/execution_engine.py` (Fase 8) --
este modulo so os conecta na ordem certa, com deteccao de idempotencia em
cada etapa (nunca duplica project/BusinessPlan/PendingApproval/notificacao).

DECISAO ARQUITETURAL -- UM UNICO GATE HUMANO (nao tres): o caminho "organico"
de mineracao (Opportunity Analyst -> Decision Engine -> Product Architect ->
aprovacao -> Business Builder -> aprovacao) tem varios gates humanos
sequenciais porque cada um deles pode legitimamente ser REJEITADO em
separado. Para uma oportunidade que chega JA PONTUADA/VETADA pelo ScalaFlow
(a pessoa ja clicou "Transformar em Projeto" no ScalaFlow -- um sinal humano
de interesse), a aprovacao de FORMATO de produto (ProductBlueprint) e
consolidada automaticamente na aprovacao do BusinessPlan: este modulo gera o
blueprint via `core.product_architect.propor_produto` (reaproveitado, nao
reimplementado) e, se houver QUALQUER candidato plausivel, promove o
melhor para `recommended_product_type` e marca `decision_status="APPROVED"`
diretamente -- documentado aqui, nunca escondido. O UNICO gate humano real
desta integracao e a aprovacao do BusinessPlan (via
`core/approval_router.py`, ja existente, sem alteracao de contrato).

FAIL CLOSED: se nao houver NENHUMA evidencia (nem candidato algum), este
modulo NUNCA fabrica um BusinessPlan vazio nem cria uma aprovacao pendente
vazia -- registra a lacuna e para, honestamente.

PONTO DE EXTENSAO FUTURO (Secao 9 da missao -- "Jev", NAO instalado aqui):
a decisao "este handoff tem evidencia suficiente para avancar automaticamente
ou precisa de mais investigacao" (`_construir_blueprint_consolidado` abaixo)
e hoje pura logica Python (reaproveitando o Product Architect). Um futuro
"Decision Gate" poderia interceptar `avancar_projeto`/
`avancar_a_partir_do_handoff` ANTES da chamada a `propor_produto` para
decisoes rapidas estruturadas (Jev yes/pick/score/run) -- as duas funcoes
publicas deste modulo (recebem `ProjectBrain`/`handoff_id` e devolvem um
dict de resultado padronizado) foram desenhadas para isso ser um `if` a
mais aqui dentro no futuro, nunca uma reescrita. Nada de Jev existe ou e
chamado nesta fase.
"""

from __future__ import annotations

import logging

from config.settings import settings
from core.business_builder import construir_plano_negocio
from core.product_architect import promover_candidato_para_blueprint, propor_produto
from memory.project_brain import BusinessPlan, ProductBlueprint, ProjectBrain

logger = logging.getLogger(__name__)


def sessao_cris() -> str:
    """Sessao Telegram canonica da unica usuaria do CRIS OS -- mesma
    convencao ja usada em `channels/telegram/bot.py`/`tools/opportunity_tools.py`
    (`f"telegram:{user_id}"`). Reaproveitada aqui porque a aprovacao/
    notificacao desta integracao SEMPRE se refere a mesma pessoa (nao ha
    multiusuario neste CRIS OS)."""
    return f"telegram:{settings.TELEGRAM_ALLOWED_USER_ID}"


# ---------------------------------------------------------------------------
# Etapa 1 -- Blueprint consolidado (reaproveita Product Architect, Fase 3)
# ---------------------------------------------------------------------------

def _construir_blueprint_consolidado(brain: ProjectBrain, llm=None) -> ProductBlueprint | None:
    """
    Devolve um `ProductBlueprint` PRONTO para o Business Builder consumir
    (`esta_aprovado() == True`), ou `None` quando genuinamente nao ha
    evidencia nenhuma para sequer levantar uma hipotese de formato (fail
    closed -- nunca inventa).

    Idempotente: se `brain.blueprint` ja esta aprovado (de uma chamada
    anterior desta mesma ponte, ou de uma aprovacao manual via Product
    Architect), devolve-o sem regenerar (evita gastar IA de novo e
    preserva uma decisao humana ja tomada).
    """
    if brain.blueprint and brain.blueprint.esta_aprovado():
        return brain.blueprint

    blueprint = propor_produto(brain, llm=llm)

    if not blueprint.recommended_product_type and blueprint.candidates:
        # Ponte ScalaFlow (ver docstring do modulo): sem uma recomendacao
        # confiante do proprio Product Architect, promove o candidato mais
        # forte (primeiro da lista -- ja ordenado por plausibilidade pelo
        # LLM/fallback) em vez de bloquear a integracao inteira esperando
        # uma segunda rodada de aprovacao de formato que esta integracao
        # deliberadamente nao usa.
        melhor = blueprint.candidates[0]
        promover_candidato_para_blueprint(blueprint, melhor)
        blueprint.recommended_product_type = melhor["product_type"]
        blueprint.alternative_product_types = [
            c["product_type"] for c in blueprint.candidates[1:]
        ]

    if not blueprint.recommended_product_type:
        return None  # nem headline/copy/nicho/score real -- nada para propor

    blueprint.decision_status = "APPROVED"
    nota = (
        " [Formato consolidado automaticamente pela integração ScalaFlow -- "
        "o gate de aprovação humana desta integração é o Plano de Negócio, "
        "não este blueprint intermediário. Ver core/scalaflow_bridge.py.]"
    )
    blueprint.reasoning_summary = (blueprint.reasoning_summary or "") + nota
    return blueprint


# ---------------------------------------------------------------------------
# Etapa 2 -- BusinessPlan + PendingApproval + notificacao (idempotente)
# ---------------------------------------------------------------------------

def _formatar_notificacao(brain: ProjectBrain, bp: BusinessPlan, handoff_id: str | None) -> str:
    linhas = [
        "NOVO PROJETO PARA APROVAÇÃO",
        "",
        f"{brain.identidade.name}",
        "Origem: ScalaFlow" + (f" / {brain.market_intelligence[-1].platform}" if brain.market_intelligence and brain.market_intelligence[-1].platform else ""),
    ]
    score = brain.oportunidade.score
    if score is not None:
        linhas.append(f"Score: {score}")
    linhas.append("")
    if bp.value_proposition:
        linhas.append(f"Proposta de valor: {bp.value_proposition}")
    if bp.main_offer:
        linhas.append(f"Oferta: {bp.main_offer}")
    if bp.target_audience:
        linhas.append(f"Público-alvo: {bp.target_audience}")
    if bp.price:
        etiqueta = " (hipótese, sem benchmark real)" if bp.price_is_hypothesis else ""
        linhas.append(f"Preço: {bp.price}{etiqueta}")
    if bp.missing_evidence:
        linhas.append("")
        linhas.append("Pendências (evidência ausente): " + "; ".join(bp.missing_evidence))
    linhas.append("")
    linhas.append(f"Projeto: {brain.project_id}")
    if handoff_id:
        linhas.append(f"Handoff: {handoff_id}")
    linhas.append("")
    linhas.append(
        'Responda "Aprovado" para aprovar este plano de negócio, ou '
        '"Rejeito" para descartar -- nenhum conteúdo/ativo/campanha é '
        "criado automaticamente."
    )
    return "\n".join(linhas)


def avancar_projeto(
    brain: ProjectBrain,
    brain_store,
    pending_store,
    session: str | None = None,
    llm_blueprint=None,
    llm_business=None,
    notificar: bool = True,
    focus_store=None,
) -> dict:
    """
    Detecta a PRIMEIRA etapa ausente para este projeto e avança dali --
    nunca recria o que já existe (idempotente por construção, seguro para
    restart/retry/chamada repetida).

    CORREÇÃO DE BUG REAL (contexto Telegram perdido): esta função é sempre
    chamada com um `project_id`/`handoff_id` EXPLÍCITO (nunca por adivinhação
    -- ver `avancar_a_partir_do_handoff`), então invocá-la é, por definição,
    a "troca EXPLÍCITA de projeto pela usuária" que o resto do sistema
    (`tools/execution_engine_tools.py`, `tools/business_builder_tools.py`,
    `tools/market_intelligence_tools.py`, ...) já respeita via
    `UserFocusStore`/`get_foco_atual` (Fase 3). Por isso, ANTES de qualquer
    outra coisa, esta função atualiza o foco da sessão para este projeto --
    sem isso, uma pendência/BusinessPlan criado aqui existe corretamente no
    Project Brain, mas qualquer comando genérico subsequente ("execute o
    plano", "mostre o plano de negócio", "status") continuava resolvendo o
    ÚLTIMO projeto focado pelo fluxo orgânico antigo (Opportunity Analyst/
    Product Architect), nunca o projeto vindo do ScalaFlow -- bug real
    observado em produção (ver commit que introduziu esta correção).

    Devolve um dict `{status, project_id, handoff_id, message}` --
    `status` é um de:
      - "NEEDS_MORE_EVIDENCE": sem evidência nenhuma para propor um
        formato de produto -- nada foi criado.
      - "PENDING_APPROVAL_ALREADY_SET": já existe uma aprovação pendente
        para este projeto (não duplicou nada).
      - "PENDING_APPROVAL_BLOCKED_BY_OTHER": já existe uma aprovação
        pendente para OUTRO projeto na mesma sessão -- nunca sobrescreve
        às cegas (mesmo princípio de `core/approval_router.py`).
      - "PENDING_APPROVAL_CREATED": BusinessPlan criado, aprovação
        pendente registrada, notificação enviada (se `notificar=True`).
      - "ALREADY_APPROVED": o BusinessPlan já foi aprovado/rejeitado
        anteriormente -- nada a fazer aqui (ver `core/approval_router.py`
        para o que acontece depois da aprovação).
    """
    session = session or sessao_cris()
    if focus_store is None:
        from memory.project_brain import UserFocusStore

        focus_store = UserFocusStore(brain_store.project_memory)
    focus_store.set_focus(session, brain.project_id)

    handoff_id = brain.market_intelligence[-1].handoff_id if brain.market_intelligence else None

    if brain.business_plan and brain.business_plan.approval_status in {"APPROVED", "REJECTED"}:
        return {
            "status": "ALREADY_APPROVED",
            "project_id": brain.project_id,
            "handoff_id": handoff_id,
            "message": (
                f"O plano de negócio deste projeto já foi "
                f"{'aprovado' if brain.business_plan.approval_status == 'APPROVED' else 'rejeitado'} "
                f"anteriormente (status: {brain.business_plan.approval_status})."
            ),
        }

    if not brain.business_plan:
        blueprint = _construir_blueprint_consolidado(brain, llm=llm_blueprint)
        if blueprint is None:
            brain.registrar_run(
                "scalaflow_bridge",
                "Evidência insuficiente para propor um formato de produto -- "
                "handoff sem headline/copy/nicho/score aproveitável.",
            )
            brain_store.save(brain)
            return {
                "status": "NEEDS_MORE_EVIDENCE",
                "project_id": brain.project_id,
                "handoff_id": handoff_id,
                "message": (
                    "Este handoff não tem evidência suficiente (headline, copy, "
                    "nicho ou score) para propor um formato de produto -- nenhum "
                    "plano de negócio foi criado."
                ),
            }
        brain.blueprint = blueprint
        brain.registrar_run(
            "scalaflow_bridge",
            f"Formato consolidado via integração ScalaFlow: '{blueprint.recommended_product_type}'.",
        )

        plano = construir_plano_negocio(brain, llm=llm_business)
        brain.business_plan = plano
        brain.registrar_run(
            "scalaflow_bridge",
            f"Plano de negócio montado para '{blueprint.recommended_product_type}' via integração ScalaFlow.",
        )
        brain_store.save(brain)
    else:
        plano = brain.business_plan  # já existe em DRAFT/READY_FOR_REVIEW/READY_FOR_APPROVAL

    if plano.approval_status != "READY_FOR_APPROVAL":
        # Estado intermediário incomum (ex.: DRAFT sem nunca ter sido
        # sincronizado) -- nunca força um estado que o próprio Business
        # Builder não produziu.
        return {
            "status": "BUSINESS_PLAN_NOT_READY",
            "project_id": brain.project_id,
            "handoff_id": handoff_id,
            "message": f"Plano de negócio existe, mas está em status '{plano.approval_status}' (não pronto para aprovação).",
        }

    pendente_atual = pending_store.get_pending(session)
    if pendente_atual:
        if pendente_atual.get("project_id") == brain.project_id and pendente_atual.get("artifact_type") == "BUSINESS_PLAN":
            return {
                "status": "PENDING_APPROVAL_ALREADY_SET",
                "project_id": brain.project_id,
                "handoff_id": handoff_id,
                "message": "Já existe uma aprovação pendente para o plano de negócio deste projeto -- nada foi duplicado.",
            }
        if pendente_atual.get("project_id") != brain.project_id:
            return {
                "status": "PENDING_APPROVAL_BLOCKED_BY_OTHER",
                "project_id": brain.project_id,
                "handoff_id": handoff_id,
                "message": (
                    f"Já existe uma aprovação pendente de outro projeto "
                    f"({pendente_atual.get('project_id')}) nesta sessão -- "
                    "resolva-a antes (aprove/rejeite) para não perder o contexto."
                ),
            }

    pending_store.set_pending(session, brain.project_id, "BUSINESS_PLAN", "APPROVE", handoff_id=handoff_id)

    notificado = False
    if notificar:
        try:
            from channels.telegram.bot import enviar_mensagem_proativa

            notificado = enviar_mensagem_proativa(_formatar_notificacao(brain, plano, handoff_id))
        except Exception as exc:  # nunca deixa a orquestracao quebrar por falha de rede/Telegram
            logger.warning("=== [SCALAFLOW_BRIDGE] Falha ao enviar notificação Telegram: %s ===", exc)

    return {
        "status": "PENDING_APPROVAL_CREATED",
        "project_id": brain.project_id,
        "handoff_id": handoff_id,
        "notificado": notificado,
        "message": "Plano de negócio criado e aprovação pendente registrada.",
    }


def avancar_a_partir_do_handoff(
    handoff_id: str,
    brain_store,
    handoff_store,
    pending_store,
    session: str | None = None,
    llm_blueprint=None,
    llm_business=None,
    notificar: bool = True,
    focus_store=None,
) -> dict:
    """
    Ponto de entrada do mecanismo de RESUME/ADVANCE (Seção 5 da missão):
    dado um `handoff_id` JÁ persistido (nunca cria/reenvia um handoff novo),
    localiza o projeto associado e chama `avancar_projeto`. Usado tanto
    para handoffs recém-chegados quanto para retomar um projeto cujo
    handoff já foi processado antes (ex.: depois de um restart, ou quando
    o botão de origem no ScalaFlow já está SENT/desabilitado).
    """
    indice = handoff_store.buscar(handoff_id)
    if not indice or not indice.get("project_id"):
        return {
            "status": "HANDOFF_NOT_FOUND",
            "project_id": None,
            "handoff_id": handoff_id,
            "message": f"Nenhum handoff persistido encontrado com id '{handoff_id}'.",
        }

    brain = brain_store.load(indice["project_id"])
    if not brain:
        return {
            "status": "PROJECT_NOT_FOUND",
            "project_id": indice["project_id"],
            "handoff_id": handoff_id,
            "message": f"O handoff existe, mas o projeto '{indice['project_id']}' não foi encontrado.",
        }

    return avancar_projeto(
        brain, brain_store, pending_store, session=session,
        llm_blueprint=llm_blueprint, llm_business=llm_business, notificar=notificar,
        focus_store=focus_store,
    )


# ---------------------------------------------------------------------------
# Status (Seção 6 da missão) -- fonte única, consumida pela rota HTTP
# `GET /api/integrations/scalaflow/intelligence/{handoff_id}/status`.
# Só leitura -- nunca cria/altera nada.
# ---------------------------------------------------------------------------

def montar_status(handoff_id: str, brain_store, handoff_store, pending_store, session: str | None = None) -> dict | None:
    """Devolve um snapshot JSON-serializável do estado deste handoff/projeto,
    ou `None` se o `handoff_id` não existir. NUNCA inclui segredo/token."""
    session = session or sessao_cris()

    indice = handoff_store.buscar(handoff_id)
    if not indice or not indice.get("project_id"):
        return None

    brain = brain_store.load(indice["project_id"])
    if not brain:
        return {
            "handoff_id": handoff_id,
            "project_id": indice["project_id"],
            "project_name": None,
            "project_status": None,
            "business_plan": {"id": None, "status": None},
            "approval": {"artifact_type": None, "status": "NONE"},
            "execution_plan": {"id": None, "status": None},
            "tasks": {"total": 0, "pending": 0, "running": 0, "completed": 0, "failed": 0},
            "last_error": "Projeto referenciado pelo handoff não foi encontrado no Project Brain.",
            "updated_at": indice.get("registered_at"),
        }

    bp = brain.business_plan
    business_plan_info = {
        "id": f"bizplan:{brain.project_id}:v{bp.version}" if bp else None,
        "status": bp.approval_status if bp else None,
    }

    pendente = pending_store.get_pending(session)
    if pendente and pendente.get("project_id") == brain.project_id:
        approval_info = {"artifact_type": pendente.get("artifact_type"), "status": "PENDING"}
    else:
        approval_info = {"artifact_type": None, "status": "NONE"}

    plano = brain.execution_plan
    if plano:
        resumo = plano.resumo()
        execution_plan_info = {"id": plano.execution_id, "status": plano.status}
        tasks_info = {
            "total": resumo["total_tasks"],
            "pending": resumo["pending_tasks"],
            "running": resumo["running_tasks"],
            "completed": resumo["completed_tasks"],
            "failed": resumo["failed_tasks"],
        }
        erro_task = next((t.error for t in plano.tasks if t.status in {"FAILED", "BLOCKED"} and t.error), None)
    else:
        execution_plan_info = {"id": None, "status": None}
        tasks_info = {"total": 0, "pending": 0, "running": 0, "completed": 0, "failed": 0}
        erro_task = None

    return {
        "handoff_id": handoff_id,
        "project_id": brain.project_id,
        "project_name": brain.identidade.name,
        "project_status": brain.identidade.status,
        "business_plan": business_plan_info,
        "approval": approval_info,
        "execution_plan": execution_plan_info,
        "tasks": tasks_info,
        "last_error": erro_task,
        "updated_at": brain.identidade.updated_at,
    }
