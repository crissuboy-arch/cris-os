"""
Ferramentas do agente Atendimento.
"""

from tools.base import Tool


def _responder_cliente(texto: str) -> str:
    return (
        f"RESPOSTA AO CLIENTE\n"
        f"{'=' * 50}\n\n"
        f"Mensagem do cliente: {texto}\n\n"
        f"Resposta:\n"
        f"  Ola! Tudo bem?\n\n"
        f"  Obrigado pelo seu contato. Recebi sua mensagem sobre:\n"
        f"  \"{texto[:100]}...\"\n\n"
        f"  Vou verificar e ja retorno com mais informacoes.\n\n"
        f"  Fico a disposicao!\n\n"
        f"Atenciosamente,\n"
        f"Equipe de Atendimento"
    )


def _responder_reclamacao(texto: str) -> str:
    return (
        f"RESPOSTA A RECLAMACAO\n"
        f"{'=' * 50}\n\n"
        f"Reclamacao: {texto}\n\n"
        f"Resposta:\n"
        f"  Ola [Nome],\n\n"
        f"  Lamentamos profundamente pelo ocorrido.\n"
        f"  Entendemos sua frustracao com \"{texto[:100]}...\"\n\n"
        f"  Ja acionamos nosso time para resolver o mais rapido possivel.\n\n"
        f"  Protocolo: #[GERAR]\n"
        f"  Prazo de solucao: ate 48h uteis\n\n"
        f"  Pedimos desculpas pelo inconveniente.\n"
        f"  Estamos aqui para ajudar.\n\n"
        f"Atenciosamente,\n"
        f"Equipe de Atendimento"
    )


def _responder_duvida(texto: str) -> str:
    return (
        f"RESPOSTA A DUVIDA\n"
        f"{'=' * 50}\n\n"
        f"Du vida: {texto}\n\n"
        f"Resposta:\n"
        f"  Ola! Obrigado pela pergunta.\n\n"
        f"  Sobre \"{texto[:100]}...\":\n"
        f"  - Sim, oferecemos esse servico\n"
        f"  - O prazo medio e de X dias uteis\n"
        f"  - O valor pode variar conforme a necessidade\n\n"
        f"  Se tiver mais duvidas, e so chamar!\n\n"
        f"Atenciosamente,\n"
        f"Equipe de Atendimento"
    )


def _responder_orcamento(texto: str) -> str:
    return (
        f"RESPOSTA A ORCAMENTO\n"
        f"{'=' * 50}\n\n"
        f"Solicitacao: {texto}\n\n"
        f"Resposta:\n"
        f"  Ola! Tudo bem?\n\n"
        f"  Recebemos sua solicitacao de orcamento.\n"
        f"  Vamos preparar uma proposta personalizada para voce.\n\n"
        f"  Pode nos informar:\n"
        f"  1. Qual a quantidade desejada?\n"
        f"  2. Qual o prazo desejado?\n"
        f"  3. Tem alguma especificacao especial?\n\n"
        f"  Assim que tivermos essas informacoes, enviamos o orcamento.\n\n"
        f"Atenciosamente,\n"
        f"Equipe de Atendimento"
    )


def _atendimento_humanizado(texto: str) -> str:
    return (
        f"ATENDIMENTO HUMANIZADO\n"
        f"{'=' * 50}\n\n"
        f"Contexto: {texto}\n\n"
        f"Resposta humanizada:\n"
        f"  Ola [Nome], tudo bem com voce?\n\n"
        f"  Recebi sua mensagem e quero te ajudar pessoalmente.\n"
        f"  Sei que cada caso e unico, e vou fazer questao de\n"
        f"  encontrar a melhor solucao para voce.\n\n"
        f"  Pode me contar mais sobre \"{texto[:100]}...\"?\n"
        f"  Assim consigo entender melhor sua necessidade.\n\n"
        f"  Fique a vontade, estou aqui para o que precisar!\n\n"
        f"  Com carinho,\n"
        f"[Seu Nome]"
    )


def get_tools():
    return [
        Tool("responder_cliente", "Responde cliente de forma padrao",
             ["responder", "cliente", "contato", "mensagem"], _responder_cliente),
        Tool("responder_reclamacao", "Responde reclamacao de cliente",
             ["reclamacao", "reclamação", "problema", "insatisfeito"], _responder_reclamacao),
        Tool("responder_duvida", "Responde duvida de cliente",
             ["duvida", "dúvida", "pergunta", "questionamento"], _responder_duvida),
        Tool("responder_orcamento", "Responde solicitacao de orcamento",
             ["orcamento", "orçamento", "quanto custa", "preco", "valor"], _responder_orcamento),
        Tool("atendimento_humanizado", "Atendimento com tom humanizado e acolhedor",
             ["humanizado", "acolhedor", "personalizado", "empatia"], _atendimento_humanizado),
    ]
