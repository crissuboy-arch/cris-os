"""
Artifact Manifest — representacao logica das pastas/entregaveis de um
projeto (Fase 4), independente de Google Drive.

Principio (pedido explicito da Fase 4): o manifest e DERIVADO do Project
Brain, nunca uma segunda fonte de verdade. Cada chamada a `gerar_manifest`
reconstroi o manifest do zero a partir do estado atual do `ProjectBrain` --
nao ha nenhum dado guardado aqui que nao exista (ou nao devesse existir) em
outro campo do brain. Isso significa: mudou o brain, o proximo manifest
gerado ja reflete a mudanca, sem sincronizacao manual.

Nao conecta a nenhum servico externo (Drive, S3, etc.) nesta fase -- e so a
ESTRUTURA logica (pastas + o que cada uma contem hoje), pronta para uma fase
futura sincronizar com um provedor real de storage.
"""

from __future__ import annotations

from memory.project_brain import ProjectBrain

# Estrutura de pastas fixa (pedido explicito da Fase 4). Cada pasta e
# preenchida com o que o Project Brain ja tem hoje -- nunca inventado.
_PASTAS = (
    "01-Pesquisa",
    "02-Product-Blueprint",
    "03-Branding",
    "04-Produto",
    "05-Pagina-de-Vendas",
    "06-Criativos",
    "07-Videos",
    "08-Copy",
    "09-Funil",
    "10-Trafego-Pago",
    "11-Resultados",
)


def _pasta_pesquisa(brain: ProjectBrain) -> dict:
    """
    Usa `ProjectBrain.coletar_evidencias_pesquisa()` -- a MESMA fonte
    canonica que `core/paid_traffic_architect.py:avaliar_prontidao` usa
    (correcao de bug real, Fase 5: antes, o manifesto contava headline/copy/
    score/caminho_decidido pro `conteudo`, mas checava so
    `oportunidade.evidence` pro `status` -- inconsistencia interna que podia
    mostrar "4 evidencias" e `status: vazio` ao mesmo tempo).
    """
    evidencias = brain.coletar_evidencias_pesquisa()
    return {
        "conteudo": evidencias,
        "status": "presente" if evidencias else "vazio",
    }


def _pasta_blueprint(brain: ProjectBrain) -> dict:
    if not brain.blueprint:
        return {"conteudo": [], "status": "vazio"}
    return {
        "conteudo": [
            f"formato_recomendado: {brain.blueprint.recommended_product_type}",
            f"status: {brain.blueprint.decision_status}",
            f"candidatos: {len(brain.blueprint.candidates)}",
        ],
        "status": "presente",
    }


def _pasta_branding(brain: ProjectBrain) -> dict:
    tem_algo = any([brain.brand.brand_name, brain.brand.slogan, brain.brand.colors, brain.brand.fonts])
    return {
        "conteudo": [brain.brand.brand_name] if brain.brand.brand_name else [],
        "status": "presente" if tem_algo else "vazio (Brand Architect ainda nao implementado -- ver ROADMAP-AGENTS.md)",
    }


def _pasta_produto(brain: ProjectBrain) -> dict:
    plano = brain.production_plan
    if not plano:
        return {"conteudo": [], "status": "vazio"}
    return {
        "conteudo": list(plano.deliverables),
        "status": "em producao" if plano.status == "IN_PRODUCTION" else plano.status.lower(),
    }


def _pasta_pagina_de_vendas(brain: ProjectBrain) -> dict:
    bplan = brain.business_plan
    if not bplan or not bplan.sales_page_structure:
        return {"conteudo": [], "status": "vazio"}
    return {
        "conteudo": [
            f"headline: {bplan.headline}" if bplan.headline else None,
            f"estrutura: {bplan.sales_page_structure}",
        ],
        "status": "planejada (nao publicada)",
    }


def _pasta_generica(itens: list[str], vazio_motivo: str) -> dict:
    return {"conteudo": itens, "status": "presente" if itens else vazio_motivo}


def _pasta_copy(brain: ProjectBrain) -> dict:
    plano = brain.production_plan
    artefatos = list(plano.deliverables) if plano else []
    tem_brief = bool(plano and any("brief" in d.lower() or "copy" in d.lower() for d in plano.deliverables))
    return {
        "conteudo": artefatos if tem_brief else [],
        "status": "presente (brief textual gerado)" if tem_brief else "vazio",
    }


def _pasta_funil(brain: ProjectBrain) -> dict:
    bplan = brain.business_plan
    if not bplan or not bplan.funnel_structure:
        return {"conteudo": [], "status": "vazio"}
    return {"conteudo": [bplan.funnel_structure], "status": "planejado (nao executado)"}


def _pasta_trafego_pago(brain: ProjectBrain) -> dict:
    """Fase 5 -- reflete `brain.traffic_plan.status` real, nunca uma segunda
    fonte de verdade: EMPTY/NOT_STARTED antes de existir plano,
    READY_FOR_APPROVAL depois de gerado, APPROVED depois de aprovacao
    humana (nunca inferida)."""
    tp = brain.traffic_plan
    if not tp:
        return {"conteudo": [], "status": "EMPTY / NOT_STARTED"}
    conteudo = [f"{len(tp.channels)} canal(is) avaliado(s)"] if tp.channels else []
    return {"conteudo": conteudo, "status": tp.status}


def gerar_manifest(brain: ProjectBrain) -> dict:
    """
    Deriva o Artifact Manifest inteiro do estado ATUAL do `brain` -- nunca
    lanca excecao (uma pasta sem dado nenhum so aparece "vazia", nunca
    quebra a geracao das demais).
    """
    pastas = {
        "01-Pesquisa": _pasta_pesquisa(brain),
        "02-Product-Blueprint": _pasta_blueprint(brain),
        "03-Branding": _pasta_branding(brain),
        "04-Produto": _pasta_produto(brain),
        "05-Pagina-de-Vendas": _pasta_pagina_de_vendas(brain),
        "06-Criativos": _pasta_generica([], "vazio (geracao de imagem/video nao habilitada nesta fase)"),
        "07-Videos": _pasta_generica([], "vazio (geracao de video nao habilitada nesta fase)"),
        "08-Copy": _pasta_copy(brain),
        "09-Funil": _pasta_funil(brain),
        "10-Trafego-Pago": _pasta_trafego_pago(brain),
        "11-Resultados": _pasta_generica([], "vazio (nenhuma campanha rodou ainda)"),
    }
    return {
        "raiz": f"SCALAFLOW/PRODUTOS/{brain.project_id}/",
        "pastas": pastas,
        "master_project": {
            "project_id": brain.project_id,
            "nome": brain.identidade.name,
            "tipo_produto": brain.blueprint.recommended_product_type if brain.blueprint else None,
            "status_blueprint": brain.blueprint.decision_status if brain.blueprint else None,
            "status_business_plan": brain.business_plan.approval_status if brain.business_plan else None,
            "status_producao": brain.production_plan.status if brain.production_plan else None,
            "status_trafego_pago": brain.traffic_plan.status if brain.traffic_plan else None,
            "atualizado_em": brain.identidade.updated_at,
        },
        "sincronizado_com_drive": False,
    }


def formatar_manifesto_get_current(manifest: dict) -> str:
    """
    Formato MINIMO e deterministico do manifesto (Fase 4 -- correcao
    pos-teste real, "GET_CURRENT_PROJECT_MANIFEST"). NUNCA despeja o
    conteudo completo do Business Plan ou de qualquer artefato longo -- so
    status curtos por pasta. Esta funcao e PURA (so formata um dict ja
    calculado) -- quem chama garante que `gerar_manifest` (tambem pura, sem
    LLM/rede) foi a unica coisa executada antes.
    """
    mp = manifest["master_project"]
    pastas = manifest["pastas"]

    def status_de(nome: str) -> str:
        return pastas.get(nome, {}).get("status", "vazio")

    linhas = [
        "📁 MANIFESTO DO PROJETO",
        "",
        f"project_id: {mp['project_id']}",
        f"project_name: {mp['nome']}",
        "",
        "01-Pesquisa/",
        f"  evidências disponíveis: {len(pastas['01-Pesquisa'].get('conteudo', []))}",
        "",
        "02-Product-Blueprint/",
        f"  formato: {mp['tipo_produto'] or '(não definido)'}",
        f"  status de aprovação: {mp['status_blueprint'] or '(nenhum)'}",
        "",
        "03-Branding/",
        f"  status: {status_de('03-Branding')}",
        "",
        "04-Produto/",
        f"  status: {status_de('04-Produto')}",
        f"  artefatos existentes: {len(pastas['04-Produto'].get('conteudo', []))}",
        "",
        "05-Pagina-de-Vendas/",
        f"  status: {status_de('05-Pagina-de-Vendas')}",
        "",
        "06-Criativos/",
        f"  status: {status_de('06-Criativos')}",
        "",
        "07-Videos/",
        f"  status: {status_de('07-Videos')}",
        "",
        "08-Copy/",
        f"  status: {status_de('08-Copy')}",
        "",
        "09-Funil/",
        f"  status: {status_de('09-Funil')}",
        "",
        "10-Trafego-Pago/",
        f"  status: {status_de('10-Trafego-Pago')}",
        "",
        "11-Resultados/",
        f"  status: {status_de('11-Resultados')}",
        "",
        "MASTER-PROJECT",
        f"  status_blueprint: {mp['status_blueprint']}",
        f"  status_business_plan: {mp['status_business_plan']}",
        f"  status_producao: {mp['status_producao']}",
        f"  status_trafego_pago: {mp['status_trafego_pago']}",
        f"  updated_at: {mp['atualizado_em']}",
    ]
    return "\n".join(linhas)
