"""
Ferramentas do agente Social Media.
"""

from tools.base import Tool


def _legenda(texto: str) -> str:
    return (
        f"LEGENDA PARA REDES SOCIAIS\n"
        f"{'=' * 40}\n\n"
        f"Baseada em: {texto}\n\n"
        f"---\n"
        f"Voce ja parou para pensar como {texto.lower()} "
        f"pode transformar o seu dia?\n\n"
        f"A verdade e que pequenas mudancas geram grandes resultados. "
        f"E hoje eu vim compartilhar uma dica que faz toda a diferenca.\n\n"
        f"💡 {texto}\n\n"
        f"E voce, ja experimentou? Conta nos comentarios!\n\n"
        f"---\n"
        f"#dica #transformacao #crescimento"
    )


def _hashtags(texto: str) -> str:
    palavras = texto.lower().split()[:5]
    tags = ["#" + p for p in palavras if len(p) > 3]
    tags.extend(["#dica", "#inspiracao", "#sucesso", "#motivacao"])
    return "HASHTAGS\n" + "=" * 20 + "\n\n" + " ".join(tags[:15])


def _calendario(texto: str) -> str:
    return (
        f"CALENDARIO DE CONTEUDO\n"
        f"{'=' * 40}\n\n"
        f"Tema: {texto}\n\n"
        f"Semana 1:\n"
        f"  Seg: Post educativo - {texto}\n"
        f"  Qua: Bastidores - Processo de criacao\n"
        f"  Sex: Prova social - Depoimento\n"
        f"  Sab: Entretenimento - Humor relacionado\n\n"
        f"Semana 2:\n"
        f"  Seg: Tutorial - Como usar {texto}\n"
        f"  Qua: Case de sucesso\n"
        f"  Sex: FAQ - Respondendo duvidas\n"
        f"  Sab: Bastidores - Equipe\n\n"
        f"Dica: alterne conteudo educativo, inspiracional e de entretenimento."
    )


def _reels_roteiro(texto: str) -> str:
    return (
        f"ROTEIRO PARA REELS\n"
        f"{'=' * 40}\n\n"
        f"Tema: {texto}\n\n"
        f"[Atencao: 15-30 segundos]\n\n"
        f"00:00-00:05 - GANCHO: \"Você sabia que {texto.lower()} \"\n"
        f"00:05-00:15 - DESENVOLVIMENTO: Mostre o processo, os detalhes\n"
        f"00:15-00:25 - DICA PRATICA: Ensine algo aplicavel\n"
        f"00:25-00:30 - CTA: \"Salva pra ver depois e compartilha!\"\n\n"
        f"Texto para tela:\n"
        f"  - Titulo chamativo no inicio\n"
        f"  - Bullet points na explicacao\n"
        f"  - CTA no final com animacao"
    )


def _tiktok_roteiro(texto: str) -> str:
    return (
        f"ROTEIRO PARA TIKTOK\n"
        f"{'=' * 40}\n\n"
        f"Tema: {texto}\n\n"
        f"[Duracao: 30-60 segundos]\n\n"
        f"00:00-00:07 - GANCHO IMPACTANTE: \"Isso vai mudar sua forma de ver {texto.lower()}!\"\n"
        f"00:07-00:35 - CONTEUDO: Ritmo rapido, cortes secos, musica alta\n"
        f"00:35-00:50 - DICA EXTRA: Algo surpreendente\n"
        f"00:50-01:00 - CTA: \"Segue pro proximo video!\"\n\n"
        f"Efeitos sugeridos: transicao rapida, zoom in/out, texto na tela"
    )


def _meta_ads(texto: str) -> str:
    return (
        f"ANUNCIO META ADS\n"
        f"{'=' * 40}\n\n"
        f"Produto/Servico: {texto}\n\n"
        f"FORMATO: Anuncio unico com imagem\n\n"
        f"TITULO: {texto} — A solucao que voce procurava\n"
        f"TEXTO PRINCIPAL:\n"
        f"  Pare de perder tempo com {texto.lower()} que nao funciona.\n"
        f"  Nos temos a solucao ideal para voce.\n"
        f"  Acesse o link e descubra.\n\n"
        f"CTA: Saiba Mais\n"
        f"PUBLICO: Interesses relacionados\n"
        f"ORCAMENTO SUGERIDO: R$ 30-50/dia (teste), R$ 80-150/dia (escala)"
    )


def _google_ads(texto: str) -> str:
    return (
        f"ANUNCIO GOOGLE ADS\n"
        f"{'=' * 40}\n\n"
        f"Produto/Servico: {texto}\n\n"
        f"TITULO 1: {texto} — Melhor Preco\n"
        f"TITULO 2: {texto} | Qualidade Garantida\n"
        f"TITULO 3: Compre {texto} Agora\n\n"
        f"DESCRICAO 1:\n"
        f"  Encontre o melhor {texto.lower()} do mercado. Entrega rapida e garantia.\n"
        f"DESCRICAO 2:\n"
        f"  Milhares de clientes satisfeitos. Confira nossas avaliacoes.\n\n"
        f"PALAVRAS-CHAVE: {texto}, {texto} barato, {texto} online, {texto} qualidade\n"
        f"TIPO DE CORRESPONDENCIA: frase\n"
        f"LANCE SUGERIDO: R$ 2-5/clique"
    )


def get_tools():
    return [
        Tool("criar_legenda", "Cria legenda para post em rede social",
             ["legenda", "legendas", "descricao", "post", "publicacao"], _legenda),
        Tool("criar_hashtags", "Cria hashtags para post",
             ["hashtag", "hashtags", "tags", "marcadores"], _hashtags),
        Tool("criar_calendario", "Cria calendario editorial de conteudo",
             ["calendario", "editorial", "conteudo", "planejamento", "cronograma"], _calendario),
        Tool("criar_reels_roteiro", "Cria roteiro para Reels do Instagram",
             ["reels", "instagram", "reel", "video curto"], _reels_roteiro),
        Tool("criar_tiktok_roteiro", "Cria roteiro para TikTok",
             ["tiktok", "tik tok"], _tiktok_roteiro),
        Tool("criar_meta_ads", "Cria anuncio para Meta Ads (Facebook/Instagram)",
             ["meta", "facebook", "fb", "ads", "anuncio", "patrocinado"], _meta_ads),
        Tool("criar_google_ads", "Cria anuncio para Google Ads",
             ["google", "adsense", "adwords", "search"], _google_ads),
    ]
