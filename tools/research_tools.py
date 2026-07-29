"""
Ferramentas do agente Pesquisador.
"""

from tools.base import Tool


def _pesquisar_web(texto: str) -> str:
    return (
        f"PESQUISA WEB\n"
        f"{'=' * 50}\n\n"
        f"Termo pesquisado: {texto}\n\n"
        f"Resultados da pesquisa:\n\n"
        f"1. [Titulo do resultado 1]\n"
        f"   URL: exemplo.com/artigo1\n"
        f"   Resumo: Pagina com informacoes relevantes sobre {texto[:60]}...\n\n"
        f"2. [Titulo do resultado 2]\n"
        f"   URL: exemplo.com/artigo2\n"
        f"   Resumo: Artigo aprofundado sobre o tema.\n\n"
        f"3. [Titulo do resultado 3]\n"
        f"   URL: exemplo.com/artigo3\n"
        f"   Resumo: Analise e dados atualizados.\n\n"
        f"Nota: Validacao e curadoria sao recomendadas antes de usar os dados."
    )


def _resumir(texto: str) -> str:
    return (
        f"RESUMO\n"
        f"{'=' * 50}\n\n"
        f"Texto original: {texto}\n\n"
        f"RESUMO EXECUTIVO:\n"
        f"  O texto aborda {texto[:80]}...\n\n"
        f"PONTOS PRINCIPAIS:\n"
        f"  - Ideia central apresentada\n"
        f"  - Dados e evidencias citados\n"
        f"  - Conclusao do autor\n\n"
        f"PALAVRAS-CHAVE:\n"
        f"  {', '.join(texto.split()[:5])}\n\n"
        f"RESUMO (1 paragrafo):\n"
        f"  {texto[:200]}...\n\n"
        f"Resumo gerado com base no texto fornecido."
    )


def _analisar(texto: str) -> str:
    return (
        f"ANALISE\n"
        f"{'=' * 50}\n\n"
        f"Tema analisado: {texto}\n\n"
        f"CONTEXTO:\n"
        f"  Analise aprofundada sobre {texto[:80]}...\n\n"
        f"PONTOS FORTES:\n"
        f"  - Relevância do tema\n"
        f"  - Aplicacao pratica\n"
        f"  - Potencial de crescimento\n\n"
        f"PONTOS FRACOS:\n"
        f"  - Concorrencia estabelecida\n"
        f"  - Barreira de entrada\n"
        f"  - Complexidade operacional\n\n"
        f"OPORTUNIDADES:\n"
        f"  - Tendencia de mercado favoravel\n"
        f"  - Publico carente de solucoes\n\n"
        f"RECOMENDACAO:\n"
        f"  Com base na analise, recomenda-se aprofundamento no tema."
    )


def _comparar(texto: str) -> str:
    return (
        f"COMPARACAO\n"
        f"{'=' * 50}\n\n"
        f"Itens comparados: {texto}\n\n"
        f"CRITERIO        | ITEM A                    | ITEM B\n"
        f"{'-' * 60}\n"
        f"Preco           | R$ X                      | R$ Y\n"
        f"Qualidade       | Alta                      | Media\n"
        f"Suporte         | 24h                       | 12h\n"
        f"Garantia        | 12 meses                  | 6 meses\n"
        f"Avaliacao       | 4.5/5                     | 4.0/5\n\n"
        f"VANTAGEM ITEM A:\n"
        f"  Melhor custo-beneficio no longo prazo.\n\n"
        f"VANTAGEM ITEM B:\n"
        f"  Mais acessivel no curto prazo.\n\n"
        f"RECOMENDACAO:\n"
        f"  Depende da prioridade do usuario. Se for qualidade, Item A."
    )


def _concorrentes(texto: str) -> str:
    return (
        f"ANALISE DE CONCORRENTES\n"
        f"{'=' * 50}\n\n"
        f"Setor/Mercado: {texto}\n\n"
        f"PRINCIPAIS CONCORRENTES:\n\n"
        f"1. Concorrente A\n"
        f"   Diferencial: Preco baixo\n"
        f"   Fraqueza: Suporte limitado\n"
        f"   Participacao: 30%\n\n"
        f"2. Concorrente B\n"
        f"   Diferencial: Qualidade premium\n"
        f"   Fraqueza: Preco alto\n"
        f"   Participacao: 25%\n\n"
        f"3. Concorrente C\n"
        f"   Diferencial: Inovacao\n"
        f"   Fraqueza: Marca pouco conhecida\n"
        f"   Participacao: 15%\n\n"
        f"OPORTUNIDADES PARA VOCE:\n"
        f"  - Nicho mal atendido\n"
        f"  - Diferencial via atendimento\n"
        f"  - Precificacao estrategica"
    )


def _tendencias(texto: str) -> str:
    return (
        f"TENDENCIAS\n"
        f"{'=' * 50}\n\n"
        f"Setor: {texto}\n\n"
        f"TENDENCIAS ATUAIS:\n\n"
        f"1. Automacao e IA\n"
        f"   Impacto: Otimizacao de processos e reducao de custos.\n\n"
        f"2. Personalizacao em massa\n"
        f"   Impacto: Experiencia unica para cada cliente.\n\n"
        f"3. Sustentabilidade\n"
        f"   Impacto: Consumidores preferem marcas responsaveis.\n\n"
        f"4. Omnichannel\n"
        f"   Impacto: Integracao de canais fisicos e digitais.\n\n"
        f"5. Dados como ativo\n"
        f"   Impacto: Decisoes baseadas em dados.\n\n"
        f"RECOMENDACAO:\n"
        f"  Invista em pelo menos 2 dessas tendencias para se manter relevante."
    )


def get_tools():
    return [
        Tool("pesquisar_web", "Pesquisa informacoes na web sobre um tema",
             ["pesquisar", "pesquisa", "buscar", "busca", "procurar", "google"], _pesquisar_web),
        Tool("resumir", "Resume texto ou artigo",
             ["resumir", "resumo", "sumario", "sumarizar", "sintese"], _resumir),
        Tool("analisar", "Analisa tema, mercado ou situacao",
             ["analisar", "analise", "análise", "diagnostico"], _analisar),
        Tool("comparar", "Compara dois ou mais itens",
             ["comparar", "comparacao", "comparação", "vs", "versus", "diferenca"], _comparar),
        Tool("analisar_concorrentes", "Analisa concorrencia de um setor",
             ["concorrente", "concorrencia", "competidor", "mercado", "setor"], _concorrentes),
        Tool("tendencias", "Levanta tendencias de um setor",
             ["tendencia", "tendência", "futuro", "novidades", "inovacao"], _tendencias),
    ]
