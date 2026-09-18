"""
Product Factory — FUNDACAO (Fase 3).

Recebe SOMENTE um Product Blueprint com `decision_status == "APPROVED"` e
monta um plano inicial de producao. Nesta fase NAO produz os ativos de
verdade (imagem, video, landing page, mini-app...) -- so:
  1. valida o gate de aprovacao (recusa qualquer coisa que nao esteja
     APPROVED -- "a Product Factory nao deve sair produzindo tudo
     automaticamente antes da aprovacao");
  2. monta um plano de producao (passos, cada um mapeado pra uma capability
     do Tool Registry, marcado disponivel/indisponivel);
  3. executa UM artefato textual simples de verdade (um brief do produto),
     via Tool Registry (`COPY_GENERATOR`);
  4. persiste tudo no Project Brain (nao cria memoria paralela).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.evidence_guard import sanitizar_claims_herdadas
from core.tool_registry import (
    CODE_GENERATOR,
    COPY_GENERATOR,
    DRIVE_STORAGE,
    GITHUB,
    IMAGE_GENERATOR,
    LANDING_PAGE_BUILDER,
    MINI_APP_BUILDER,
    VERCEL,
    VIDEO_GENERATOR,
    ToolRegistry,
)
from memory.project_brain import ProductBlueprint, ProjectBrain, ProductionPlan

# Passos previstos de um lancamento completo -- lista GENERICA usada como
# fallback para qualquer `product_type` que nao tenha uma lista propria
# abaixo (nunca trava por um tipo novo/desconhecido). Cada passo mapeia pra
# uma capability do Tool Registry.
_PASSOS_PREVISTOS = [
    ("Brief/copy inicial do produto", COPY_GENERATOR),
    ("Identidade visual (cores/fontes/logo)", IMAGE_GENERATOR),
    ("Mini-app / protótipo funcional", MINI_APP_BUILDER),
    ("Landing page", LANDING_PAGE_BUILDER),
    ("Código/integrações técnicas", CODE_GENERATOR),
    ("Vídeo/criativos", VIDEO_GENERATOR),
    ("Armazenamento de assets", DRIVE_STORAGE),
    ("Repositório de código", GITHUB),
    ("Publicação/deploy", VERCEL),
]

# Entregaveis ESPECIFICOS por formato de produto (Fase 4 -- pedido explicito:
# "nao presumir ebook", o formato aprovado no Product Blueprint determina a
# estrategia de producao). Tipos nao listados aqui caem no fallback generico
# (`_PASSOS_PREVISTOS`) -- nunca lanca excecao por um tipo nao mapeado.
_PASSOS_MINI_APP = [
    ("Brief/copy inicial do produto", COPY_GENERATOR),
    ("Especificação funcional (MVP)", CODE_GENERATOR),
    ("Telas e fluxo", IMAGE_GENERATOR),
    ("Prompt/build specification", MINI_APP_BUILDER),
    ("Stack sugerida e backend", CODE_GENERATOR),
    ("Landing page", LANDING_PAGE_BUILDER),
    ("Identidade visual/branding", IMAGE_GENERATOR),
    ("Documentação", GITHUB),
]

_PASSOS_MICRO_SAAS = [
    ("Brief/copy inicial do produto", COPY_GENERATOR),
    ("Requisitos", CODE_GENERATOR),
    ("MVP", CODE_GENERATOR),
    ("Arquitetura", CODE_GENERATOR),
    ("Onboarding", LANDING_PAGE_BUILDER),
    ("Pricing hypothesis", COPY_GENERATOR),
    ("Landing page", LANDING_PAGE_BUILDER),
    ("Documentação", GITHUB),
]

_PASSOS_CONTEUDO_DIGITAL = [  # ebook, guia, curso, comunidade, assinatura
    ("Brief/copy inicial do produto", COPY_GENERATOR),
    ("Estrutura/capítulos", COPY_GENERATOR),
    ("Conteúdo", COPY_GENERATOR),
    ("Capa/mockup", IMAGE_GENERATOR),
    ("Página de vendas", LANDING_PAGE_BUILDER),
    ("Criativos", IMAGE_GENERATOR),
]

_PASSOS_AFILIADO = [  # NUNCA cria produto proprio -- so comercializa a oferta
    ("Brief/copy inicial da oferta", COPY_GENERATOR),
    ("Posicionamento", COPY_GENERATOR),
    ("Presell", LANDING_PAGE_BUILDER),
    ("Página", LANDING_PAGE_BUILDER),
    ("Criativos", IMAGE_GENERATOR),
    ("Conteúdo", COPY_GENERATOR),
    ("Funil", LANDING_PAGE_BUILDER),
    ("Plano de aquisição", COPY_GENERATOR),
]

_PASSOS_COMERCIO_REVENDA = [
    ("Brief/copy inicial do produto", COPY_GENERATOR),
    ("Produto", COPY_GENERATOR),
    ("Fornecedor (PENDÊNCIA: desconhecido, sem dado real)", DRIVE_STORAGE),
    ("Margem (HIPÓTESE: sem custo real de fornecedor)", COPY_GENERATOR),
    ("Oferta", COPY_GENERATOR),
    ("Página", LANDING_PAGE_BUILDER),
    ("Criativos", IMAGE_GENERATOR),
    ("Canais", COPY_GENERATOR),
    ("Logística/estoque (DEPENDÊNCIA)", DRIVE_STORAGE),
]

_PASSOS_POR_TIPO: dict[str, list[tuple[str, str]]] = {
    "mini_app": _PASSOS_MINI_APP,
    "ferramenta_web": _PASSOS_MINI_APP,
    "calculadora": _PASSOS_MINI_APP,
    "gerador": _PASSOS_MINI_APP,
    "quiz": _PASSOS_MINI_APP,
    "dashboard": _PASSOS_MINI_APP,
    "app": _PASSOS_MINI_APP,
    "agente_ia": _PASSOS_MINI_APP,
    "skill": _PASSOS_MINI_APP,
    "extensao_navegador": _PASSOS_MINI_APP,
    "template": _PASSOS_MINI_APP,
    "biblioteca_templates": _PASSOS_MINI_APP,
    "kit_digital": _PASSOS_MINI_APP,
    "micro_saas": _PASSOS_MICRO_SAAS,
    "ebook": _PASSOS_CONTEUDO_DIGITAL,
    "guia": _PASSOS_CONTEUDO_DIGITAL,
    "curso": _PASSOS_CONTEUDO_DIGITAL,
    "comunidade": _PASSOS_CONTEUDO_DIGITAL,
    "assinatura": _PASSOS_CONTEUDO_DIGITAL,
    "afiliado": _PASSOS_AFILIADO,
    "comercio_revenda": _PASSOS_COMERCIO_REVENDA,
}


def _passos_para_tipo(product_type: str | None) -> list[tuple[str, str]]:
    """Nunca trava por tipo desconhecido -- cai no fallback generico."""
    return _PASSOS_POR_TIPO.get((product_type or "").strip().lower(), _PASSOS_PREVISTOS)


# Tipos "produto digital tecnico" (mini-app-like + micro-SaaS) -- pra estes,
# alem do brief curto, a Product Factory PLANEJA uma especificacao tecnica/
# funcional completa (Fase 4 -- correcao pos-teste real: "mesmo sem builder
# conectado, a Cris deve conseguir planejar/especificar internamente").
_TIPOS_ESPECIFICACAO_TECNICA = frozenset({
    "mini_app", "ferramenta_web", "calculadora", "gerador", "quiz",
    "dashboard", "app", "agente_ia", "skill", "extensao_navegador",
    "template", "biblioteca_templates", "kit_digital", "micro_saas",
})


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PassoProducao:
    nome: str
    capability: str
    disponivel: bool
    status: str  # "concluido" | "pendente" | "planejado" | "indisponivel"
    resultado: str | None = None


@dataclass
class PlanoProducao:
    project_id: str
    product_type: str
    passos: list[PassoProducao] = field(default_factory=list)
    artefatos_gerados: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_agora)


class ProductFactoryError(Exception):
    """Recusa explicita da Product Factory (gate de aprovacao, etc.)."""


def gerar_copy_simples(blueprint: ProductBlueprint, llm=None) -> str:
    """
    Artefato textual simples: um brief curto do produto. Usa OpenRouter
    (tier ECONOMICO, se `llm` for passado) para redigir; sem LLM, monta um
    template deterministico direto dos campos do blueprint -- nunca inventa
    dado que o blueprint nao tem.
    """
    campos = {
        "tipo": blueprint.recommended_product_type or "(não definido)",
        "nicho": blueprint.niche or "(não definido)",
        "problema": blueprint.problem or "(não definido)",
        "conceito": blueprint.product_concept or "(não definido)",
        "valor_central": blueprint.core_value or "(não definido)",
        "publico": blueprint.target_audience or "(não definido)",
        "diferenciacao": blueprint.differentiation or "(não definida)",
        "mvp": blueprint.mvp_scope or "(não definido)",
    }

    if llm is not None:
        try:
            resp = llm.chat([
                {
                    "role": "system",
                    "content": (
                        "Escreva um brief curto (max 4 frases) de um produto, em "
                        "portugues do Brasil, usando SOMENTE os dados fornecidos. "
                        "NAO invente nenhum dado (preco, prazo, numero) que nao "
                        "esteja aqui. Se um campo for '(não definido)', apenas "
                        "omita esse ponto, nao invente um valor pra ele."
                    ),
                },
                {"role": "user", "content": str(campos)},
            ])
            texto = (resp.content or "").strip()
            if texto:
                # Defesa de ultima linha (Fase 4 -- correcao pos-teste real):
                # mesmo com o prompt instruindo a nao inventar dado, sanitiza
                # alegacoes herdadas do concorrente (numero de clientes,
                # "acesso vitalicio", etc.) que porventura tenham vindo do
                # `conceito`/`valor_central` do blueprint (ja promovidos do
                # candidato vencedor do Product Architect).
                return sanitizar_claims_herdadas(texto)
        except Exception:
            pass  # cai no template deterministico abaixo

    return (
        f"Produto proposto: {campos['tipo']}.\n"
        f"Nicho: {campos['nicho']}.\n"
        f"Problema: {campos['problema']}.\n"
        f"Conceito: {campos['conceito']}.\n"
        f"Valor central: {campos['valor_central']}.\n"
        f"Público-alvo: {campos['publico']}.\n"
        f"Diferenciação: {campos['diferenciacao']}.\n"
        f"Escopo do MVP: {campos['mvp']}."
    )


def gerar_especificacao_tecnica(blueprint: ProductBlueprint, brain: ProjectBrain, llm=None) -> str:
    """
    Especificacao funcional/tecnica PLANEJAVEL de um produto digital tecnico
    (mini-app/ferramenta/micro-SaaS/etc.) -- Fase 4, correcao pos-teste real.

    IMPORTANTE: `MINI_APP_BUILDER`/`CODE_GENERATOR`/`LANDING_PAGE_BUILDER`
    estarem `NOT_CONNECTED` (sem executor automatico) NAO significa que a
    Cris nao pode PLANEJAR -- significa so que ela nao pode CONSTRUIR/
    PUBLICAR sozinha. Esta funcao gera o PLANEJAMENTO real (via LLM, usando
    o contexto ja coletado do projeto -- nicho, publico, problema,
    evidencias, riscos), nunca finge que algo foi executado/construido.
    """
    campos = {
        "tipo": blueprint.recommended_product_type or "(não definido)",
        "nicho": blueprint.niche or "(não definido)",
        "pais": blueprint.country or "(não definido)",
        "publico": blueprint.target_audience or "(não definido)",
        "problema": blueprint.problem or "(não definido)",
        "conceito": blueprint.product_concept or "(não definido)",
        "diferenciacao": blueprint.differentiation or "(não definida)",
        "mvp_proposto": blueprint.mvp_scope or "(não definido)",
        "monetizacao_hipotese": ", ".join(blueprint.monetization_options) or "(não definida)",
        "evidencias": "; ".join(blueprint.evidence) or "(nenhuma)",
        "riscos": "; ".join(blueprint.risks) or "(nenhum)",
        "evidencias_ausentes": "; ".join(blueprint.missing_evidence) or "(nenhuma)",
    }

    if llm is not None:
        try:
            resp = llm.chat([
                {
                    "role": "system",
                    "content": (
                        "Escreva uma especificacao funcional/tecnica de um "
                        "produto digital (mini-app/ferramenta/micro-SaaS), em "
                        "portugues do Brasil, usando SOMENTE os dados "
                        "fornecidos. Cubra, em topicos curtos e objetivos: "
                        "OBJETIVO, PROBLEMA RESOLVIDO, USUARIO, "
                        "FUNCIONALIDADES DO MVP, TELAS, FLUXO PRINCIPAL, "
                        "DADOS DE ENTRADA, RESULTADOS/SAIDAS, REGRAS DE "
                        "NEGOCIO, PROPOSTA DE VALOR, DIFERENCIACAO, "
                        "HIPOTESE DE MONETIZACAO (marque como HIPOTESE), "
                        "STACK SUGERIDA (marque como SUGESTAO, nao "
                        "execucao), PROMPT/BUILD SPECIFICATION (pronto pra "
                        "colar num mini-app builder externo), ESTRUTURA DA "
                        "LANDING PAGE e DIRECAO DE BRANDING (cores/tom, nao "
                        "uma imagem). NUNCA afirme que algo foi construido, "
                        "publicado ou executado -- isto e so PLANEJAMENTO. "
                        "NAO invente nenhum dado que nao esteja aqui -- se "
                        "um campo for '(não definido)'/'(nenhuma)'/"
                        "'(nenhum)', apenas declare que falta essa "
                        "informacao, nunca invente um valor."
                    ),
                },
                {"role": "user", "content": str(campos)},
            ])
            texto = (resp.content or "").strip()
            if texto:
                return sanitizar_claims_herdadas(texto)  # defesa de ultima linha (ver gerar_copy_simples)
        except Exception:
            pass  # cai no template deterministico abaixo

    return (
        "ESPECIFICAÇÃO FUNCIONAL (template determinístico — OpenRouter indisponível)\n"
        f"Objetivo: {campos['tipo']} para o nicho '{campos['nicho']}'.\n"
        f"Problema: {campos['problema']}.\n"
        f"Usuário: {campos['publico']}.\n"
        f"Proposta de valor: {campos['conceito']}.\n"
        f"Diferenciação: {campos['diferenciacao']}.\n"
        f"MVP proposto (ver Product Architect): {campos['mvp_proposto']}.\n"
        f"Monetização (HIPÓTESE): {campos['monetizacao_hipotese']}.\n"
        "Funcionalidades do MVP, telas, fluxo, stack e prompt de build "
        "detalhados ainda não especificados (requer IA — OpenRouter "
        "indisponível nesta tentativa)."
    )


def criar_plano_inicial(
    brain: ProjectBrain,
    registry: ToolRegistry,
    llm_economico=None,
) -> PlanoProducao:
    """
    GATE: recusa (levanta ProductFactoryError) se o blueprint nao existir ou
    nao estiver APPROVED. So chega aqui depois de aprovacao humana explicita
    -- ver tools/product_architect_tools.py.
    """
    blueprint = brain.blueprint
    if not blueprint:
        raise ProductFactoryError("Nao ha Product Blueprint neste projeto para produzir.")
    if blueprint.decision_status != "APPROVED":
        raise ProductFactoryError(
            f"Blueprint nao esta aprovado (status atual: {blueprint.decision_status}). "
            "A Product Factory so inicia producao apos aprovacao explicita."
        )

    tipo_normalizado = (blueprint.recommended_product_type or "").strip().lower()
    especificacao_tecnica: str | None = None
    if tipo_normalizado in _TIPOS_ESPECIFICACAO_TECNICA:
        especificacao_tecnica = gerar_especificacao_tecnica(blueprint, brain, llm=llm_economico)

    passos: list[PassoProducao] = []
    artefatos: list[str] = []
    copy_ja_gerado = False
    especificacao_ja_anexada = False
    for nome, capability in _passos_para_tipo(blueprint.recommended_product_type):
        disponivel = registry.disponivel(capability)
        plannable = registry.plannable(capability)
        if disponivel and capability == COPY_GENERATOR and not copy_ja_gerado:
            # So gera o artefato de copy UMA vez por chamada, mesmo que o
            # tipo de produto tenha varios passos mapeados pra COPY_GENERATOR
            # (ex.: comercio/revenda) -- cost-first, nunca paga pelo mesmo
            # artefato duas vezes na mesma execucao.
            resultado = registry.executar(capability, blueprint=blueprint, llm=llm_economico)
            passos.append(PassoProducao(nome, capability, True, "concluido", resultado))
            artefatos.append(resultado)
            copy_ja_gerado = True
        elif disponivel:
            passos.append(PassoProducao(nome, capability, True, "pendente"))
        elif especificacao_tecnica and plannable:
            # NOT_CONNECTED (sem executor automatico) != "nao posso
            # planejar". Marca "planejado" (nunca "concluido" -- nada foi
            # de fato construido/publicado). Uma UNICA chamada de LLM cobre
            # todos os passos plannable desse tipo (cost-first) -- so o
            # PRIMEIRO carrega o texto completo, os demais so referenciam
            # (evita duplicar o mesmo texto longo em cada passo persistido).
            if not especificacao_ja_anexada:
                passos.append(PassoProducao(nome, capability, False, "planejado", especificacao_tecnica))
                artefatos.append(especificacao_tecnica)
                especificacao_ja_anexada = True
            else:
                passos.append(PassoProducao(
                    nome, capability, False, "planejado",
                    "Coberto pela especificação técnica gerada (ver passo anterior).",
                ))
        else:
            passos.append(PassoProducao(nome, capability, False, "indisponivel"))

    return PlanoProducao(
        project_id=brain.project_id,
        product_type=blueprint.recommended_product_type or "(não definido)",
        passos=passos,
        artefatos_gerados=artefatos,
    )


def persistir_plano(brain: ProjectBrain, plano: PlanoProducao) -> None:
    """
    Converte o `PlanoProducao` (ephemero, so existia na resposta do Telegram
    ate a Fase 3) num `ProductionPlan` persistido no Project Brain (Fase 4).
    Funcao PURA (sem I/O) -- so muda `brain.production_plan` em memoria;
    quem chama e responsavel por salvar (`ProjectBrainStore.save`), igual ao
    padrao ja usado para `brain.blueprint`/`brain.business_plan`.
    """
    brain.production_plan = ProductionPlan(
        project_id=plano.project_id,
        product_type=plano.product_type,
        steps=[
            {
                "nome": p.nome, "capability": p.capability,
                "disponivel": p.disponivel, "status": p.status,
                "resultado": p.resultado,
            }
            for p in plano.passos
        ],
        deliverables=[p.nome for p in plano.passos],
        dependencies=[p.nome for p in plano.passos if "DEPENDÊNCIA" in p.nome.upper()],
        status="IN_PRODUCTION",
    )
