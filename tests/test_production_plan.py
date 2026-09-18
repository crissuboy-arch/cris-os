"""
Testes da Fase 4: Production Plan especifico por tipo de produto + persistencia
no Project Brain (complementa `core/product_factory.py`, Fase 3 -- nunca
duplica a logica existente).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from core.product_factory import (
    ProductFactoryError,
    criar_plano_inicial,
    persistir_plano,
)
from core.tool_registry import (
    COPY_GENERATOR,
    DRIVE_STORAGE,
    MINI_APP_BUILDER,
    criar_registry_padrao,
)
from memory.layers import ProjectMemory
from memory.project_brain import ProductBlueprint, ProjectBrainStore
from storage import SQLiteMemory


@pytest.fixture()
def brain_store(tmp_path):
    backend = SQLiteMemory(tmp_path / "test_production_plan.db")
    yield ProjectBrainStore(ProjectMemory(backend))
    backend.close()


def _brain_com_blueprint(store, tipo):
    brain = store.create(name="Oferta Teste", tipo="opportunity")
    brain.blueprint = ProductBlueprint(
        project_id=brain.project_id,
        recommended_product_type=tipo,
        decision_status="APPROVED",
    )
    store.save(brain)
    return brain


def test_mini_app_inclui_passo_de_mini_app_builder(brain_store):
    brain = _brain_com_blueprint(brain_store, "mini_app")
    registry = criar_registry_padrao()
    plano = criar_plano_inicial(brain, registry)
    capabilities = {p.capability for p in plano.passos}
    assert MINI_APP_BUILDER in capabilities
    assert COPY_GENERATOR in capabilities


def test_afiliado_nunca_inclui_passo_de_producao_de_produto_proprio(brain_store):
    """Afiliado NAO cria produto proprio -- so comercializa a oferta."""
    brain = _brain_com_blueprint(brain_store, "afiliado")
    registry = criar_registry_padrao()
    plano = criar_plano_inicial(brain, registry)
    capabilities = {p.capability for p in plano.passos}
    assert MINI_APP_BUILDER not in capabilities


def test_comercio_revenda_marca_fornecedor_como_pendencia(brain_store):
    brain = _brain_com_blueprint(brain_store, "comercio_revenda")
    registry = criar_registry_padrao()
    plano = criar_plano_inicial(brain, registry)
    nomes = [p.nome for p in plano.passos]
    assert any("PENDÊNCIA" in n for n in nomes)
    assert any("HIPÓTESE" in n for n in nomes)


def test_tipo_desconhecido_cai_no_fallback_generico_sem_travar(brain_store):
    brain = _brain_com_blueprint(brain_store, "produto_fisico")
    registry = criar_registry_padrao()
    plano = criar_plano_inicial(brain, registry)  # nao pode lancar excecao
    assert len(plano.passos) > 0


def test_copy_generator_so_executa_uma_vez_mesmo_com_varios_passos_mapeados(brain_store):
    """comercio_revenda tem VARIOS passos mapeados pra COPY_GENERATOR --
    so o primeiro deve gerar de verdade (cost-first: nunca paga 2x pelo
    mesmo tipo de artefato na mesma chamada)."""
    brain = _brain_com_blueprint(brain_store, "comercio_revenda")
    registry = criar_registry_padrao()
    plano = criar_plano_inicial(brain, registry)
    concluidos = [p for p in plano.passos if p.status == "concluido"]
    assert len(concluidos) == 1
    assert len(plano.artefatos_gerados) == 1


def test_persistir_plano_converte_para_production_plan(brain_store):
    brain = _brain_com_blueprint(brain_store, "ebook")
    registry = criar_registry_padrao()
    plano = criar_plano_inicial(brain, registry)

    persistir_plano(brain, plano)

    assert brain.production_plan is not None
    assert brain.production_plan.product_type == "ebook"
    assert brain.production_plan.status == "IN_PRODUCTION"
    assert len(brain.production_plan.steps) == len(plano.passos)
    assert brain.production_plan.deliverables == [p.nome for p in plano.passos]


def test_persistir_plano_sobrevive_a_save_e_load(brain_store):
    brain = _brain_com_blueprint(brain_store, "curso")
    registry = criar_registry_padrao()
    plano = criar_plano_inicial(brain, registry)
    persistir_plano(brain, plano)
    brain_store.save(brain)

    recarregado = brain_store.load(brain.project_id)
    assert recarregado.production_plan is not None
    assert recarregado.production_plan.product_type == "curso"
    assert recarregado.production_plan.steps


def test_gate_continua_recusando_sem_aprovacao(brain_store):
    """Regressao Fase 3: o gate de aprovacao continua absoluto mesmo com a
    lista de passos agora sendo especifica por tipo."""
    brain = _brain_com_blueprint(brain_store, "mini_app")
    brain.blueprint.decision_status = "PENDING_APPROVAL"
    registry = criar_registry_padrao()
    with pytest.raises(ProductFactoryError):
        criar_plano_inicial(brain, registry)
