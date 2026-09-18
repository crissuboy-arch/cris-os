"""
Testes da Fase 4: Artifact Manifest -- estrutura logica de pastas/entregaveis,
derivada do Project Brain (nunca uma segunda fonte de verdade), sem conexao
com Google Drive nesta fase.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.artifact_manifest import formatar_manifesto_get_current, gerar_manifest
from core.product_factory import criar_plano_inicial, persistir_plano
from core.tool_registry import criar_registry_padrao
from memory.project_brain import Identidade, ProductBlueprint, ProjectBrain

_PASTAS_ESPERADAS = (
    "01-Pesquisa", "02-Product-Blueprint", "03-Branding", "04-Produto",
    "05-Pagina-de-Vendas", "06-Criativos", "07-Videos", "08-Copy",
    "09-Funil", "10-Trafego-Pago", "11-Resultados",
)


def _brain_minimo() -> ProjectBrain:
    return ProjectBrain(identidade=Identidade(project_id="proj_teste123", name="Projeto Teste"))


def test_manifest_tem_todas_as_11_pastas_mesmo_para_projeto_vazio():
    brain = _brain_minimo()
    manifest = gerar_manifest(brain)
    assert set(manifest["pastas"].keys()) == set(_PASTAS_ESPERADAS)


def test_manifest_nao_conecta_drive_nesta_fase():
    brain = _brain_minimo()
    manifest = gerar_manifest(brain)
    assert manifest["sincronizado_com_drive"] is False


def test_manifest_raiz_usa_estrutura_scalaflow_produtos():
    brain = _brain_minimo()
    manifest = gerar_manifest(brain)
    assert manifest["raiz"] == "SCALAFLOW/PRODUTOS/proj_teste123/"


def test_manifest_e_derivado_nunca_segunda_fonte_de_verdade():
    """Duas chamadas seguidas sobre o MESMO brain (sem mudanca nenhuma)
    devolvem o mesmo conteudo -- prova que nada e guardado 'a parte',
    tudo vem do brain a cada chamada."""
    brain = _brain_minimo()
    m1 = gerar_manifest(brain)
    m2 = gerar_manifest(brain)
    assert m1 == m2


def test_manifest_reflete_mudanca_no_brain_imediatamente():
    brain = _brain_minimo()
    antes = gerar_manifest(brain)
    assert antes["pastas"]["02-Product-Blueprint"]["status"] == "vazio"

    brain.blueprint = ProductBlueprint(project_id=brain.project_id, recommended_product_type="curso", decision_status="APPROVED")
    depois = gerar_manifest(brain)
    assert depois["pastas"]["02-Product-Blueprint"]["status"] == "presente"
    assert depois["master_project"]["tipo_produto"] == "curso"


def test_manifest_pasta_produto_reflete_production_plan():
    brain = _brain_minimo()
    brain.blueprint = ProductBlueprint(project_id=brain.project_id, recommended_product_type="ebook", decision_status="APPROVED")
    registry = criar_registry_padrao()
    plano = criar_plano_inicial(brain, registry)
    persistir_plano(brain, plano)

    manifest = gerar_manifest(brain)
    assert manifest["pastas"]["04-Produto"]["conteudo"]
    assert manifest["pastas"]["08-Copy"]["status"].startswith("presente")


def test_formatar_manifesto_get_current_nao_lanca_excecao_para_projeto_vazio():
    brain = _brain_minimo()
    manifest = gerar_manifest(brain)
    texto = formatar_manifesto_get_current(manifest)
    assert "MANIFESTO DO PROJETO" in texto
    assert brain.project_id in texto
    assert "MASTER-PROJECT" in texto
