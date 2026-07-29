"""
Ferramentas do agente Produtividade.
"""

from tools.base import Tool


def _planejamento_diario(texto: str) -> str:
    return (
        f"PLANEJAMENTO DIARIO\n"
        f"{'=' * 50}\n\n"
        f"Tarefas do dia: {texto}\n\n"
        f"---\n"
        f"DATA: [dd/mm/aaaa]\n\n"
        f"MANHA (08:00-12:00) — Alta energia:\n"
        f"  08:00-08:30 | Planejamento e revisao do dia\n"
        f"  08:30-10:00 | Tarefa mais importante\n"
        f"  10:00-10:15 | Pausa\n"
        f"  10:15-12:00 | Tarefa secundaria\n\n"
        f"ALMOCO (12:00-13:00)\n\n"
        f"TARDE (13:00-18:00) — Moderada:\n"
        f"  13:00-14:30 | Reunioes e contatos\n"
        f"  14:30-14:45 | Pausa\n"
        f"  14:45-16:00 | Tarefas administrativas\n"
        f"  16:00-18:00 | Revisao e preparacao do dia seguinte\n\n"
        f"TOP 3 PRIORIDADES:\n"
        f"  1. [Principal]\n"
        f"  2. [Secundaria]\n"
        f"  3. [Se der tempo]"
    )


def _checklist(texto: str) -> str:
    return (
        f"CHECKLIST\n"
        f"{'=' * 50}\n\n"
        f"Referencia: {texto}\n\n"
        f"[ ] 1. Definir objetivo claro\n"
        f"[ ] 2. Listar recursos necessarios\n"
        f"[ ] 3. Dividir em etapas menores\n"
        f"[ ] 4. Estimar tempo para cada etapa\n"
        f"[ ] 5. Executar primeira etapa\n"
        f"[ ] 6. Revisar e ajustar\n"
        f"[ ] 7. Concluir e celebrar\n\n"
        f"Dica: uma tarefa por vez. Nao multitarefa.\n"
        f"Use pomodoro: 25 min foco, 5 min pausa."
    )


def _plano_semanal(texto: str) -> str:
    return (
        f"PLANO SEMANAL\n"
        f"{'=' * 50}\n\n"
        f"Objetivos: {texto}\n\n"
        f"SEGUNDA:\n"
        f"  - Planejamento da semana\n"
        f"  - Tarefas administrativas\n\n"
        f"TERCA:\n"
        f"  - Foco no projeto principal\n"
        f"  - Reunioes internas\n\n"
        f"QUARTA:\n"
        f"  - Desenvolvimento e criacao\n"
        f"  - Acompanhamento de prazos\n\n"
        f"QUINTA:\n"
        f"  - Reunioes com clientes/parceiros\n"
        f"  - Tarefas operacionais\n\n"
        f"SEXTA:\n"
        f"  - Fechamento da semana\n"
        f"  - Revisao de resultados\n"
        f"  - Preparacao para a proxima\n\n"
        f"SABADO/DOMINGO (opcional):\n"
        f"  - Leitura e estudo\n"
        f"  - Atividades pessoais"
    )


def _plano_mensal(texto: str) -> str:
    return (
        f"PLANO MENSAL\n"
        f"{'=' * 50}\n\n"
        f"Objetivos do mes: {texto}\n\n"
        f"SEMANA 1 — Planejamento:\n"
        f"  - Definir metas do mes\n"
        f"  - Alinhar expectativas\n"
        f"  - Organizar recursos\n\n"
        f"SEMANA 2 — Execucao:\n"
        f"  - Foco nas entregas\n"
        f"  - Acompanhamento de metricas\n\n"
        f"SEMANA 3 — Ajustes:\n"
        f"  - Revisar progresso\n"
        f"  - Corrigir rota se necessario\n\n"
        f"SEMANA 4 — Fechamento:\n"
        f"  - Concluir pendentes\n"
        f"  - Avaliar resultados\n"
        f"  - Planejar proximo mes\n\n"
        f"META PRINCIPAL DO MES:\n"
        f"  {texto[:80]}\n\n"
        f"INDICADORES:\n"
        f"  - Progresso semanal: []\n"
        f"  - Entregas realizadas: []\n"
        f"  - Satisfacao: []"
    )


def _organizar(texto: str) -> str:
    return (
        f"ORGANIZACAO\n"
        f"{'=' * 50}\n\n"
        f"Itens a organizar: {texto}\n\n"
        f"METODO GTD (GETTING THINGS DONE):\n\n"
        f"1. CAPTURAR\n"
        f"   Liste tudo o que esta na sua cabeca.\n\n"
        f"2. PROCESSAR\n"
        f"   Para cada item: e acao? Sim -> faca em 2min, delegue, ou agende.\n"
        f"   Nao -> arquive, descarte, ou coloque em lista de espera.\n\n"
        f"3. ORGANIZAR\n"
        f"   - Proximas acoes\n"
        f"   - Projetos (mais de uma acao)\n"
        f"   - Delegados (aguardando outros)\n"
        f"   - Calendario (datas fixas)\n\n"
        f"4. REVISAR\n"
        f"   Revisao semanal de todas as listas.\n\n"
        f"5. EXECUTAR\n"
        f"   Escolha a tarefa por: contexto, tempo disponivel, energia, prioridade.\n\n"
        f"Dica: use categorias como @casa, @escritorio, @computador, @ligacoes."
    )


def _dicas_produtividade(texto: str) -> str:
    return (
        f"DICAS DE PRODUTIVIDADE\n"
        f"{'=' * 50}\n\n"
        f"Contexto: {texto}\n\n"
        f"1. METODO POMODORO\n"
        f"   25 min de foco + 5 min de pausa. A cada 4 ciclos, pausa de 15-30 min.\n\n"
        f"2. MATRIZ EISENHOWER\n"
        f"   Urgente + Importante -> Faca agora\n"
        f"   Importante + Nao Urgente -> Agende\n"
        f"   Urgente + Nao Importante -> Delegue\n"
        f"   Nao Urgente + Nao Importante -> Elimine\n\n"
        f"3. REGRA DOS 2 MINUTOS\n"
        f"   Se leva menos de 2 min, faca agora.\n\n"
        f"4. EATING THE FROG\n"
        f"   Comece o dia pela tarefa mais dificil.\n\n"
        f"5. TIME BLOCKING\n"
        f"   Bloqueie horarios no calendario para cada tipo de tarefa.\n\n"
        f"6. LEI DE PARETO (80/20)\n"
        f"   80% dos resultados vêm de 20% dos esforços. Foque no que realmente importa.\n\n"
        f"Dica: escolha 1 ou 2 metodos e pratique por 30 dias."
    )


def get_tools():
    return [
        Tool("planejamento_diario", "Cria planejamento do dia",
             ["planejamento", "dia", "diario", "hoje"], _planejamento_diario),
        Tool("checklist", "Cria checklist de tarefas",
             ["checklist", "lista", "tarefas", "to-do", "afazeres"], _checklist),
        Tool("plano_semanal", "Cria plano da semana",
             ["semanal", "semana"], _plano_semanal),
        Tool("plano_mensal", "Cria plano do mes",
             ["mensal", "mes", "mês"], _plano_mensal),
        Tool("organizar", "Organiza tarefas com metodo GTD",
             ["organizar", "organizacao", "organização", "gtd", "metodo"], _organizar),
        Tool("dicas_produtividade", "Da dicas de produtividade",
             ["dica", "dicas", "produtividade", "como ser produtivo", "melhorar"], _dicas_produtividade),
    ]
