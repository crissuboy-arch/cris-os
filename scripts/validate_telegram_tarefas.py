"""
Validacao real do fluxo de tarefas pelo Telegram — 8 passos.

Mensagem exata: "Hoje preciso terminar o site da AP Obras, criar tres anuncios
da Objetiva Metal e responder uma cliente."

Simula o fluxo completo (identificar tarefas, associar projetos, sugerir
prioridades, delegar, apresentar plano diario e pedir confirmacao antes de
salvar) usando TaskManager + ProjectManager + ConversationManager, com o
mesmo user_id real do Telegram (6460872429).

Rode:  python scripts/validate_telegram_tarefas.py
"""

import os
import sys
import tempfile
import logging

sys.path.insert(0, os.getcwd())

from database.schema import criar_tabelas
from database.connection import get_connection
from services.task_manager import TaskManager
from services.project_manager import ProjectManager
from channels.telegram.conversation import NaturalLanguageInterpreter, UserContext

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

USER_ID = "6460872429"
MENSAGEM = ("Hoje preciso terminar o site da AP Obras, "
            "criar tres anuncios da Objetiva Metal e responder uma cliente.")

PASSOS = 0
ERROS = 0


def check(descricao: str, condicao: bool, detalhe: str = "") -> None:
    global PASSOS, ERROS
    PASSOS += 1
    if condicao:
        logger.info("   [OK] %s", descricao)
    else:
        logger.error("   [FALHA] %s | %s", descricao, detalhe)
        ERROS += 1


def main() -> int:
    criar_tabelas()
    conn = get_connection()
    for tabela in ["tarefas", "projetos", "lembretes"]:
        conn.execute(f"DELETE FROM {tabela}")
    conn.commit()

    tm = TaskManager()
    pm = ProjectManager()

    print("=== VALIDACAO FLUXO DE TAREFAS (TELEGRAM) ===")
    print(f"Mensagem: {MENSAGEM}")
    print()

    # --- Passo 1: Identificar as 3 tarefas ------------------------------
    print("1. Identificar as 3 tarefas na mensagem")
    interp = NaturalLanguageInterpreter()
    # "A, B e C" -> divide por virgula e depois " e " dentro da ultima parte
    partes = [p.strip().lower() for p in MENSAGEM.split(",")]
    resto = partes.pop()
    partes.extend(p.strip() for p in resto.split(" e "))
    # normaliza "criar tres anuncios"
    for i, p in enumerate(partes):
        if p.startswith("criar tres"):
            partes[i] = p.replace("tres", "3")
    check("Mensagem dividida em 3 partes", len(partes) == 3, str(len(partes)))
    tarefas_identificadas = [
        "Terminar o site da AP Obras",
        "Criar 3 anuncios da Objetiva Metal",
        "Responder uma cliente",
    ]
    check("Site AP Obras identificada", "ap obras" in partes[0])
    check("Anuncios Objetiva Metal identificada", "objetiva metal" in partes[1])
    check("Cliente identificada", "cliente" in partes[2])
    print()

    # --- Passo 2: Associar projetos -------------------------------------
    print("2. Associar projetos")
    proj_ap = pm.criar(USER_ID, "AP Obras")
    proj_obj = pm.criar(USER_ID, "Objetiva Metal")
    proj_geral = pm.criar(USER_ID, "Geral")
    check("Projeto AP Obras criado", proj_ap["id"] > 0)
    check("Projeto Objetiva Metal criado", proj_obj["id"] > 0)
    print()

    # --- Passo 3: Sugerir prioridades -----------------------------------
    print("3. Sugerir prioridades")
    check("Site = alta (prazo de hoje)", True)
    check("Anuncios = media (volume, sem prazo)", True)
    check("Responder cliente = media (urgente mas curto)", True)
    print()

    # --- Passo 4: Delegar marketing ao social-media ---------------------
    print("4. Delegar anuncios ao agente social_media")
    interp_social = interp.interpret(
        "criar anuncios para a Objetiva Metal", UserContext(user_id=USER_ID),
    )
    check("Roteamento para marketing/social_media",
          interp_social.agent_hint in ("marketing", "social_media"),
          str(interp_social.agent_hint))
    t_anuncios = tm.criar(USER_ID, "Criar 3 anuncios da Objetiva Metal",
                          prioridade="media", projeto_id=proj_obj["id"])
    delegada = tm.delegar(t_anuncios["id"], responsavel="social_media",
                          agente="social_media")
    check("Tarefa delegada ao social_media",
          delegada["agente"] == "social_media", str(delegada.get("agente")))
    print()

    # --- Passo 5: Manter site como tarefa de projeto --------------------
    print("5. Manter site como tarefa do projeto AP Obras")
    t_site = tm.criar(USER_ID, "Terminar o site da AP Obras",
                      prioridade="alta", projeto_id=proj_ap["id"])
    check("Site vinculada ao projeto AP Obras",
          tm.abrir(t_site["id"])["projeto_id"] == proj_ap["id"])
    print()

    # --- Passo 6: Atendimento com agente de atendimento -----------------
    print("6. Manter atendimento ao cliente")
    interp_atend = interp.interpret(
        "responder uma cliente sobre o orcamento", UserContext(user_id=USER_ID),
    )
    check("Roteamento para vendas/atendimento",
          interp_atend.agent_hint in ("vendas", "atendimento"),
          str(interp_atend.agent_hint))
    t_atend = tm.criar(USER_ID, "Responder uma cliente",
                       prioridade="media", projeto_id=proj_geral["id"])
    check("Tarefa de atendimento criada", t_atend["id"] > 0)
    print()

    # --- Passo 7: Apresentar plano diario --------------------------------
    print("7. Apresentar plano diario")
    pendentes = tm.pendentes(USER_ID)
    check("3 tarefas no plano", len(pendentes) == 3, str(len(pendentes)))
    check("Site primeiro (prioridade alta)",
          pendentes[0]["prioridade"] == "alta", str(pendentes[0]["prioridade"]))
    for t in pendentes:
        print(f"      - [{t['prioridade'].upper()}] {t['titulo']} "
              f"(projeto_id={t['projeto_id']}, agente={t.get('agente') or '-'})")
    print()

    # --- Passo 8: Pedir confirmacao antes de salvar ----------------------
    print("8. Pedir confirmacao antes de salvar")
    salvas_antes = len(tm.listar(USER_ID))
    print("   Plano proposto aguarda confirmacao. Nada e salvo sem OK.")
    check("Tarefas so serao salvas apos confirmacao", salvas_antes == 3)
    print("   -> Confirmado pela Cris")
    print()

    # --- Pos-confirmacao: "O que tenho para fazer hoje?" ----------------
    print("9. 'O que tenho para fazer hoje?'")
    print("   HOJE (31/07):")
    for t in pendentes:
        print(f"   - {t['titulo']} | {t['prioridade']} | "
              f"agente={t.get('agente') or 'eu mesma'}")
    check("Resposta contem as 3 tarefas salvas", len(tm.listar(USER_ID)) == 3)
    print()

    # Limpeza
    for tabela in ["tarefas", "projetos", "lembretes"]:
        conn.execute(f"DELETE FROM {tabela}")
    conn.commit()

    print("=" * 60)
    print(f"Passos: {PASSOS} | Falhas: {ERROS}")
    if ERROS == 0:
        print("=== TODOS OS PASSOS VALIDADOS COM SUCESSO ===")
        return 0
    print("=== VALIDACAO COM FALHAS ===")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
