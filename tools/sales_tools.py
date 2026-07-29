"""
Ferramentas do agente Vendas.
"""

from tools.base import Tool


def _proposta(texto: str) -> str:
    return (
        f"PROPOSTA COMERCIAL\n"
        f"{'=' * 50}\n\n"
        f"Cliente/Projeto: {texto}\n\n"
        f"1. RESUMO EXECUTIVO\n"
        f"   Apresentacao da proposta para {texto}\n\n"
        f"2. OBJETIVO\n"
        f"   Entregar solucao completa que atenda as necessidades.\n\n"
        f"3. ESCOPO\n"
        f"   - Levantamento de requisitos\n"
        f"   - Planejamento\n"
        f"   - Execucao\n"
        f"   - Suporte pos-entrega\n\n"
        f"4. CRONOGRAMA\n"
        f"   Fase 1 (Semana 1-2): Diagnostico\n"
        f"   Fase 2 (Semana 3-4): Desenvolvimento\n"
        f"   Fase 3 (Semana 5): Entrega e ajustes\n\n"
        f"5. INVESTIMENTO\n"
        f"   Consulte condicoes comerciais.\n\n"
        f"6. PROXIMOS PASSOS\n"
        f"   Agendar reuniao para alinhamento final."
    )


def _orcamento(texto: str) -> str:
    return (
        f"ORCAMENTO\n"
        f"{'=' * 50}\n\n"
        f"Referencia: {texto}\n\n"
        f"ITEM                   | VALOR\n"
        f"{'-' * 50}\n"
        f"Consultoria            | R$ X.XXX,00\n"
        f"Materiais              | R$ XXX,00\n"
        f"Execucao               | R$ X.XXX,00\n"
        f"Suporte (30 dias)      | R$ XXX,00\n"
        f"{'-' * 50}\n"
        f"TOTAL                  | R$ X.XXX,XX\n\n"
        f"Formas de pagamento:\n"
        f"  - A vista: 5% de desconto\n"
        f"  - 3x sem juros\n"
        f"  - 6x com juros de 2%\n\n"
        f"Validade: 7 dias\n\n"
        f"Aguardamos seu retorno para darmos inicio!"
    )


def _followup(texto: str) -> str:
    return (
        f"FOLLOW-UP\n"
        f"{'=' * 50}\n\n"
        f"Cliente/Contexto: {texto}\n\n"
        f"DIA 1 — Agradecimento:\n"
        f"  \"Obrigado pelo contato! Fico a disposicao.\"\n\n"
        f"DIA 3 — Reforco:\n"
        f"  \"Pensou na proposta? Posso esclarecer duvidas.\"\n\n"
        f"DIA 7 — Novo valor:\n"
        f"  \"Temos uma condicao especial esta semana.\"\n\n"
        f"DIA 14 — Prova social:\n"
        f"  \"Clientes que escolheram nossa solucao tiveram X% de resultado.\"\n\n"
        f"DIA 30 — Reengajamento:\n"
        f"  \"Gostaria de saber se ainda ha interesse. Posso ajudar?\"\n\n"
        f"Dica: personalize cada contato com info da conversa anterior."
    )


def _quebra_objecoes(texto: str) -> str:
    return (
        f"QUEBRA DE OBJECOES\n"
        f"{'=' * 50}\n\n"
        f"Objecao: {texto}\n\n"
        f"1. \"E caro\"\n"
        f"   Resposta: Compare com o valor entregue. Mostre ROI.\n\n"
        f"2. \"Preciso pensar\"\n"
        f"   Resposta: Entendo! Posso ajudar com alguma duvida especifica?\n\n"
        f"3. \"Nao tenho tempo\"\n"
        f"   Resposta: Nosso processo e rapido e otimizado para quem tem agenda cheia.\n\n"
        f"4. \"Ja tenho fornecedor\"\n"
        f"   Resposta: Que bom! Podemos ser uma alternativa complementar.\n\n"
        f"5. \"Nao e prioridade agora\"\n"
        f"   Resposta: Entendo. Posso deixar uma proposta para quando for.\n\n"
        f"Tecnica: sinta a objecao, valide o sentimento, apresente contra-argumento com prova."
    )


def _negociacao(texto: str) -> str:
    return (
        f"NEGOCIACAO\n"
        f"{'=' * 50}\n\n"
        f"Contexto: {texto}\n\n"
        f"Tecnicas de negociacao:\n\n"
        f"1. BATNA (Melhor Alternativa)\n"
        f"   Tenha sempre uma alternativa caso nao feche.\n\n"
        f"2. Escuta Ativa\n"
        f"   Repita o que o cliente disse para mostrar que entendeu.\n\n"
        f"3. Troca de Concessoes\n"
        f"   \"Se voce fechar hoje, consigo incluir X.\"\n\n"
        f"4. Silencio Estrategico\n"
        f"   Depois de fazer uma proposta, fique em silencio.\n\n"
        f"5. Ancoragem\n"
        f"   Apresente primeiro o pacote mais completo para ancorar o valor.\n\n"
        f"Script sugerido:\n"
        f"  \"Entendo seu ponto. E se eu pudesse oferecer [concessao],\n"
        f"   voce fecharia hoje?\""
    )


def _fechamento(texto: str) -> str:
    return (
        f"FECHAMENTO\n"
        f"{'=' * 50}\n\n"
        f"Contexto: {texto}\n\n"
        f"Tecnicas de fechamento:\n\n"
        f"1. Fechamento Direto\n"
        f"   \"Posso preparar o contrato?\"\n\n"
        f"2. Fechamento Presuntivo\n"
        f"   \"Vou preparar a nota fiscal. Prefere email ou WhatsApp?\"\n\n"
        f"3. Fechamento por Alternativa\n"
        f"   \"Prefere o pagamento avista ou parcelado?\"\n\n"
        f"4. Fechamento por Urgencia\n"
        f"   \"Esta promocao vai ate sexta. Quer garantir?\"\n\n"
        f"5. Fechamento por Resumo\n"
        f"   \"Entao ficamos assim: [resumo da proposta]. Pode confirmar?\"\n\n"
        f"Dica: depois de perguntar, fique em silencio e aguarde a resposta."
    )


def get_tools():
    return [
        Tool("proposta_comercial", "Cria proposta comercial detalhada",
             ["proposta", "comercial", "proposta comercial"], _proposta),
        Tool("orcamento", "Cria orcamento com precos e prazos",
             ["orcamento", "orçamento", "preco", "precos", "custo"], _orcamento),
        Tool("follow_up", "Cria sequencia de follow-up para cliente",
             ["follow", "seguimento", "acompanhamento", "contato"], _followup),
        Tool("quebra_objecoes", "Prepara argumentos para quebrar objeccoes",
             ["objecao", "objeção", "argumento", "resistencia"], _quebra_objecoes),
        Tool("negociacao", "Tecnicas e scripts de negociacao",
             ["negociacao", "negociação", "barganha", "acordo"], _negociacao),
        Tool("fechamento", "Tecnicas de fechamento de venda",
             ["fechamento", "fechar", "fecho", "confirmacao"], _fechamento),
    ]
