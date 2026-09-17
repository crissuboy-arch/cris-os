"""
Testes da correcao pos-teste real da Fase 3: o "projeto/oportunidade em
foco" deixou de ser uma variavel Python (perdida a cada restart, global
entre todos os usuarios) e passou a ser persistido via `UserFocusStore`,
reaproveitando a MESMA infraestrutura do Project Brain (`ProjectMemory` /
`data/cris_os.db`), isolado por `session` (canal+usuario).

Cobre especificamente:
  - persistencia por usuario/chat;
  - recuperacao apos "restart" (nova conexao/objeto apontando pro MESMO
    arquivo de banco -- simula o processo reiniciando);
  - inexistencia de contexto (nunca inventa);
  - isolamento entre duas sessoes/usuarios diferentes.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest

from memory.layers import ProjectMemory
from memory.project_brain import ProjectBrainStore, UserFocusStore
from storage import SQLiteMemory

SESSAO_A = "telegram:1111"
SESSAO_B = "telegram:2222"


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_persistencia_foco.db"


def _abrir_stores(caminho):
    """Simula 'abrir o CRIS OS': cria conexoes NOVAS a partir do mesmo
    arquivo -- exatamente o que acontece quando o processo reinicia."""
    backend = SQLiteMemory(caminho)
    pm = ProjectMemory(backend)
    return ProjectBrainStore(pm), UserFocusStore(pm), backend


# ---------------------------------------------------------------------------
# Persistencia basica por usuario/chat
# ---------------------------------------------------------------------------

def test_set_get_focus_persiste_por_sessao(db_path):
    brain_store, focus_store, backend = _abrir_stores(db_path)
    brain = brain_store.create(name="Oferta X")

    assert focus_store.get_focus(SESSAO_A) is None  # nada ainda -- nunca inventa

    focus_store.set_focus(SESSAO_A, brain.project_id)
    assert focus_store.get_focus(SESSAO_A) == brain.project_id
    backend.close()


def test_focus_store_nao_e_uma_segunda_fonte_de_verdade(db_path):
    """O foco fica na MESMA tabela/arquivo do Project Brain -- nao cria
    banco/tabela paralela."""
    brain_store, focus_store, backend = _abrir_stores(db_path)
    brain = brain_store.create(name="Oferta X")
    focus_store.set_focus(SESSAO_A, brain.project_id)

    # mesma ProjectMemory/backend usada pelos dois -- literalmente o mesmo
    # `project_memory` do SQLite.
    assert focus_store._pm is brain_store._pm
    backend.close()


def test_get_focus_sem_sessao_nunca_inventa(db_path):
    brain_store, focus_store, backend = _abrir_stores(db_path)
    assert focus_store.get_focus("") is None
    assert focus_store.get_focus(SESSAO_A) is None
    backend.close()


def test_set_focus_sem_sessao_nao_persiste_as_cegas(db_path):
    brain_store, focus_store, backend = _abrir_stores(db_path)
    brain = brain_store.create(name="Oferta X")
    focus_store.set_focus("", brain.project_id)  # sem sessao -- deve ser NO-OP
    assert focus_store.get_focus("") is None
    backend.close()


# ---------------------------------------------------------------------------
# RECUPERACAO APOS RESTART (o caso real que falhou no teste pelo Telegram)
# ---------------------------------------------------------------------------

def test_foco_sobrevive_a_reabertura_do_banco_simulando_restart(db_path):
    """Passo A/B/C/D/E pedido na correcao: vincula uma oportunidade, fecha
    tudo, abre de novo a partir do MESMO arquivo (= restart do processo) e
    confirma que o MESMO project_id continua acessivel."""
    # A) vincular/investigar uma oportunidade
    brain_store_1, focus_store_1, backend_1 = _abrir_stores(db_path)
    brain = brain_store_1.create(name="Velas Artesanais", tipo="opportunity")
    brain.origem.source_offer_id = "859300870484371"
    brain_store_1.save(brain)
    focus_store_1.set_focus(SESSAO_A, brain.project_id)

    # B) confirmar o project_id
    project_id_original = brain.project_id
    assert focus_store_1.get_focus(SESSAO_A) == project_id_original

    # C) encerrar o processo (fecha a conexao -- nada mais em memoria)
    backend_1.close()
    del brain_store_1, focus_store_1, backend_1

    # D) "reiniciar": abre stores NOVOS a partir do MESMO arquivo de banco
    brain_store_2, focus_store_2, backend_2 = _abrir_stores(db_path)

    # E) confirma que o MESMO project_id foi restaurado
    project_id_restaurado = focus_store_2.get_focus(SESSAO_A)
    assert project_id_restaurado == project_id_original

    brain_restaurado = brain_store_2.load(project_id_restaurado)
    assert brain_restaurado is not None
    assert brain_restaurado.origem.source_offer_id == "859300870484371"
    backend_2.close()


def test_investigar_oportunidade_sobrevive_a_restart_real(monkeypatch, db_path):
    """Mesmo teste acima, mas passando pelo fluxo REAL de
    `tools/opportunity_tools.py` (investigar_oportunidade + get_foco_atual),
    nao so pelo store isolado."""
    import tools.opportunity_tools as ot

    URL = "https://www.facebook.com/ads/library/?id=859300870484371"
    oferta = {
        "id": "x", "ad_library_id": "859300870484371", "advertiser": "Velas Artesanais",
        "headline": "Aprenda a vender velas artesanais", "copy": "Curso completo " * 10,
        "keyword": "velas artesanais", "niche": "Geral", "score": 94, "country": "US",
        "platform": "FACEBOOK", "ad_url": URL,
    }

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return [oferta]

    monkeypatch.setattr(ot.requests, "get", lambda *a, **kw: FakeResp())
    monkeypatch.setattr(ot.settings, "SUPABASE_URL", "https://exemplo.supabase.co")
    monkeypatch.setattr(ot.settings, "SUPABASE_SERVICE_KEY", "chave-fake")

    # --- "processo 1" ---
    brain_store_1, _, backend_1 = _abrir_stores(db_path)
    monkeypatch.setattr(ot, "_get_project_brain_store", lambda: brain_store_1)
    monkeypatch.setattr(ot, "get_project_brain_store", lambda: brain_store_1)

    resultado = ot.investigar_oportunidade(URL, SESSAO_A)
    assert "Projeto:" in resultado
    project_id_original = ot.get_foco_atual(SESSAO_A)
    assert project_id_original is not None
    backend_1.close()

    # --- "processo 2" (restart: stores novos, mesmo arquivo) ---
    brain_store_2, _, backend_2 = _abrir_stores(db_path)
    monkeypatch.setattr(ot, "_get_project_brain_store", lambda: brain_store_2)
    monkeypatch.setattr(ot, "get_project_brain_store", lambda: brain_store_2)

    project_id_restaurado = ot.get_foco_atual(SESSAO_A)
    assert project_id_restaurado == project_id_original

    brain_restaurado = brain_store_2.load(project_id_restaurado)
    assert brain_restaurado.origem.source_offer_id == "859300870484371"
    backend_2.close()


# ---------------------------------------------------------------------------
# Isolamento entre usuarios/sessoes (preparo multi-tenant)
# ---------------------------------------------------------------------------

def test_isolamento_entre_duas_sessoes(db_path):
    brain_store, focus_store, backend = _abrir_stores(db_path)
    brain_a = brain_store.create(name="Oferta do usuario A")
    brain_b = brain_store.create(name="Oferta do usuario B")

    focus_store.set_focus(SESSAO_A, brain_a.project_id)
    focus_store.set_focus(SESSAO_B, brain_b.project_id)

    assert focus_store.get_focus(SESSAO_A) == brain_a.project_id
    assert focus_store.get_focus(SESSAO_B) == brain_b.project_id
    assert focus_store.get_focus(SESSAO_A) != focus_store.get_focus(SESSAO_B)
    backend.close()


def test_sessao_sem_foco_nao_ve_foco_de_outra_sessao(db_path):
    brain_store, focus_store, backend = _abrir_stores(db_path)
    brain_a = brain_store.create(name="Oferta do usuario A")
    focus_store.set_focus(SESSAO_A, brain_a.project_id)

    # sessao B nunca definiu foco -- NUNCA deve herdar o da sessao A
    assert focus_store.get_focus(SESSAO_B) is None
    backend.close()


def test_atualizar_foco_de_uma_sessao_nao_afeta_a_outra(db_path):
    brain_store, focus_store, backend = _abrir_stores(db_path)
    brain_a1 = brain_store.create(name="Oferta A1")
    brain_a2 = brain_store.create(name="Oferta A2")
    brain_b = brain_store.create(name="Oferta B")

    focus_store.set_focus(SESSAO_A, brain_a1.project_id)
    focus_store.set_focus(SESSAO_B, brain_b.project_id)
    focus_store.set_focus(SESSAO_A, brain_a2.project_id)  # A muda de foco

    assert focus_store.get_focus(SESSAO_A) == brain_a2.project_id
    assert focus_store.get_focus(SESSAO_B) == brain_b.project_id  # B intacto
    backend.close()
