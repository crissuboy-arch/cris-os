"""
Performance Agent -- fundação (Fase 6): LÊ métricas REAIS/IMPORTADAS de uma
campanha quando elas existirem, NUNCA inventa.

REGRA MAIS IMPORTANTE: sem nenhum `PerformanceSnapshot` REAL/IMPORTED
registrado para o projeto, a resposta é SEMPRE determinística ("ainda não
existem métricas suficientes") -- nenhum LLM é chamado só pra produzir esse
aviso (ver `tem_metricas_utilizaveis`, checado ANTES de qualquer chamada de
LLM em `tools/performance_agent_tools.py`).

Quando existe snapshot utilizável, o diagnóstico separa FATOS (os números
exatos do snapshot, nunca alterados) de HIPÓTESES (possíveis causas -- nunca
afirmadas como causalidade comprovada). SIMULATED nunca é tratado como
utilizável para diagnóstico real -- existe só para cenários de teste.
"""

from __future__ import annotations

import json
import logging
import re

from core.evidence_guard import sanitizar_claims_herdadas
from memory.project_brain import PerformanceSnapshot, ProjectBrain

logger = logging.getLogger(__name__)

# REAL/IMPORTED sao as UNICAS fontes utilizaveis para diagnostico --
# SIMULATED nunca e apresentado como se fosse dado real (nunca misturado).
_FONTES_UTILIZAVEIS = frozenset({"REAL", "IMPORTED"})

_CAMPOS_METRICA = (
    ("Investimento", "spend"), ("Impressões", "impressions"),
    ("Alcance", "reach"), ("Cliques", "clicks"),
    ("CTR", "ctr"), ("CPC", "cpc"), ("CPM", "cpm"),
    ("Leads", "leads"), ("Compras", "purchases"), ("Receita", "revenue"),
    ("CPL", "cpl"), ("CPA", "cpa"), ("CVR", "cvr"), ("ROAS", "roas"),
)


def tem_metricas_utilizaveis(brain: ProjectBrain) -> bool:
    """True se existir pelo menos 1 snapshot REAL ou IMPORTED (nunca
    SIMULATED) para este projeto."""
    return any(s.source in _FONTES_UTILIZAVEIS for s in brain.performance_snapshots)


def ultimo_snapshot_utilizavel(brain: ProjectBrain) -> PerformanceSnapshot | None:
    utilizaveis = [s for s in brain.performance_snapshots if s.source in _FONTES_UTILIZAVEIS]
    return utilizaveis[-1] if utilizaveis else None


def registrar_snapshot(brain: ProjectBrain, snapshot: PerformanceSnapshot) -> None:
    """Adiciona um snapshot novo ao histórico do projeto -- nunca substitui/
    mescla com um snapshot existente (cada coleta é seu próprio registro,
    nunca uma média/merge silenciosa entre REAL e SIMULATED)."""
    brain.performance_snapshots.append(snapshot)
    brain.identidade.updated_at = snapshot.collected_at


def _formatar_fatos(snap: PerformanceSnapshot) -> list[str]:
    linhas = []
    for nome, campo in _CAMPOS_METRICA:
        valor = getattr(snap, campo)
        linhas.append(f"  {nome}: {valor if valor is not None else 'NOT_AVAILABLE'}")
    return linhas


def _prompt_diagnostico(snap: PerformanceSnapshot) -> list[dict]:
    dados = {nome: (getattr(snap, campo) or "NOT_AVAILABLE") for nome, campo in _CAMPOS_METRICA}
    dados["platform"] = snap.platform or "NOT_AVAILABLE"
    dados["date_range"] = snap.date_range or "NOT_AVAILABLE"
    sistema = (
        "Você é o Performance Agent do CRIS OS. Recebe métricas REAIS/"
        "IMPORTADAS já coletadas de uma campanha (nunca invente nenhum "
        "número -- os valores abaixo já são fatos verificados) e comenta "
        "possíveis causas -- SEMPRE como HIPÓTESE, NUNCA como causalidade "
        "comprovada.\n\n"
        "REGRAS OBRIGATÓRIAS:\n"
        "1. NUNCA altere, arredonde ou reafirme um número diferente do que "
        "foi dado -- você só comenta, nunca recalcula métrica.\n"
        "2. Toda causa possível para um número é uma HIPÓTESE -- nunca "
        "afirme que algo É a causa, só que PODE ser.\n"
        "3. Responda SOMENTE com um JSON válido, EXATAMENTE neste formato:\n"
        '{"diagnostico": "...", "hipoteses": ["..."], "riscos": ["..."], "proximo_teste": ["..."]}'
    )
    usuario = "Métricas já coletadas (fatos, não inventar nem alterar):\n" + json.dumps(dados, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": sistema},
        {"role": "user", "content": usuario},
    ]


def _extrair_json(texto: str) -> dict | None:
    texto = texto.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip(), flags=re.MULTILINE)
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texto, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
        return None


def _lista_limpa(v) -> list[str]:
    if not v:
        return []
    itens = v if isinstance(v, list) else [v]
    return [t for t in (sanitizar_claims_herdadas(str(x).strip()) for x in itens if str(x).strip()) if t]


def diagnosticar_performance(brain: ProjectBrain, llm=None) -> str:
    """
    Só é chamada quando `tem_metricas_utilizaveis(brain)` já é True (ver
    `tools/performance_agent_tools.py`) -- nunca inventa métrica. FATOS vêm
    SEMPRE do snapshot (nunca do LLM); HIPÓTESES/DIAGNÓSTICO usam o LLM
    (tier inteligente) só para comentar os números já dados, com fallback
    determinístico e honesto se o LLM estiver indisponível.
    """
    snap = ultimo_snapshot_utilizavel(brain)
    if not snap:
        return (
            "Ainda não existem métricas reais/importadas suficientes para "
            "avaliar a performance desta campanha."
        )

    linhas = [
        "📊 DIAGNÓSTICO DE PERFORMANCE",
        "",
        f"Projeto: {brain.project_id}",
        f"Plataforma: {snap.platform or 'NOT_AVAILABLE'} | Período: {snap.date_range or 'NOT_AVAILABLE'} | Fonte: {snap.source}",
        "",
        "FATOS (dados exatos do snapshot -- nunca alterados):",
        *_formatar_fatos(snap),
        "",
    ]

    hipoteses: list[str] = []
    riscos: list[str] = []
    proximo_teste: list[str] = []
    diagnostico_texto: str | None = None

    if llm is not None:
        try:
            resposta = llm.chat(_prompt_diagnostico(snap))
            dados = _extrair_json(resposta.content or "")
            if dados:
                diagnostico_texto = sanitizar_claims_herdadas(str(dados.get("diagnostico") or "").strip()) or None
                hipoteses = _lista_limpa(dados.get("hipoteses"))
                riscos = _lista_limpa(dados.get("riscos"))
                proximo_teste = _lista_limpa(dados.get("proximo_teste"))
        except Exception as exc:
            logger.warning("=== [PERFORMANCE_AGENT] LLM falhou, usando diagnóstico determinístico: %s ===", exc)

    if diagnostico_texto:
        linhas.append(f"DIAGNÓSTICO: {diagnostico_texto}")
    else:
        linhas.append(
            "DIAGNÓSTICO: leitura estrutural dos dados acima -- nenhuma "
            "causa foi inferida automaticamente nesta chamada.",
        )
    linhas.append("")

    linhas.append("HIPÓTESES (possíveis causas -- nunca causalidade comprovada):")
    if hipoteses:
        for h in hipoteses:
            linhas.append(f"  - {h}")
    else:
        linhas.append(
            "  - Nenhuma hipótese gerada automaticamente -- qualquer causa "
            "para os números acima exige julgamento humano adicional.",
        )
    linhas.append("")

    linhas.append("RISCOS:")
    if riscos:
        for r in riscos:
            linhas.append(f"  - {r}")
    else:
        linhas.append("  - Decidir continuar/pausar/escalar sem mais dados pode ser prematuro.")
    linhas.append("")

    linhas.append("PRÓXIMO TESTE:")
    if proximo_teste:
        for p in proximo_teste:
            linhas.append(f"  - {p}")
    else:
        tp = brain.traffic_plan
        if tp and (tp.stop_conditions or tp.scale_conditions):
            linhas.append(
                "  - Use as condições de parada/escala já registradas no "
                "plano de tráfego aprovado para decidir o próximo passo.",
            )
        else:
            linhas.append("  - Nenhuma condição de parada/escala registrada ainda para orientar o próximo teste.")

    return "\n".join(linhas)
