"""
Ferramentas do agente Copywriter.
"""

from tools.base import Tool


def _pagina_vendas(texto: str) -> str:
    return (
        f"PAGINA DE VENDAS\n"
        f"{'=' * 50}\n\n"
        f"Produto: {texto}\n\n"
        f"HEADLINE: {texto} — A Escolha Inteligente\n\n"
        f"SUBHEADLINE: Descubra por que milhares ja escolheram {texto.lower()}\n\n"
        f"PROBLEMA:\n"
        f"  Voce ja se sentiu frustrado com {texto.lower()} que nao entrega?\n\n"
        f"SOLUCAO:\n"
        f"  Apresentamos a solucao que resolve de verdade.\n\n"
        f"BENEFICIOS:\n"
        f"  - Resultado rapido e comprovado\n"
        f"  - Suporte especializado\n"
        f"  - Garantia incondicional\n\n"
        f"PROVA SOCIAL:\n"
        f"  \"Mudou minha vida!\" — Cliente satisfeito\n\n"
        f"GARANTIA:\n"
        f"  7 dias de garantia ou seu dinheiro de volta.\n\n"
        f"CTA: COMPRE AGORA — [Link]\n"
        f"ULTIMATO: Oferta por tempo limitado!"
    )


def _vsl(texto: str) -> str:
    return (
        f"VSL (VIDEO SALES LETTER)\n"
        f"{'=' * 50}\n\n"
        f"Produto: {texto}\n\n"
        f"ESTRUTURA DO VIDEO:\n\n"
        f"[00:00-00:15] GANCHO:\n"
        f"  \"Você sabia que 90% das pessoas erram ao escolher {texto.lower()}?\"\n\n"
        f"[00:15-01:00] PROBLEMA:\n"
        f"  Apresente a dor de forma intensa.\n"
        f"  Faca perguntas que gerem identificacao.\n\n"
        f"[01:00-03:00] SOLUCAO:\n"
        f"  Apresente {texto} como a resposta.\n"
        f"  Mostre funcionamento e beneficios.\n\n"
        f"[03:00-04:30] PROVA SOCIAL:\n"
        f"  Depoimentos, dados, resultados.\n\n"
        f"[04:30-05:30] OFERTA:\n"
        f"  Preco, bonus, garantia.\n\n"
        f"[05:30-06:00] CTA:\n"
        f"  \"Clique no link abaixo e garanta o seu agora!\""
    )


def _headline(texto: str) -> str:
    return (
        f"HEADLINES\n"
        f"{'=' * 50}\n\n"
        f"Produto/Tema: {texto}\n\n"
        f"1. Direta: {texto} — O Melhor para Voce\n"
        f"2. Curiosidade: O que ninguem te conta sobre {texto.lower()}\n"
        f"3. Urgencia: Ultimas unidades de {texto.lower()}!\n"
        f"4. Como Fazer: Como escolher {texto.lower()} perfeito em 3 passos\n"
        f"5. Prova Social: {texto} — Preferido por mais de 10 mil clientes\n"
        f"6. Pergunta: Voce ainda usa {texto.lower()} antigo?\n"
        f"7. Lista: 7 razoes para escolher {texto.lower()} agora\n"
        f"8. Negacao: Nao compre {texto.lower()} antes de ler isso\n\n"
        f"Dica: teste as 3 primeiras em anúncios e veja qual converte mais."
    )


def _oferta(texto: str) -> str:
    return (
        f"ESTRUTURA DE OFERTA\n"
        f"{'=' * 50}\n\n"
        f"Produto: {texto}\n\n"
        f"OFERTA PRINCIPAL:\n"
        f"  {texto} — Valor: R$ X,XX\n\n"
        f"BRINDES/BONUS:\n"
        f"  Bonus 1: Guia rapido (R$ 47 de valor)\n"
        f"  Bonus 2: Suporte VIP por 30 dias (R$ 97 de valor)\n"
        f"  Bonus 3: Acesso a comunidade exclusiva (R$ 67 de valor)\n\n"
        f"TOTAL DOS BONUS: R$ 211\n"
        f"VALOR DA OFERTA: R$ X,XX\n\n"
        f"GARANTIA:\n"
        f"  7 dias de satisfacao ou seu dinheiro de volta.\n\n"
        f"PARCELAMENTO:\n"
        f"  Em ate 12x sem juros no cartao.\n\n"
        f"URGENCIA:\n"
        f"  Oferta valida por 48 horas."
    )


def _email_marketing(texto: str) -> str:
    return (
        f"EMAIL MARKETING\n"
        f"{'=' * 50}\n\n"
        f"Produto/Tema: {texto}\n\n"
        f"ASSUNTO: {texto} — A escolha certa para voce\n"
        f"PRE-HEADER: Descubra como {texto.lower()} pode ajudar\n\n"
        f"CORPO:\n\n"
        f"Ola [Nome],\n\n"
        f"Se voce busca {texto.lower()}, temos a solucao ideal.\n\n"
        f"Por que escolher nos?\n"
        f"- Qualidade comprovada\n"
        f"- Entrega rapida\n"
        f"- Suporte dedicado\n\n"
        f"Clique aqui e confira: [Link]\n\n"
        f"Atenciosamente,\n"
        f"Equipe CRIS OS"
    )


def _sequencia_emails(texto: str) -> str:
    return (
        f"SEQUENCIA DE EMAILS\n"
        f"{'=' * 50}\n\n"
        f"Produto/Tema: {texto}\n\n"
        f"DIA 1 — Apresentacao:\n"
        f"  Assunto: Conheca {texto}\n"
        f"  Conteudo: Apresente o produto, problema que resolve\n\n"
        f"DIA 3 — Educacao:\n"
        f"  Assunto: Como {texto.lower()} funciona na pratica\n"
        f"  Conteudo: Tutorial, dicas de uso\n\n"
        f"DIA 5 — Prova Social:\n"
        f"  Assunto: O que nossos clientes dizem sobre {texto.lower()}\n"
        f"  Conteudo: Depoimentos, cases\n\n"
        f"DIA 7 — Oferta:\n"
        f"  Assunto: Oferta especial para voce\n"
        f"  Conteudo: Precificacao, bonus, CTA\n\n"
        f"DIA 10 — Urgencia:\n"
        f"  Assunto: Ultimas horas! Nao perca esta oferta\n"
        f"  Conteudo: Ultimato, CTA final\n\n"
        f"DIA 14 — Reengajamento:\n"
        f"  Assunto: Sentimos sua falta\n"
        f"  Conteudo: Nova oferta, novidades"
    )


def _copy_whatsapp(texto: str) -> str:
    return (
        f"COPY PARA WHATSAPP\n"
        f"{'=' * 50}\n\n"
        f"Produto/Servico: {texto}\n\n"
        f"MENSAGEM INICIAL:\n"
        f"  Ola! Tudo bem?\n"
        f"  Vi que voce se interessou por {texto.lower()}.\n"
        f"  Posso te ajudar com alguma duvida?\n\n"
        f"SEGUIMENTO:\n"
        f"  Aqui estao alguns beneficios:\n"
        f"  - Qualidade que voce merece\n"
        f"  - Preco justo\n"
        f"  - Entrega rapida\n\n"
        f"  Quer saber mais?\n\n"
        f"ENCERRAMENTO:\n"
        f"  Fico a disposicao! 😊\n"
        f"  So chamar aqui ou ligar."
    )


def _copy_telegram(texto: str) -> str:
    return (
        f"COPY PARA TELEGRAM\n"
        f"{'=' * 50}\n\n"
        f"Produto/Servico: {texto}\n\n"
        f"MENSAGEM:\n"
        f"  Olá! 👋\n\n"
        f"  Você sabia que {texto.lower()} pode fazer a diferença?\n\n"
        f"  Benefícios:\n"
        f"  ✅ Pratico e rapido\n"
        f"  ✅ Qualidade garantida\n"
        f"  ✅ Suporte via Telegram\n\n"
        f"  Quer saber mais? Me chama aqui!\n\n"
        f"  👇\n"
        f"  [Link]"
    )


def get_tools():
    return [
        Tool("pagina_de_vendas", "Cria pagina de vendas completa",
             ["pagina", "vendas", "landing", "lp", "pagina de venda"], _pagina_vendas),
        Tool("vsl", "Cria roteiro de VSL (Video Sales Letter)",
             ["vsl", "video", "sales", "letter", "venda em video"], _vsl),
        Tool("headline", "Cria variacoes de headline chamativa",
             ["headline", "titulo", "chamada", "manchete"], _headline),
        Tool("oferta", "Estrutura oferta com bonus e urgencia",
             ["oferta", "preco", "valor", "promocao", "desconto"], _oferta),
        Tool("email_marketing", "Cria email marketing promocional",
             ["email", "newsletter", "mail", "e-mail"], _email_marketing),
        Tool("sequencia_emails", "Cria sequencia de emails automatizada",
             ["sequencia", "automacao", "drip", "campanha de email"], _sequencia_emails),
        Tool("copy_whatsapp", "Cria copy para WhatsApp comercial",
             ["whatsapp", "zap", "whats"], _copy_whatsapp),
        Tool("copy_telegram", "Cria copy para Telegram",
             ["telegram", "telegrama"], _copy_telegram),
    ]
