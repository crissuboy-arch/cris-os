"""
Reproducao do bug real reportado no teste da Fase 5 (Telegram), projeto real
`proj_cb094b4ef6a4`:

  O manifesto ("01-Pesquisa/") reportou "evidências disponíveis: 4", mas o
  Paid Traffic Architect respondeu NEEDS_INFORMATION com "Nenhuma evidência
  de mercado registrada".

CAUSA RAIZ: os dois liam campos DIFERENTES do Project Brain.
  - O manifesto contava headline/copy/score/caminho_decidido (4 campos de
    metadado da oportunidade).
  - O Paid Traffic Architect so olhava `oportunidade.evidence` -- uma lista
    EXCLUSIVA de sinais cross-plataforma (TikTok/Instagram/YouTube/Trends)
    coletados pelo Opportunity Analyst -- que pode estar vazia mesmo com
    headline/copy/score reais presentes (nenhuma fonte externa confirmou
    sinal, mas a oportunidade em si tem dado real).

CORRECAO: `ProjectBrain.coletar_evidencias_pesquisa()` -- fonte CANONICA
unica, reutilizada por `core/artifact_manifest.py` e
`core/paid_traffic_architect.py`. Nenhum dado novo foi criado; nenhuma
evidencia foi inventada ou duplicada -- so os dois consumidores passaram a
ler a MESMA agregacao de campos ja existentes.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import json

import pytest

from core.artifact_manifest import gerar_manifest
from core.paid_traffic_architect import avaliar_prontidao, criar_plano_trafego
from memory.layers import ProjectMemory
from memory.project_brain import ProductBlueprint, ProjectBrainStore
from storage import SQLiteMemory


class FakeLLMJSON:
    _provider_name = "fake:inteligente"

    def __init__(self, payload):
        self.payload = payload
        self.chamadas = 0

    def chat(self, messages, tools=None):
        from core.contracts.llm import LLMResponse
        self.chamadas += 1
        return LLMResponse(content=json.dumps(self.payload, ensure_ascii=False))

    def is_alive(self):
        return True


_PAYLOAD_MINIMO = {
    "objective": "Validar demanda", "audience_summary": "Iniciantes em velas artesanais",
    "channels": [], "angles": [], "hooks": [], "creative_matrix": [],
    "testing_plan": [], "measurement_plan": [], "stop_conditions": [], "scale_conditions": [],
    "budget_scenarios": [
        {"nome": "LOW", "valor": "R$20/dia", "type": "PLANNING_ASSUMPTION"},
        {"nome": "STANDARD", "valor": "R$50/dia", "type": "PLANNING_ASSUMPTION"},
        {"nome": "EXPANDED", "valor": "R$150/dia", "type": "PLANNING_ASSUMPTION"},
    ],
    "assumptions": [], "unknowns": [], "risks": [], "approval_required_actions": [],
}


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_fase5_correcao_evidencia.db"


@pytest.fixture()
def brain_store(db_path):
    backend = SQLiteMemory(db_path)
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def _brain_como_o_projeto_real(store):
    """Reproduz EXATAMENTE o estado do bug real: headline/copy/score/nicho/
    caminho decidido presentes, mas ZERO sinal cross-plataforma confirmado
    (nenhuma fonte externa bateu -- `oportunidade.evidence` vazio)."""
    brain = store.create(name="Curso de Velas Artesanais", tipo="opportunity")
    brain.origem.source_headline = "Aprenda a fazer velas artesanais em casa"
    brain.origem.source_copy = "Metodo passo a passo, sem experiencia previa."
    brain.mercado.niche = "velas artesanais"
    brain.mercado.target_country = "BR"
    brain.oportunidade.score = 88
    brain.oportunidade.evidence = []  # <- exatamente o que causou o bug real
    brain.decisao.recommended_path = "AFFILIATE"
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id,
        recommended_product_type="mini_app",
        decision_status="APPROVED",
        target_audience="Iniciantes em velas artesanais",
        country="BR",
        differentiation="Metodo guiado",
        evidence=[],  # copiado de oportunidade.evidence -- tambem vazio
    )
    store.save(brain)
    return brain


def _brain_sem_nenhuma_evidencia(store):
    """Projeto genuinamente sem informacao nenhuma -- deve CONTINUAR
    NEEDS_INFORMATION (regressao: a correcao nao pode afrouxar o gate)."""
    brain = store.create(name="Projeto Vazio", tipo="opportunity")
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id,
        recommended_product_type="mini_app",
        decision_status="APPROVED",
        target_audience="Alguem",
        country="BR",
        differentiation="Algo",
        evidence=[],
    )
    store.save(brain)
    return brain


# ---------------------------------------------------------------------------
# Reproducao exata do bug -- manifesto e Paid Traffic Architect concordam
# ---------------------------------------------------------------------------

def test_manifesto_e_paid_traffic_architect_veem_a_mesma_evidencia(brain_store):
    brain = _brain_como_o_projeto_real(brain_store)

    manifest = gerar_manifest(brain)
    evidencias_do_manifesto = manifest["pastas"]["01-Pesquisa"]["conteudo"]
    assert evidencias_do_manifesto  # o manifesto via evidencia real (4 itens, como no bug)
    assert manifest["pastas"]["01-Pesquisa"]["status"] == "presente"

    lacunas = avaliar_prontidao(brain)
    assert not any("nenhuma evidencia" in l.lower() for l in lacunas)

    # As DUAS fontes usam a MESMA lista -- nunca mais podem divergir.
    assert evidencias_do_manifesto == brain.coletar_evidencias_pesquisa()


def test_paid_traffic_architect_gera_plano_com_evidencia_real_do_projeto(brain_store):
    """Bug real: o projeto tinha evidencia real (headline/copy/score/nicho/
    caminho decidido), mas o Paid Traffic Architect bloqueava com
    NEEDS_INFORMATION dizendo 'nenhuma evidencia'. Apos a correcao, o plano
    deve ser gerado normalmente."""
    brain = _brain_como_o_projeto_real(brain_store)
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(_PAYLOAD_MINIMO))
    assert plano.status == "READY_FOR_APPROVAL"
    assert plano.evidence_summary  # evidencia real refletida no plano
    assert any("velas" in e.lower() for e in plano.evidence_summary)


def test_evidence_summary_referencia_project_brain_nao_duplica_dado_novo(brain_store):
    """O Traffic Plan REFERENCIA a evidencia do Project Brain -- nunca cria
    uma copia paralela/inventada. As strings devem ser EXATAMENTE as
    derivadas do brain, nunca outra coisa."""
    brain = _brain_como_o_projeto_real(brain_store)
    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(_PAYLOAD_MINIMO))
    assert plano.evidence_summary == brain.coletar_evidencias_pesquisa()


def test_evidence_count_nao_e_hardcoded_varia_com_o_brain(brain_store):
    """A contagem de evidencias reflete o estado REAL do brain -- nunca um
    numero fixo (ex.: sempre '4')."""
    brain = _brain_como_o_projeto_real(brain_store)
    manifest_antes = gerar_manifest(brain)
    qtd_antes = len(manifest_antes["pastas"]["01-Pesquisa"]["conteudo"])

    brain.oportunidade.evidence = ["2 resultados no TikTok", "1 resultado no YouTube"]
    manifest_depois = gerar_manifest(brain)
    qtd_depois = len(manifest_depois["pastas"]["01-Pesquisa"]["conteudo"])

    assert qtd_depois == qtd_antes + 2  # cresceu exatamente pelas novas evidencias reais


# ---------------------------------------------------------------------------
# Regressao: projeto SEM nenhuma evidencia continua bloqueado (gate preservado)
# ---------------------------------------------------------------------------

def test_projeto_sem_evidencia_nenhuma_continua_needs_information(brain_store):
    brain = _brain_sem_nenhuma_evidencia(brain_store)
    lacunas = avaliar_prontidao(brain)
    assert any("nenhuma evidencia" in l.lower() for l in lacunas)

    plano = criar_plano_trafego(brain, llm=FakeLLMJSON(_PAYLOAD_MINIMO))
    assert plano.status == "NEEDS_INFORMATION"

    manifest = gerar_manifest(brain)
    assert manifest["pastas"]["01-Pesquisa"]["status"] == "vazio"
    assert manifest["pastas"]["01-Pesquisa"]["conteudo"] == []


def test_needs_information_lista_apenas_a_lacuna_real_nao_generica(brain_store):
    """Pedido explicito: quando faltar so uma coisa especifica, a lacuna
    reportada deve ser especifica -- nunca 'nenhuma evidencia' quando ha
    evidencia real disponivel."""
    brain = _brain_como_o_projeto_real(brain_store)
    brain.blueprint.target_audience = None  # falta so o publico, agora
    lacunas = avaliar_prontidao(brain)
    assert any("publico" in l.lower() or "público" in l.lower() for l in lacunas)
    assert not any("nenhuma evidencia" in l.lower() for l in lacunas)


# ---------------------------------------------------------------------------
# Persistencia real apos restart (mesmo project_id)
# ---------------------------------------------------------------------------

def test_evidencia_e_reconhecida_igual_apos_restart(db_path, brain_store):
    brain = _brain_como_o_projeto_real(brain_store)
    brain_store.save(brain)

    novo_backend = SQLiteMemory(db_path)
    novo_store = ProjectBrainStore(ProjectMemory(novo_backend))
    try:
        recarregado = novo_store.load(brain.project_id)
        assert recarregado.project_id == brain.project_id

        manifest = gerar_manifest(recarregado)
        assert manifest["pastas"]["01-Pesquisa"]["status"] == "presente"
        assert len(manifest["pastas"]["01-Pesquisa"]["conteudo"]) == len(brain.coletar_evidencias_pesquisa())

        lacunas = avaliar_prontidao(recarregado)
        assert not any("nenhuma evidencia" in l.lower() for l in lacunas)
    finally:
        novo_backend.close()


# ---------------------------------------------------------------------------
# GET manifest / GET status continuam deterministicos (regressao Fase 4/5)
# ---------------------------------------------------------------------------

def test_manifesto_continua_zero_llm_apos_correcao(monkeypatch, brain_store):
    import tools.product_factory_tools as pft

    brain = _brain_como_o_projeto_real(brain_store)
    monkeypatch.setattr(pft, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(pft, "get_project_brain_store", lambda: brain_store)

    def _boom():
        raise AssertionError("Manifesto nunca deveria chamar LLM")
    monkeypatch.setattr(pft, "_get_llm_economico", _boom)

    resposta = pft.gerenciar_producao("mostre o manifesto atual", "telegram:1")
    assert "MANIFESTO DO PROJETO" in resposta


# ---------------------------------------------------------------------------
# Reproducao EXATA do bug de cache reportado no reteste real: um
# NEEDS_INFORMATION persistido ANTES da correcao de evidencia nao pode ficar
# "congelado" para sempre -- o comando de criar precisa reavaliar.
# ---------------------------------------------------------------------------

def test_needs_information_antigo_nao_fica_congelado_apos_corrigir_evidencia(monkeypatch, brain_store):
    """Reproduz o segundo bug real: a pessoa pediu o plano de novo depois da
    correcao de evidencia, mas recebeu a MESMA resposta antiga
    (NEEDS_INFORMATION) -- porque um TrafficPlan com esse status ja estava
    persistido de uma tentativa ANTERIOR (antes da correcao), e o comando
    'crie o plano' so reexibia o cache em vez de reavaliar."""
    import tools.paid_traffic_tools as ptt

    brain = _brain_sem_nenhuma_evidencia(brain_store)
    monkeypatch.setattr(ptt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(ptt, "get_project_brain_store", lambda: brain_store)
    monkeypatch.setattr(ptt, "_get_llm_inteligente", lambda: FakeLLMJSON(_PAYLOAD_MINIMO))

    # 1) Primeira tentativa: projeto sem evidencia -- fica NEEDS_INFORMATION
    #    e isso e persistido (exatamente como aconteceu no bug real).
    resposta1 = ptt.gerenciar_trafego("crie o plano de tráfego deste projeto", "telegram:1")
    assert "NEEDS_INFORMATION" in resposta1
    persistido = brain_store.load(brain.project_id)
    assert persistido.traffic_plan.status == "NEEDS_INFORMATION"

    # 2) O projeto GANHA evidencia real (equivalente a corrigir o bug de
    #    leitura de evidencia -- agora ha informacao suficiente).
    persistido.origem.source_headline = "Aprenda a fazer velas artesanais em casa"
    persistido.mercado.niche = "velas artesanais"
    persistido.oportunidade.score = 88
    brain_store.save(persistido)

    # 3) Pedir o plano de novo DEVE reavaliar -- nunca reexibir o
    #    NEEDS_INFORMATION antigo agora que ha evidencia real.
    resposta2 = ptt.gerenciar_trafego("crie o plano de tráfego deste projeto", "telegram:1")
    assert "NEEDS_INFORMATION" not in resposta2
    assert "READY_FOR_APPROVAL" in resposta2

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.traffic_plan.status == "READY_FOR_APPROVAL"
    assert recarregado.traffic_plan.version == 1  # NEEDS_INFORMATION nao conta como versao real


def test_plano_real_ja_gerado_continua_sendo_cache_sem_novo_llm(monkeypatch, brain_store):
    """Regressao: depois que um plano REAL (READY_FOR_APPROVAL) existe, o
    comando de criar continua reaproveitando o cache -- a correcao nao pode
    fazer TODO pedido de 'criar' chamar o LLM de novo."""
    import tools.paid_traffic_tools as ptt

    brain = _brain_como_o_projeto_real(brain_store)
    monkeypatch.setattr(ptt, "get_foco_atual", lambda session: brain.project_id)
    monkeypatch.setattr(ptt, "get_project_brain_store", lambda: brain_store)
    fake = FakeLLMJSON(_PAYLOAD_MINIMO)
    monkeypatch.setattr(ptt, "_get_llm_inteligente", lambda: fake)

    ptt.gerenciar_trafego("crie o plano de tráfego deste projeto", "telegram:1")
    assert fake.chamadas == 1

    ptt.gerenciar_trafego("crie o plano de tráfego deste projeto", "telegram:1")
    assert fake.chamadas == 1  # nao gastou de novo
