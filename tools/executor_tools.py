"""10 ferramentas de sistema para o Tool Executor.

Cada ferramenta expoe:
  - name: identificador
  - description: descricao para o LLM
  - schema() -> dict: JSON Schema dos parametros
  - run(**kwargs) -> str: executa e devolve texto
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. GitHub Tool
# ---------------------------------------------------------------------------
def _github_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_repos", "list_commits", "list_branches", "status"],
                "description": "Acao do Git/GitHub",
            },
            "path": {
                "type": "string",
                "description": "Caminho do repositorio local (padrao: diretorio atual)",
            },
        },
        "required": ["action"],
    }


def _github_run(**kwargs) -> str:
    action = kwargs.get("action", "status")
    path = kwargs.get("path", ".")

    if action == "status":
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True, text=True, timeout=15, cwd=path,
            )
            saida = result.stdout or result.stderr or "(vazio)"
            return f"[GITHUB] status:\n{saida.strip()}"
        except FileNotFoundError:
            return "[GITHUB] git nao encontrado no PATH"
        except subprocess.TimeoutExpired:
            return "[GITHUB] comando git excedeu timeout"
        except Exception as e:
            return f"[GITHUB] erro: {e}"

    if action == "list_repos":
        try:
            result = subprocess.run(
                ["git", "remote", "-v"],
                capture_output=True, text=True, timeout=15, cwd=path,
            )
            remotes = result.stdout.strip() or "(sem remotes)"
            branches = subprocess.run(
                ["git", "branch", "-a"],
                capture_output=True, text=True, timeout=15, cwd=path,
            )
            return f"[GITHUB] Remotes:\n{remotes}\n\nBranches:\n{branches.stdout.strip()}"
        except Exception as e:
            return f"[GITHUB] erro: {e}"

    if action == "list_commits":
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                capture_output=True, text=True, timeout=15, cwd=path,
            )
            saida = result.stdout.strip() or "(sem commits)"
            return f"[GITHUB] Ultimos commits:\n{saida}"
        except Exception as e:
            return f"[GITHUB] erro: {e}"

    if action == "list_branches":
        try:
            result = subprocess.run(
                ["git", "branch", "-a"],
                capture_output=True, text=True, timeout=15, cwd=path,
            )
            saida = result.stdout.strip() or "(sem branches)"
            return f"[GITHUB] Branches:\n{saida}"
        except Exception as e:
            return f"[GITHUB] erro: {e}"

    return f"[GITHUB] Acao desconhecida: {action}"


# ---------------------------------------------------------------------------
# 2. Files Tool
# ---------------------------------------------------------------------------
def _files_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "list", "delete"],
                "description": "Acao no sistema de arquivos",
            },
            "path": {
                "type": "string",
                "description": "Caminho do arquivo ou diretorio",
            },
            "content": {
                "type": "string",
                "description": "Conteudo para escrever (usado com action=write)",
            },
        },
        "required": ["action", "path"],
    }


def _files_run(**kwargs) -> str:
    action = kwargs.get("action")
    path = kwargs.get("path", "")
    content = kwargs.get("content", "")

    if not path:
        return "[FILES] Caminho nao informado"

    p = Path(path)

    if action == "read":
        if not p.exists():
            return f"[FILES] Arquivo nao encontrado: {path}"
        try:
            texto = p.read_text(encoding="utf-8")
            return f"[FILES] {path} ({len(texto)} chars):\n{texto}"
        except Exception as e:
            return f"[FILES] Erro ao ler: {e}"

    if action == "write":
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"[FILES] Arquivo criado: {path} ({len(content)} chars)"
        except Exception as e:
            return f"[FILES] Erro ao escrever: {e}"

    if action == "list":
        if not p.exists():
            return f"[FILES] Diretorio nao encontrado: {path}"
        if not p.is_dir():
            return f"[FILES] Nao e um diretorio: {path}"
        try:
            entries = list(p.iterdir())
            linhas = [f"  {e.name}{'/' if e.is_dir() else ''}" for e in sorted(entries)]
            return f"[FILES] {path} ({len(entries)} entradas):\n" + "\n".join(linhas)
        except Exception as e:
            return f"[FILES] Erro ao listar: {e}"

    if action == "delete":
        if not p.exists():
            return f"[FILES] Nao encontrado: {path}"
        try:
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
            return f"[FILES] Removido: {path}"
        except Exception as e:
            return f"[FILES] Erro ao remover: {e}"

    return f"[FILES] Acao desconhecida: {action}"


# ---------------------------------------------------------------------------
# 3. Terminal Tool
# ---------------------------------------------------------------------------
def _terminal_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Comando a executar no terminal",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout em segundos (padrao: 30)",
                "default": 30,
            },
            "workdir": {
                "type": "string",
                "description": "Diretorio de trabalho (opcional)",
            },
        },
        "required": ["command"],
    }


def _terminal_run(**kwargs) -> str:
    command = kwargs.get("command", "")
    timeout = kwargs.get("timeout", 30)
    workdir = kwargs.get("workdir", None)

    if not command:
        return "[TERMINAL] Nenhum comando informado"

    logger.info("=== [TERMINAL] Executando: '%s' (timeout=%ds) ===", command[:200], timeout)
    t0 = time.perf_counter()

    try:
        result = subprocess.run(
            command,
            capture_output=True, text=True, timeout=timeout,
            shell=True, cwd=workdir,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        saida = result.stdout or ""
        erros = result.stderr or ""
        status = f"codigo={result.returncode}"
        if saida:
            saida = saida[:3000]
        if erros:
            erros = erros[:1000]
        logger.info("=== [TERMINAL] Concluido em %.0fms, %s, stdout=%d chars, stderr=%d chars ===",
                    elapsed_ms, status, len(saida), len(erros))
        partes = [f"[TERMINAL] Comando: {command}", f"Status: {status}", f"Tempo: {elapsed_ms:.0f}ms"]
        if saida:
            partes.append(f"Saida:\n{saida}")
        if erros:
            partes.append(f"Erros:\n{erros}")
        return "\n".join(partes)
    except subprocess.TimeoutExpired:
        return f"[TERMINAL] Comando excedeu timeout de {timeout}s: {command[:100]}"
    except FileNotFoundError:
        return f"[TERMINAL] Comando nao encontrado: {command.split()[0]}"
    except Exception as e:
        return f"[TERMINAL] Erro: {e}"


# ---------------------------------------------------------------------------
# 4. SQLite Tool
# ---------------------------------------------------------------------------
def _sqlite_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["query", "execute"],
                "description": "query = SELECT (retorna dados), execute = INSERT/UPDATE/DELETE/CREATE",
            },
            "sql": {
                "type": "string",
                "description": "Comando SQL",
            },
            "db_path": {
                "type": "string",
                "description": "Caminho do arquivo .db (padrao: data/cris_os.db)",
            },
        },
        "required": ["action", "sql"],
    }


def _sqlite_run(**kwargs) -> str:
    action = kwargs.get("action", "query")
    sql = kwargs.get("sql", "")
    db_path = kwargs.get("db_path", "")

    if not sql:
        return "[SQLITE] Nenhum SQL informado"

    path = Path(db_path) if db_path else Path("data/cris_os.db")

    if not path.exists():
        return f"[SQLITE] Banco nao encontrado: {path}"

    t0 = time.perf_counter()
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql)

        if action == "query":
            rows = cursor.fetchall()
            colunas = [d[0] for d in cursor.description] if cursor.description else []
            linhas = "\n".join(str(dict(r)) for r in rows[:50])
            total = len(rows)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            conn.close()
            return f"[SQLITE] Query ok ({total} resultados, {elapsed_ms:.0f}ms)\nColunas: {colunas}\n{linhas}"

        conn.commit()
        changes = cursor.rowcount
        elapsed_ms = (time.perf_counter() - t0) * 1000
        conn.close()
        return f"[SQLITE] Executado: {sql} ({changes} linhas afetadas, {elapsed_ms:.0f}ms)"
    except sqlite3.Error as e:
        return f"[SQLITE] Erro SQL: {e}"
    except Exception as e:
        return f"[SQLITE] Erro: {e}"


# ---------------------------------------------------------------------------
# 5. Browser Tool
# ---------------------------------------------------------------------------
def _browser_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL para acessar (http/https)",
            },
            "extract": {
                "type": "string",
                "enum": ["text", "title", "links"],
                "description": "O que extrair (padrao: text)",
                "default": "text",
            },
        },
        "required": ["url"],
    }


def _browser_run(**kwargs) -> str:
    url = kwargs.get("url", "")
    extract = kwargs.get("extract", "text")

    if not url:
        return "[BROWSER] URL nao informada"
    if not url.startswith(("http://", "https://")):
        return "[BROWSER] URL deve comecar com http:// ou https://"

    t0 = time.perf_counter()
    try:
        req = Request(url, headers={"User-Agent": "CRIS-OS/1.0"})
        with urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            elapsed_ms = (time.perf_counter() - t0) * 1000

            import re
            title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = title_m.group(1).strip() if title_m else "(sem titulo)"

            if extract == "title":
                return f"[BROWSER] Titulo: {title} ({elapsed_ms:.0f}ms)"

            text_m = re.sub(r"<[^>]+>", " ", html)
            text_m = re.sub(r"\s+", " ", text_m).strip()
            text = text_m[:3000]

            if extract == "links":
                links = re.findall(r'href=["\'](https?://[^"\']+)["\']', html)
                return f"[BROWSER] Links encontrados: {len(links)}\n" + "\n".join(links[:20])

            return f"[BROWSER] {title} ({len(html)} bytes, {elapsed_ms:.0f}ms):\n{text[:2000]}"
    except Exception as e:
        return f"[BROWSER] Erro ao acessar {url}: {e}"


# ---------------------------------------------------------------------------
# 6. Search Tool
# ---------------------------------------------------------------------------
def _search_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Termo de busca",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximo de resultados (padrao: 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    }


def _search_run(**kwargs) -> str:
    query = kwargs.get("query", "")
    max_results = kwargs.get("max_results", 5)

    if not query:
        return "[SEARCH] Nenhum termo de busca informado"

    t0 = time.perf_counter()
    try:
        params = urlencode({"q": query, "num": min(max_results, 10)})
        url = f"https://html.duckduckgo.com/html/?{params}"
        req = Request(url, headers={"User-Agent": "CRIS-OS/1.0"})
        with urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            elapsed_ms = (time.perf_counter() - t0) * 1000

            import re
            results = re.findall(
                r'<a[^>]+class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                html, re.DOTALL,
            )
            snippets = re.findall(
                r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                html, re.DOTALL,
            )

            linhas = []
            for i, (url_result, titulo) in enumerate(results[:max_results]):
                snippet = snippets[i] if i < len(snippets) else ""
                snippet = re.sub(r"<[^>]+>", "", snippet).strip()
                linhas.append(f"{i+1}. {re.sub(r'<[^>]+>', '', titulo).strip()}")
                linhas.append(f"   URL: {url_result}")
                if snippet:
                    linhas.append(f"   {snippet[:200]}")

            if not linhas:
                return f"[SEARCH] Nenhum resultado encontrado para '{query}' ({elapsed_ms:.0f}ms)"

            return f"[SEARCH] '{query}' — {len(results)} resultados ({elapsed_ms:.0f}ms):\n" + "\n".join(linhas)
    except Exception as e:
        return f"[SEARCH] Erro ao buscar '{query}': {e}"


# ---------------------------------------------------------------------------
# 7. Document Generator Tool
# ---------------------------------------------------------------------------
def _docgen_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Titulo do documento",
            },
            "content": {
                "type": "string",
                "description": "Conteudo em markdown",
            },
            "output_path": {
                "type": "string",
                "description": "Caminho para salvar (opcional — se nao informado, retorna o texto)",
            },
        },
        "required": ["title", "content"],
    }


def _docgen_run(**kwargs) -> str:
    title = kwargs.get("title", "Documento")
    content = kwargs.get("content", "")
    output_path = kwargs.get("output_path", "")

    doc = f"# {title}\n\n{content}"
    t0 = time.perf_counter()

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc, encoding="utf-8")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return f"[DOCGEN] Documento salvo: {output_path} ({len(doc)} chars, {elapsed_ms:.0f}ms)"
    else:
        return f"[DOCGEN] Documento gerado ({len(doc)} chars):\n{doc}"


# ---------------------------------------------------------------------------
# 8. Image Generator Tool (placeholder)
# ---------------------------------------------------------------------------
def _imggen_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Descricao da imagem a ser gerada",
            },
            "size": {
                "type": "string",
                "enum": ["512x512", "1024x1024"],
                "description": "Tamanho da imagem",
                "default": "1024x1024",
            },
        },
        "required": ["prompt"],
    }


def _imggen_run(**kwargs) -> str:
    prompt = kwargs.get("prompt", "")
    size = kwargs.get("size", "1024x1024")
    return (
        f"[IMGGEN] Prompt recebido: '{prompt}' ({size})\n"
        f"Geracao de imagens por IA requer integracao com API externa "
        f"(Stable Diffusion / DALL-E / Midjourney).\n"
        f"O prompt foi registrado para geracao futura."
    )


# ---------------------------------------------------------------------------
# 9. HTTP/API Tool
# ---------------------------------------------------------------------------
def _http_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "DELETE"],
                "description": "Metodo HTTP",
                "default": "GET",
            },
            "url": {
                "type": "string",
                "description": "URL da requisicao",
            },
            "headers": {
                "type": "object",
                "description": "Cabecalhos HTTP (opcional)",
                "default": {},
            },
            "body": {
                "type": "string",
                "description": "Corpo da requisicao (para POST/PUT, opcional)",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout em segundos (padrao: 30)",
                "default": 30,
            },
        },
        "required": ["url"],
    }


def _http_run(**kwargs) -> str:
    method = kwargs.get("method", "GET").upper()
    url = kwargs.get("url", "")
    headers = kwargs.get("headers", {}) or {}
    body = kwargs.get("body", "")
    timeout = kwargs.get("timeout", 30)

    if not url:
        return "[HTTP] URL nao informada"

    t0 = time.perf_counter()
    try:
        data = body.encode("utf-8") if body and method in ("POST", "PUT") else None
        req = Request(url, data=data, headers={
            "User-Agent": "CRIS-OS/1.0",
            **({} if not headers else headers),
        }, method=method)

        with urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            elapsed_ms = (time.perf_counter() - t0) * 1000
            status = resp.status
            return (
                f"[HTTP] {method} {url} -> {status} ({elapsed_ms:.0f}ms)\n"
                f"{content[:2000]}"
            )
    except Exception as e:
        return f"[HTTP] Erro: {method} {url} -> {e}"


# ---------------------------------------------------------------------------
# 10. Prospector Tool
# ---------------------------------------------------------------------------
def _prospector_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "prospectar", "redesenhar", "publicar", "proposta",
                    "contrato", "followups", "fechar", "listar", "status",
                ],
                "description": "Acao de prospeccao de leads",
            },
            "nicho": {
                "type": "string",
                "description": "Nicho/segmento para prospectar (ex.: 'impressao 3d')",
            },
            "cidade": {
                "type": "string",
                "description": "Cidade ou regiao da busca de leads",
            },
            "quantos": {
                "type": "integer",
                "description": "Quantidade de leads (opcional, padrao do motor)",
            },
            "slug": {
                "type": "string",
                "description": "Identificador unico do lead (slug)",
            },
            "valor": {
                "type": "number",
                "description": "Valor do fechamento (action=fechar)",
            },
            "manutencao": {
                "type": "number",
                "description": "Mensalidade de manutencao (action=fechar, opcional)",
            },
            "simular": {
                "type": "boolean",
                "description": "Modo simulacao (nao usa IA nem publica; padrao: automatico)",
            },
        },
        "required": ["action"],
    }


def _prospector_run(**kwargs) -> str:
    from services.prospector.service import get_prospector_service

    action = kwargs.get("action", "")

    if action == "status":
        return "[PROSPECTOR] Status: " + json.dumps(service.status(), ensure_ascii=False)

    if action == "listar":
        try:
            return "[PROSPECTOR] Leads:\n" + service.listar()
        except Exception as e:
            return f"[PROSPECTOR] Erro: {e}"

    if action == "prospectar":
        nicho = kwargs.get("nicho", "")
        cidade = kwargs.get("cidade", "")
        if not nicho or not cidade:
            return "[PROSPECTOR] informe 'nicho' e 'cidade'"
        try:
            res = service.prospectar(nicho, cidade, kwargs.get("quantos"), kwargs.get("simular"))
            return "[PROSPECTOR] Busca: %s\n%s" % (
                "simulacao" if res["simular"] else "real", res["saida"] or res.get("erro", ""),
            )
        except Exception as e:
            return f"[PROSPECTOR] Erro: {e}"

    if action in ("redesenhar", "publicar", "proposta", "contrato"):
        slug = kwargs.get("slug", "")
        if not slug:
            return f"[PROSPECTOR] informe 'slug' para {action}"
        try:
            res = getattr(service, action)(slug, kwargs.get("simular"))
            return f"[PROSPECTOR] {action}: " + (res.get("mensagem") or res.get("erro", ""))
        except Exception as e:
            return f"[PROSPECTOR] Erro: {e}"

    if action == "followups":
        try:
            res = service.followups(kwargs.get("simular"))
            return "[PROSPECTOR] followups: " + (res.get("mensagem") or res.get("erro", ""))
        except Exception as e:
            return f"[PROSPECTOR] Erro: {e}"

    if action == "fechar":
        slug = kwargs.get("slug", "")
        valor = kwargs.get("valor")
        if not slug or valor is None:
            return "[PROSPECTOR] informe 'slug' e 'valor'"
        try:
            res = service.fechar(slug, valor, kwargs.get("manutencao"))
            return "[PROSPECTOR] fechar: " + (res.get("mensagem") or res.get("erro", ""))
        except Exception as e:
            return f"[PROSPECTOR] Erro: {e}"

    return f"[PROSPECTOR] Acao desconhecida: {action}"


# ---------------------------------------------------------------------------
# Catalogo de ferramentas
# ---------------------------------------------------------------------------
TOOL_CATALOG = [
    {
        "name": "github",
        "description": "Executa comandos Git/GitHub: status, listar repositorios, commits, branches.",
        "schema": _github_schema,
        "run": _github_run,
    },
    {
        "name": "files",
        "description": "Le, escreve, lista e deleta arquivos no sistema de arquivos local.",
        "schema": _files_schema,
        "run": _files_run,
    },
    {
        "name": "terminal",
        "description": "Executa comandos no terminal do sistema operacional (shell).",
        "schema": _terminal_schema,
        "run": _terminal_run,
    },
    {
        "name": "sqlite",
        "description": "Executa consultas SQL e comandos em banco SQLite.",
        "schema": _sqlite_schema,
        "run": _sqlite_run,
    },
    {
        "name": "browser",
        "description": "Navega em paginas web e extrai texto, titulo ou links (somente leitura).",
        "schema": _browser_schema,
        "run": _browser_run,
    },
    {
        "name": "search",
        "description": "Pesquisa na web e retorna resultados com titulo, URL e snippet.",
        "schema": _search_schema,
        "run": _search_run,
    },
    {
        "name": "docgen",
        "description": "Gera documentos em markdown a partir de titulo e conteudo.",
        "schema": _docgen_schema,
        "run": _docgen_run,
    },
    {
        "name": "imggen",
        "description": "Gera imagens por IA a partir de descricao textual (placeholder — requer API externa).",
        "schema": _imggen_schema,
        "run": _imggen_run,
    },
    {
        "name": "http",
        "description": "Faz requisicoes HTTP/API (GET, POST, PUT, DELETE) para URLs externas.",
        "schema": _http_schema,
        "run": _http_run,
    },
    {
        "name": "prospector",
        "description": "Prospeccao de leads via Maquina de Leads: prospectar (buscar leads), redesenhar, publicar, proposta, contrato, followups, fechar, listar e status.",
        "schema": _prospector_schema,
        "run": _prospector_run,
    },
]


def get_tool_catalog():
    """Retorna o catalogo completo de ferramentas de sistema."""
    return list(TOOL_CATALOG)
