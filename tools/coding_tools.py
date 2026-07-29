"""
Ferramentas do agente Programador.
"""

from tools.base import Tool


def _gerar_codigo(texto: str) -> str:
    return (
        f"CODIGO GERADO\n"
        f"{'=' * 50}\n\n"
        f"Descricao: {texto}\n\n"
        f"```python\n"
        f"# {texto[:60]}\n"
        f"\n"
        f"def solucao():\n"
        f'    """Implementacao gerada automaticamente."""\n'
        f"    # TODO: implementar logica\n"
        f"    pass\n"
        f"\n"
        f"\n"
        f"if __name__ == '__main__':\n"
        f"    resultado = solucao()\n"
        f"    print(resultado)\n"
        f"```\n\n"
        f"Nota: estrutura gerada. Adapte conforme a necessidade.\n"
        f"Dica: especifique linguagem, framework e bibliotecas desejadas."
    )


def _corrigir_bugs(texto: str) -> str:
    return (
        f"CORRECAO DE BUG\n"
        f"{'=' * 50}\n\n"
        f"Problema relatado: {texto}\n\n"
        f"ANALISE:\n"
        f"  Possivel causa: [identificar causa raiz]\n\n"
        f"SOLUCAO PROPOSTA:\n"
        f"  1. Verificar logs e traces\n"
        f"  2. Adicionar tratamento de excecao\n"
        f"  3. Validar entrada de dados\n\n"
        f"CODIGO CORRIGIDO:\n"
        f"```python\n"
        f"try:\n"
        f"    # codigo original com correcao\n"
        f"    resultado = executar_operacao()\n"
        f"except Exception as e:\n"
        f"    logger.error(f\"Erro ao executar: {e}\")\n"
        f"    raise\n"
        f"```\n\n"
        f"TESTE SUGERIDO:\n"
        f"  - Teste com entrada valida\n"
        f"  - Teste com entrada invalida\n"
        f"  - Teste de estresse"
    )


def _revisar_codigo(texto: str) -> str:
    return (
        f"REVISAO DE CODIGO\n"
        f"{'=' * 50}\n\n"
        f"Codigo para revisao: {texto}\n\n"
        f"PONTOS POSITIVOS:\n"
        f"  - Estrutura clara\n"
        f"  - Nomenclatura adequada\n\n"
        f"PONTOS DE ATENCAO:\n"
        f"  - Faltam tratamentos de erro\n"
        f"  - Complexidade ciclomatica alta em alguns trechos\n"
        f"  - Sugestao: extrair funcoes menores\n\n"
        f"SUGESTOES:\n"
        f"  1. Adicionar docstrings\n"
        f"  2. Separar responsabilidades\n"
        f"  3. Adicionar testes unitarios\n"
        f"  4. Seguir padrao PEP 8\n\n"
        f"NOTA GERAL: Codigo funcional, mas pode ser melhorado."
    )


def _criar_api(texto: str) -> str:
    return (
        f"API CRIADA\n"
        f"{'=' * 50}\n\n"
        f"Descricao: {texto}\n\n"
        f"```python\n"
        f"from fastapi import FastAPI, HTTPException\n"
        f"\n"
        f"app = FastAPI(title='API - {texto[:30]}')\n"
        f"\n"
        f"\n"
        f"@app.get('/')\n"
        f"def root():\n"
        f"    return {{'message': 'API funcionando', 'version': '1.0.0'}}\n"
        f"\n"
        f"\n"
        f"@app.get('/api/recurso')\n"
        f"def get_recurso():\n"
        f'    """Endpoint principal."""\n'
        f"    return {{'status': 'ok', 'data': []}}\n"
        f"```\n\n"
        f"ESTRUTURA SUGERIDA:\n"
        f"  /api/  -> endpoints principais\n"
        f"  /docs  -> documentacao Swagger\n"
        f"  /health -> health check\n\n"
        f"Dica: especifique framework (FastAPI, Flask, Express) e banco de dados."
    )


def _criar_testes(texto: str) -> str:
    return (
        f"TESTES CRIADOS\n"
        f"{'=' * 50}\n\n"
        f"Codigo a testar: {texto}\n\n"
        f"```python\n"
        f"import pytest\n"
        f"\n"
        f"\n"
        f"def test_funcionalidade_principal():\n"
        f'    """Testa o fluxo principal."""\n'
        f"    resultado = solucao(parametro_valido)\n"
        f"    assert resultado is not None\n"
        f"    assert resultado['status'] == 'ok'\n"
        f"\n"
        f"\n"
        f"def test_caso_borda():\n"
        f'    """Testa entrada vazia."""\n'
        f"    with pytest.raises(ValueError):\n"
        f"        solucao('')\n"
        f"\n"
        f"\n"
        f"def test_caso_erro():\n"
        f'    """Testa erro esperado."""\n'
        f"    resultado = solucao(parametro_invalido)\n"
        f"    assert 'erro' in resultado\n"
        f"```\n\n"
        f"COBERTURA SUGERIDA:\n"
        f"  - Fluxo principal (happy path)\n"
        f"  - Casos de borda (vazio, nulo)\n"
        f"  - Casos de erro (excecoes)\n"
        f"  - Testes de integracao"
    )


def _documentar(texto: str) -> str:
    return (
        f"DOCUMENTACAO\n"
        f"{'=' * 50}\n\n"
        f"Codigo/Projeto: {texto}\n\n"
        f"```python\n"
        f'def func_principal(parametro: str) -> dict:\n'
        f'    """\n'
        f"    Descricao da funcionalidade.\n"
        f"\n"
        f"    Parameters\n"
        f"    ----------\n"
        f"    parametro : str\n"
        f"        Descricao do parametro.\n"
        f"\n"
        f"    Returns\n"
        f"    -------\n"
        f"    dict\n"
        f"        Dicionario com resultado.\n"
        f"\n"
        f"    Examples\n"
        f"    --------\n"
        f'    >>> func_principal("exemplo")\n'
        f"    {{'status': 'ok'}}\n"
        f'    """\n'
        f"```\n\n"
        f"DOCUMENTACAO GERADA:\n"
        f"  - Docstring no formato Google/PEP 257\n"
        f"  - Descricao dos parametros\n"
        f"  - Tipo de retorno\n"
        f"  - Exemplo de uso\n\n"
        f"Adapte conforme o padrao usado no projeto."
    )


def get_tools():
    return [
        Tool("gerar_codigo", "Gera codigo a partir de descricao",
             ["codigo", "código", "programa", "funcao", "função", "implementar", "criar codigo", "script"], _gerar_codigo),
        Tool("corrigir_bugs", "Corrige bugs em codigo",
             ["bug", "erro", "corrigir", "consertar", "debug", "defeito"], _corrigir_bugs),
        Tool("revisar_codigo", "Revisa codigo e sugere melhorias",
             ["revisar", "revisao", "revisão", "code review", "avaliar", "auditar"], _revisar_codigo),
        Tool("criar_api", "Cria estrutura de API REST",
             ["api", "rest", "endpoint", "servico", "serviço", "rota"], _criar_api),
        Tool("criar_testes", "Cria testes unitarios para codigo",
             ["teste", "testes", "pytest", "unitario", "unitário", "cobertura"], _criar_testes),
        Tool("documentar", "Gera documentacao de codigo",
             ["documentar", "documentacao", "documentação", "docstring", "doc"], _documentar),
    ]
