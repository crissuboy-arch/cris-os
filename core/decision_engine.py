"""
Decision Engine — decide o caminho de uma oportunidade a partir de EVIDENCIA
REAL, sem LLM (Fase 2: 100% deterministico, sem custo de IA).

Caminhos possiveis: CREATE_OWN_PRODUCT | AFFILIATE | COMMERCE_RESALE |
INVESTIGATE_MORE | DISCARD.

Postura deliberadamente conservadora (pedido explicito da Cris):
  - NAO assume que toda oportunidade deve virar produto proprio.
  - "Produto viral" != "produto lucrativo": sem dado de fornecedor, comissao
    de afiliado ou modelo de negocio, o motor nunca recomenda
    CREATE_OWN_PRODUCT ou COMMERCE_RESALE sozinho -- essas duas saidas ficam
    disponiveis para quando uma fase futura trouxer esse tipo de evidencia
    (ou a Cris decidir manualmente e registrar no Project Brain).
  - Sem evidencia cruzada (so o proprio ScalaFlow), o motor pede mais
    investigacao em vez de decidir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CAMINHOS_VALIDOS = frozenset({
    "CREATE_OWN_PRODUCT", "AFFILIATE", "COMMERCE_RESALE",
    "INVESTIGATE_MORE", "DISCARD",
})

_SCORE_MINIMO_PARA_INVESTIGAR = 50


@dataclass
class SinalPlataforma:
    """Um sinal (ou a ausencia dele) numa fonte externa ao ScalaFlow."""

    fonte: str  # "tiktok" | "instagram" | "youtube" | "google_trends"
    encontrado: bool
    resumo: str  # texto legivel; se nao encontrado: "Sem evidencia disponivel nesta fonte."
    metricas: dict = field(default_factory=dict)
    termo_busca: str | None = None  # palavra-chave usada para correlacionar (sempre exposto -- NAO e link garantido)


@dataclass
class Decisao:
    path: str
    motivo: str
    evidence_level: str  # "baixo" | "medio" | "alto"
    fontes_com_evidencia: list[str] = field(default_factory=list)
    dados_faltantes: list[str] = field(default_factory=list)


def decidir(
    score_scalaflow: float | None,
    sinais: list[SinalPlataforma],
) -> Decisao:
    """
    Regras (nesta ordem, primeira que bater decide):

    1. Sem score (nunca deveria acontecer para um anuncio real do ScalaFlow)
       -> INVESTIGATE_MORE.
    2. Score abaixo do minimo -> DISCARD (motivo registrado p/ nao reanalisar).
    3. Nenhuma fonte externa confirmou sinal -> INVESTIGATE_MORE.
    4. Só 1 fonte externa confirmou -> INVESTIGATE_MORE (pede mais fontes).
    5. 2+ fontes externas confirmaram -> AFFILIATE (caminho mais barato pra
       validar antes de comprometer recursos; CREATE_OWN_PRODUCT/
       COMMERCE_RESALE exigem evidencia de fornecedor/modelo de negocio que
       o ScalaFlow sozinho nao fornece -- ver docstring do modulo).
    """
    fontes_com_evidencia = [s.fonte for s in sinais if s.encontrado]
    fontes_sem_evidencia = [s.fonte for s in sinais if not s.encontrado]

    if score_scalaflow is None:
        return Decisao(
            path="INVESTIGATE_MORE",
            motivo="Nao ha score do ScalaFlow para este anuncio -- dado essencial ausente.",
            evidence_level="baixo",
            fontes_com_evidencia=fontes_com_evidencia,
            dados_faltantes=["score_scalaflow"] + fontes_sem_evidencia,
        )

    if score_scalaflow < _SCORE_MINIMO_PARA_INVESTIGAR:
        return Decisao(
            path="DISCARD",
            motivo=(
                f"Score do ScalaFlow ({score_scalaflow}) abaixo do minimo "
                f"({_SCORE_MINIMO_PARA_INVESTIGAR}) para justificar investigacao."
            ),
            evidence_level="baixo",
            fontes_com_evidencia=fontes_com_evidencia,
            dados_faltantes=fontes_sem_evidencia,
        )

    if not fontes_com_evidencia:
        return Decisao(
            path="INVESTIGATE_MORE",
            motivo=(
                "Nenhuma fonte alem do proprio ScalaFlow confirmou sinal. "
                "Faltam dados cruzados antes de decidir um caminho."
            ),
            evidence_level="baixo",
            fontes_com_evidencia=[],
            dados_faltantes=fontes_sem_evidencia,
        )

    if len(fontes_com_evidencia) == 1:
        return Decisao(
            path="INVESTIGATE_MORE",
            motivo=(
                f"Apenas 1 fonte externa ({fontes_com_evidencia[0]}) confirmou sinal. "
                "Recomendo checar mais plataformas antes de decidir um caminho."
            ),
            evidence_level="medio",
            fontes_com_evidencia=fontes_com_evidencia,
            dados_faltantes=fontes_sem_evidencia,
        )

    evidence_level = "alto" if len(fontes_com_evidencia) >= 3 else "medio"
    return Decisao(
        path="AFFILIATE",
        motivo=(
            f"{len(fontes_com_evidencia)} fontes externas confirmam sinal "
            f"(score ScalaFlow {score_scalaflow}). Afiliacao e o caminho mais "
            "barato/rapido para validar antes de comprometer recursos em "
            "produto proprio ou revenda."
        ),
        evidence_level=evidence_level,
        fontes_com_evidencia=fontes_com_evidencia,
        dados_faltantes=fontes_sem_evidencia,
    )


# ---------------------------------------------------------------------------
# Secoes 5-7 do pedido: formatos de produto proprio / afiliacao / comercio.
# Implementadas como preparo estrutural HONESTO: o ScalaFlow (anuncios
# minerados) nao tem dado de fornecedor, comissao de afiliado, checkout ou
# estoque -- por isso essas funcoes NAO inventam essas respostas. Ficam
# prontas para uma fase futura conectar uma fonte real (ex.: consulta a um
# programa de afiliados, catalogo de fornecedores).
# ---------------------------------------------------------------------------

def sugerir_formatos_produto_proprio(decisao: Decisao) -> list[dict]:
    """
    So sugere formatos quando o caminho decidido for CREATE_OWN_PRODUCT (hoje
    o motor nunca decide isso sozinho -- ver `decidir()`). Retorna vazio nos
    demais casos, com o motivo explicito.
    """
    if decisao.path != "CREATE_OWN_PRODUCT":
        return []
    # Placeholder estrutural: quando uma fase futura permitir chegar aqui
    # (por decisao manual da Cris registrada no Project Brain), preencher com
    # avaliacao real por nicho/formato -- nao antes.
    return [{
        "formato": "(nao avaliado)",
        "motivo": "Formato de produto proprio ainda nao e avaliado automaticamente nesta fase.",
        "vantagens": [],
        "riscos": [],
        "complexidade": None,
        "velocidade_mvp": None,
        "diferenciacao_possivel": None,
    }]


def preparar_analise_afiliacao(sinais: list[SinalPlataforma]) -> dict:
    """Estrutura de analise de afiliacao -- sem evidencia real disponivel ainda."""
    return {
        "programa_afiliados": "Sem evidencia disponivel (ScalaFlow nao mineira programas de afiliados).",
        "plataforma": None,
        "comissao": None,
        "paises": None,
        "moeda": None,
        "restricoes": None,
        "brand_bidding": None,
        "checkout": None,
        "presell": None,
        "canais_possiveis": [s.fonte for s in sinais if s.encontrado] or None,
        "observacao": (
            "Nao afirmar que existe programa de afiliados sem evidencia. "
            "Produto viral nao significa automaticamente produto lucrativo."
        ),
    }


def preparar_analise_comercio(sinais: list[SinalPlataforma]) -> dict:
    """Estrutura de analise de comercio/revenda -- sem evidencia real disponivel ainda."""
    return {
        "demanda": "Sem evidencia disponivel (ScalaFlow nao mineira dados de demanda/estoque).",
        "fornecedor": None,
        "margem": None,
        "preco": None,
        "logistica": None,
        "mercado": None,
        "canais_possiveis": [s.fonte for s in sinais if s.encontrado] or None,
        "riscos": ["Sem dado de fornecedor/logistica -- nao comprar/criar loja/contratar fornecedor nesta fase."],
    }
