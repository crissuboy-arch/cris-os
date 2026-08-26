"""
CeoMode — Diretor de Operações pessoal do CRIS OS.

Transforma um objetivo grande da Cris em um plano executável:
  1. Entender o objetivo
  2. Quebrar em fases
  3. Criar tarefas automaticamente
  4. Identificar dependencias
  5. Escolher os agentes ideais
  6. Delegar automaticamente
  7. Acompanhar progresso
  8. Atualizar memoria
  9. Gerar relatorios
 10. Pedir confirmacao apenas para acoes sensiveis

Integra com: MemorySystem, TaskManager, ProjectManager, Telegram e
AgentOrchestrator (via campo `agente` nas tarefas).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from repositories.objetivo_repo import ObjetivoRepository
from repositories.dependencia_repo import DependenciaRepository
from services.project_manager import ProjectManager
from services.task_manager import TaskManager

logger = logging.getLogger(__name__)

# Catalogo de agentes conhecidos -> dominio (usado para escolher o ideal)
CATALOGO_AGENTES = {
    "pesquisador": "pesquisa, analise, mercado, concorrentes, tendencias",
    "programador": "codigo, desenvolvimento, site, saas, automacao",
    "marketing": "campanhas, anuncios, trafego, divulgacao",
    "social-media": "conteudo, redes sociais, posts, legenda, criativos",
    "copywriter": "copy, landing page, texto de vendas, conversao",
    "vendas": "prospecao, propostas, orcamento, negociacao, fechamento",
    "atendimento": "suporte, atendimento, pos-venda, clientes",
    "financeiro": "preco, custo, margem, precificacao, financeiro",
    "secretary": "rotina, agenda, organizacao, lembretes, logistica",
    "produtividade": "rotina, prioridades, planejamento pessoal",
    "prospector": "prospecao, leads, prospectar, encontrar clientes, busca de clientes",
}


class CeoMode:
    """Diretor de Operacoes: de objetivo bruto a plano executavel."""

    def __init__(self, task_manager: TaskManager | None = None,
                 project_manager: ProjectManager | None = None,
                 memory=None, agentes: dict[str, str] | None = None) -> None:
        self.tasks = task_manager or TaskManager()
        self.projects = project_manager or ProjectManager()
        self.memory = memory
        self.objetivos = ObjetivoRepository()
        self.deps = DependenciaRepository()
        self.agentes = agentes or dict(CATALOGO_AGENTES)

    # ------------------------------------------------------------------
    #  1. Entender o objetivo
    # ------------------------------------------------------------------

    def entender(self, objetivo: str) -> dict:
        """Extrai tipo, projeto, meta numerica, unidade e mercado."""
        t = objetivo.strip()
        texto = t.lower()

        if "saas" in texto or "software" in texto:
            tipo = "saas"
        elif re.search(r"prospectar|prospecção|prospeccao|encontrar\s+(?:\d+\s+)?clientes?|buscar\s+(?:\d+\s+)?leads?|gerar\s+leads?", texto):
            tipo = "prospecao"
        elif "lançar" in texto or "lancar" in texto or "lançamento" in texto or "lancamento" in texto:
            tipo = "lancamento"
        elif "vender" in texto or "venda" in texto or "vendas" in texto:
            tipo = "vendas"
        elif "criar" in texto:
            tipo = "criacao"
        else:
            tipo = "geral"

        m_num = re.search(r"(\d[\d.]*)", texto)
        numero = float(m_num.group(1).replace(".", "")) if m_num else None

        m_mercado = re.search(r"(?:em|para|no|na)\s+(portugal|brasil|espanha|europa|usa|eua|mundo)", texto)
        mercado = m_mercado.group(1) if m_mercado else ""

        m_unidade = re.search(
            r"(?:vender\s+\d+\s+|comprar\s+\d+\s+)([a-záéíóúãõç]+)",
            texto,
        )
        unidade = m_unidade.group(1) if m_unidade else ""
        if not unidade:
            m_unid = re.search(r"(?:encontrar|buscar|prospectar|conseguir|fechar)\s+\d+\s+(clientes|leads)", texto)
            unidade = m_unid.group(1) if m_unid else ""

        # Nome do projeto: palavra-chave reconhecida ou termo apos o verbo
        projetos_conhecidos = {
            "scalaflow": "ScalaFlow", "zavix": "Zavix.online",
            "vitrinepro": "VitrinePro", "pinklogic": "PinkLogic",
            "mkvideos": "mkVideos", "chaveiros": "Chaveiros",
        }
        projeto = ""
        for chave, nome in projetos_conhecidos.items():
            if chave in texto:
                projeto = nome
                break
        if not projeto and tipo == "saas":
            m_saas = re.search(r"saas\s+(?:para|de|pra)?\s*([a-záéíóúãõç]+)", texto)
            projeto = f"SaaS {m_saas.group(1).title()}" if m_saas else "SaaS"
        if not projeto:
            m_proj = re.search(r"(?:lan[çc]ar|o projeto|criar)\s+(?:o\s+|um\s+|uma\s+)?([a-z][a-z0-9.]*)", texto)
            if m_proj:
                projeto = m_proj.group(1).title()

        return {
            "texto": t,
            "tipo": tipo,
            "projeto": projeto or "Novo Projeto",
            "numero": numero,
            "unidade": unidade,
            "mercado": mercado,
        }

    # ------------------------------------------------------------------
    #  2. Quebrar em fases + 5. escolher agentes + 6. delegar
    # ------------------------------------------------------------------

    def _template(self, entendido: dict) -> dict:
        """Monta o plano (fases + tarefas + agentes) para o objetivo."""
        tipo = entendido["tipo"]
        projeto = entendido["projeto"]
        n = entendido["numero"]
        unidade = entendido["unidade"]
        mercado = entendido["mercado"]

        if tipo == "lancamento":
            return self._template_lancamento(projeto)
        if tipo == "vendas":
            return self._template_vendas(projeto, n, unidade, mercado)
        if tipo == "prospecao":
            return self._template_prospecao(projeto, n, unidade, mercado)
        if tipo == "saas":
            return self._template_saas(projeto)
        if tipo == "criacao":
            return self._template_criacao(projeto)
        return self._template_geral(projeto)

    def _template_lancamento(self, projeto: str) -> dict:
        fase1 = [
            ("Pesquisar mercado e concorrentes do " + projeto,
             "pesquisador", "alta", 3, [], False),
            ("Definir publico-alvo e proposta de valor",
             "pesquisador", "media", 2, [1], False),
        ]
        fase2 = [
            ("Preparar produto e material do " + projeto,
             "programador", "alta", 5, [], False),
            ("Escrever copy de vendas e materiais do " + projeto,
             "copywriter", "media", 3, [1], False),
        ]
        fase3 = [
            ("Criar campanha de anuncios para o " + projeto,
             "marketing", "alta", 4, [2, 4], True),
            ("Planejar e agendar conteudo nas redes sociais",
             "social-media", "media", 3, [4], False),
        ]
        fase4 = [
            ("Executar o lancamento do " + projeto,
             "marketing", "alta", 1, [3, 5], False),
        ]
        fase5 = [
            ("Acompanhar metricas e atender leads pos-lancamento",
             "atendimento", "media", 5, [7], False),
            ("Revisar resultados e planejar proxima rodada",
             "financeiro", "baixa", 2, [8], False),
        ]
        return {
            "nome": f"Lancamento {projeto}",
            "riscos": [
                "Produto pode nao gerar demanda suficiente",
                "Anuncios podem estourar o orcamento",
                "Prazo de lancamento pode escorregar",
            ],
            "fases": [
                ("1. Pesquisa e Validacao", fase1),
                ("2. Preparacao do Produto", fase2),
                ("3. Marketing e Conteudo", fase3),
                ("4. Lancamento", fase4),
                ("5. Pos-lancamento", fase5),
            ],
        }

    def _template_vendas(self, projeto: str, n, unidade: str, mercado: str) -> dict:
        meta = f"{int(n)} {unidade}" if n and unidade else f"{int(n) if n else ''} unidades"
        alvo = f" em {mercado}" if mercado else ""
        fase1 = [
            (f"Pesquisar mercado de {unidade} {alvo}".replace("  ", " ").strip(),
             "pesquisador", "alta", 3, [], False),
            ("Definir preco e margem por unidade",
             "financeiro", "alta", 2, [1], False),
        ]
        fase2 = [
            ("Garantir estoque/producao para a meta de " + meta,
             "secretary", "alta", 5, [], False),
        ]
        fase3 = [
            (f"Criar campanha de anuncios para vender {meta}{alvo}",
             "marketing", "alta", 4, [2], True),
            ("Criar conteudo e criativos para as redes",
             "social-media", "media", 3, [4], False),
        ]
        fase4 = [
            ("Atender pedidos e leads de vendas",
             "atendimento", "alta", 3, [3, 5], False),
        ]
        fase5 = [
            ("Enviar e acompanhar entregas",
             "secretary", "media", 4, [6], False),
            ("Coletar avaliacoes e gerar recompra",
             "vendas", "baixa", 3, [7], False),
        ]
        return {
            "nome": f"Vender {meta}{alvo}",
            "riscos": [
                "Estoque insuficiente para atingir a meta",
                "Custo de aquisicao de cliente pode ser alto",
                "Logistica de entrega pode atrasar",
            ],
            "fases": [
                ("1. Pesquisa de Mercado", fase1),
                ("2. Preparacao do Produto", fase2),
                ("3. Marketing e Trafego", fase3),
                ("4. Vendas", fase4),
                ("5. Entrega e Pos-venda", fase5),
            ],
        }

    def _template_prospecao(self, projeto: str, n, unidade: str, mercado: str) -> dict:
        meta = f"{int(n)} {unidade}" if n and unidade else ("unidades" if n else "")
        alvo = f" em {mercado}" if mercado else ""
        tarefa_base = f"Prospectar {meta}{alvo}".replace("  ", " ").strip()
        fase1 = [
            (f"{tarefa_base} (buscar e salvar leads)",
             "prospector", "alta", 5, [], False),
            ("Revisar leads encontrados e qualificar",
             "prospector", "media", 2, [1], False),
        ]
        fase2 = [
            ("Redesenhar site dos leads qualificados",
             "prospector", "media", 4, [2], False),
            ("Enviar propostas para os leads",
             "prospector", "alta", 3, [3], False),
        ]
        fase3 = [
            ("Rodar follow-ups de leads sem resposta",
             "prospector", "media", 4, [4], False),
            ("Gerar contratos e registrar fechamentos",
             "prospector", "alta", 3, [5], True),
        ]
        return {
            "nome": "Prospecao de clientes",
            "riscos": [
                "Poucos leads qualificados no nicho/regiao",
                "Propostas podem nao converter no prazo",
                "Fechamentos exigem confirmacao da Cris",
            ],
            "fases": [
                ("1. Prospeccao", fase1),
                ("2. Redesign e Propostas", fase2),
                ("3. Follow-up e Contratos", fase3),
            ],
        }

    def _template_saas(self, projeto: str) -> dict:
        fase1 = [
            ("Pesquisar mercado de imobiliarias e concorrentes",
             "pesquisador", "alta", 4, [], False),
            ("Definir proposta de valor e precificacao",
             "financeiro", "alta", 3, [1], False),
        ]
        fase2 = [
            ("Criar MVP do " + projeto,
             "programador", "alta", 10, [2], False),
            ("Implementar automacoes e integracoes",
             "programador", "media", 6, [3], False),
        ]
        fase3 = [
            ("Criar landing page e copy do " + projeto,
             "copywriter", "alta", 4, [2], False),
            ("Planejar lancamento e conteudo",
             "marketing", "media", 3, [6], False),
        ]
        fase4 = [
            ("Prospectar clientes (imobiliarias)",
             "vendas", "alta", 4, [4, 7], False),
            ("Criar campanha de aquisicao de clientes",
             "marketing", "media", 4, [7], True),
        ]
        fase5 = [
            ("Suporte e onboarding de clientes",
             "atendimento", "media", 5, [8], False),
        ]
        return {
            "nome": projeto,
            "riscos": [
                "MVP pode crescer alem do escopo",
                "Churn de clientes no inicio",
                "Custo de aquisicao alto para SaaS",
            ],
            "fases": [
                ("1. Pesquisa e Validacao", fase1),
                ("2. Desenvolvimento", fase2),
                ("3. Lancamento", fase3),
                ("4. Aquisicao de Clientes", fase4),
                ("5. Operacao", fase5),
            ],
        }

    def _template_criacao(self, projeto: str) -> dict:
        fase1 = [
            ("Pesquisar o mercado do " + projeto,
             "pesquisador", "alta", 3, [], False),
            ("Definir escopo e entregas",
             "financeiro", "alta", 2, [1], False),
        ]
        fase2 = [
            ("Produzir as entregas principais do " + projeto,
             "programador", "alta", 7, [2], False),
        ]
        fase3 = [
            ("Criar material de divulgacao",
             "social-media", "media", 3, [3], False),
        ]
        fase4 = [
            ("Revisar e entregar o " + projeto,
             "secretary", "media", 2, [4], False),
        ]
        return {
            "nome": projeto,
            "riscos": [
                "Escopo pode crescer durante a execucao",
                "Prazos podem escorregar",
            ],
            "fases": [
                ("1. Pesquisa e Escopo", fase1),
                ("2. Execucao", fase2),
                ("3. Divulgacao", fase3),
                ("4. Revisao e Entrega", fase4),
            ],
        }

    def _template_geral(self, projeto: str) -> dict:
        fase1 = [
            ("Pesquisar e detalhar o objetivo do " + projeto,
             "pesquisador", "alta", 3, [], False),
            ("Definir plano e cronograma",
             "secretary", "alta", 2, [1], False),
        ]
        fase2 = [
            ("Executar as principais entregas",
             "programador", "alta", 7, [2], False),
        ]
        fase3 = [
            ("Revisar resultados e ajustar",
             "financeiro", "media", 3, [3], False),
        ]
        return {
            "nome": projeto,
            "riscos": [
                "Objetivo amplo pode gerar escopo grande",
                "Prioridades podem mudar durante a execucao",
            ],
            "fases": [
                ("1. Pesquisa e Planejamento", fase1),
                ("2. Execucao", fase2),
                ("3. Revisao", fase3),
            ],
        }

    # ------------------------------------------------------------------
    #  Planejamento completo (sem escrever no banco)
    # ------------------------------------------------------------------

    def planejar(self, objetivo: str) -> dict:
        """Gera o plano completo: fases, tarefas, agentes, cronograma, riscos."""
        entendido = self.entender(objetivo)
        template = self._template(entendido)

        tarefas: list[dict] = []
        num = 0
        fase_tarefas: list[dict] = []
        hoje = datetime.now().date()

        for idx, (fase_nome, itens) in enumerate(template["fases"], 1):
            num_fase = 0
            for titulo, agente, prioridade, dias, deps, sensivel in itens:
                num += 1
                num_fase += 1
                tarefas.append({
                    "num": num,
                    "fase": idx,
                    "fase_nome": fase_nome,
                    "titulo": titulo,
                    "agente": agente,
                    "prioridade": prioridade,
                    "prazo_dias": dias,
                    "prazo": (hoje + timedelta(days=num_fase * dias)).isoformat(),
                    "depende_de": deps,
                    "sensivel": sensivel,
                    "status": "pendente",
                })

        inicio = hoje.isoformat()
        fim = (hoje + timedelta(days=sum(t["prazo_dias"] for t in tarefas))).isoformat()

        proxima_acao = tarefas[0]["titulo"] if tarefas else ""

        return {
            "objetivo": entendido["texto"],
            "tipo": entendido["tipo"],
            "projeto": entendido["projeto"],
            "meta": {
                "numero": entendido["numero"],
                "unidade": entendido["unidade"],
                "mercado": entendido["mercado"],
            },
            "plano": template["nome"],
            "fases": [
                {"id": i, "nome": nome}
                for i, (nome, _) in enumerate(template["fases"], 1)
            ],
            "tarefas": tarefas,
            "cronograma": {"inicio": inicio, "fim": fim},
            "riscos": template["riscos"],
            "proxima_acao": proxima_acao,
            "status": "planejado",
            "confirmacoes_necessarias": [
                t for t in tarefas if t["sensivel"]
            ],
        }

    # ------------------------------------------------------------------
    #  3. Criar tarefas + 4. dependencias + 6. delegar + 8. memoria
    # ------------------------------------------------------------------

    def executar(self, objetivo: str, usuario_id: str,
                 confirmado: bool = False) -> dict:
        """Entende, planeja e materializa tudo no banco.

        Acoes sensiveis so sao delegadas quando `confirmado=True`.
        """
        plano = self.planejar(objetivo)

        # Cria/recupera o projeto
        proj = None
        for p in self.projects.listar_todos(usuario_id):
            if p["nome"].lower() == plano["projeto"].lower():
                proj = p
                break
        if proj is None:
            proj = self.projects.criar(usuario_id, plano["projeto"],
                                       descricao=plano["objetivo"],
                                       contexto=plano["plano"])

        # Cria as tarefas e registra dependencias
        mapa_nums: dict[int, int] = {}
        for t in plano["tarefas"]:
            if t["sensivel"] and not confirmado:
                continue  # sensivel so e criada com confirmacao
            tarefa = self.tasks.criar(
                usuario_id, t["titulo"],
                prioridade=t["prioridade"],
                prazo=t["prazo"],
                agente=t["agente"],
                projeto_id=proj["id"],
            )
            mapa_nums[t["num"]] = tarefa["id"]
            t["tarefa_id"] = tarefa["id"]

        for t in plano["tarefas"]:
            tarefa_id = mapa_nums.get(t["num"])
            if not tarefa_id:
                continue
            for dep in t.get("depende_de", []):
                dep_id = mapa_nums.get(dep)
                if dep_id:
                    self.deps.criar(usuario_id, tarefa_id, dep_id)

        # Registra o objetivo
        oid = self.objetivos.criar(
            usuario_id, plano["objetivo"], plano["tipo"],
            proj["id"], plano,
        )
        plano["objetivo_id"] = oid
        plano["projeto_id"] = proj["id"]

        # 8. Atualiza memoria
        if self.memory:
            try:
                self.memory.remember(
                    f"Objetivo da Cris: {plano['objetivo']} "
                    f"(projeto {plano['projeto']}, status {plano['status']})",
                    user_id=usuario_id, workspace="default",
                    origin="ceo_mode", agent="orquestrador",
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("Falha ao salvar memoria do objetivo: %s", exc)

        logger.info("CEO Mode: objetivo '%s' criado (id=%d, projeto=%s, tarefas=%d)",
                     plano["objetivo"], oid, plano["projeto"], len(mapa_nums))
        return plano

    # ------------------------------------------------------------------
    #  7. Acompanhar progresso
    # ------------------------------------------------------------------

    def progresso(self, objetivo_id: int) -> dict:
        """Calcula progresso das tarefas de um objetivo."""
        objetivo = self.objetivos.abrir(objetivo_id)
        if not objetivo:
            return {"erro": "Objetivo nao encontrado"}
        plano = objetivo.get("plano") or {}
        tarefas_plan = plano.get("tarefas", [])

        ids = [t.get("tarefa_id") for t in tarefas_plan if t.get("tarefa_id")]
        reais: dict[int, dict] = {}
        for tid in ids:
            t = self.tasks.abrir(tid)
            if t:
                reais[tid] = t

        concluidas = sum(1 for t in tarefas_plan
                         if t.get("tarefa_id") in reais
                         and reais[t["tarefa_id"]]["status"] == "concluida")
        total = len([t for t in tarefas_plan if t.get("tarefa_id")])
        pct = round((concluidas / total) * 100) if total else 0

        return {
            "objetivo_id": objetivo_id,
            "total_tarefas": total,
            "concluidas": concluidas,
            "pendentes": total - concluidas,
            "progresso_pct": pct,
        }

    # ------------------------------------------------------------------
    #  9. Relatorio + proxima acao
    # ------------------------------------------------------------------

    def relatorio(self, objetivo_id: int) -> dict:
        """Relatorio completo do objetivo."""
        objetivo = self.objetivos.abrir(objetivo_id)
        if not objetivo:
            return {"erro": "Objetivo nao encontrado"}
        plano = objetivo.get("plano") or {}
        prog = self.progresso(objetivo_id)

        tarefas = []
        for t in plano.get("tarefas", []):
            real = self.tasks.abrir(t["tarefa_id"]) if t.get("tarefa_id") else None
            tarefas.append({
                "titulo": t["titulo"],
                "agente": t["agente"],
                "prioridade": t["prioridade"],
                "prazo": t["prazo"],
                "status": real["status"] if real else t.get("status", "pendente"),
                "sensivel": t.get("sensivel", False),
                "tarefa_id": t.get("tarefa_id"),
            })

        pendentes = [t for t in tarefas if t["status"] == "pendente"]
        proxima_acao = pendentes[0]["titulo"] if pendentes else "Objetivo concluido!"

        return {
            "objetivo": plano.get("objetivo", objetivo["objetivo"]),
            "tipo": plano.get("tipo", objetivo.get("tipo")),
            "projeto": plano.get("projeto", ""),
            "plano": plano.get("plano", ""),
            "fases": plano.get("fases", []),
            "cronograma": plano.get("cronograma", {}),
            "riscos": plano.get("riscos", []),
            "tarefas": tarefas,
            "progresso": prog,
            "proxima_acao": proxima_acao,
            "status": objetivo.get("status"),
            "objetivo_id": objetivo_id,
        }

    def proxima_acao(self, objetivo_id: int) -> str:
        """Retorna a proxima acao pendente (respeitando dependencias)."""
        objetivo = self.objetivos.abrir(objetivo_id)
        if not objetivo:
            return "Objetivo nao encontrado."
        plano = objetivo.get("plano") or {}

        dependencias = self.deps.por_usuario(objetivo["usuario_id"])
        bloco_map: dict[int, set[int]] = {}
        for d in dependencias:
            bloco_map.setdefault(d["tarefa_id"], set()).add(d["depende_de"])

        concluidos = set()
        for t in plano.get("tarefas", []):
            tid = t.get("tarefa_id")
            if tid and (self.tasks.abrir(tid) or {}).get("status") == "concluida":
                concluidos.add(tid)

        for t in plano.get("tarefas", []):
            tid = t.get("tarefa_id")
            if not tid:
                continue
            real = self.tasks.abrir(tid)
            if real and real["status"] != "pendente":
                continue
            deps = bloco_map.get(tid, set())
            if deps and not deps.issubset(concluidos):
                continue
            return t["titulo"]
        return "Objetivo concluido!"

    # ------------------------------------------------------------------
    #  Utilitarios
    # ------------------------------------------------------------------

    def listar(self, usuario_id: str) -> list[dict]:
        return self.objetivos.por_usuario(usuario_id)

    def confirmacoes_pendentes(self, objetivo_id: int) -> list[dict]:
        """Lista acoes sensiveis do objetivo que ainda precisam de confirmacao."""
        objetivo = self.objetivos.abrir(objetivo_id)
        if not objetivo:
            return []
        plano = objetivo.get("plano") or {}
        pendentes = []
        for t in plano.get("tarefas", []):
            if not t.get("sensivel"):
                continue
            tid = t.get("tarefa_id")
            real = self.tasks.abrir(tid) if tid else None
            if real is None or real["status"] == "pendente":
                pendentes.append({
                    "titulo": t["titulo"],
                    "agente": t["agente"],
                    "tarefa_id": tid,
                })
        return pendentes
