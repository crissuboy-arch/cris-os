"""
API REST do CRIS OS Dashboard.

Reutiliza toda a arquitetura existente (services, database, agents, tools).
Nao duplica codigo — apenas expoe endpoints HTTP.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

# Garante que o projeto esta no path
RAIZ = Path(__file__).resolve().parent.parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database.schema import criar_tabelas

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("crisos-api")

app = FastAPI(title="CRIS OS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    criar_tabelas()


# Importa rotas
from web.backend.routes import system, agents, chat, memory, clients, projects, tasks, prompts, logs, settings, studio

app.include_router(system.router, prefix="/api", tags=["Sistema"])
app.include_router(agents.router, prefix="/api", tags=["Agentes"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(memory.router, prefix="/api", tags=["Memoria"])
app.include_router(clients.router, prefix="/api", tags=["Clientes"])
app.include_router(projects.router, prefix="/api", tags=["Projetos"])
app.include_router(tasks.router, prefix="/api", tags=["Tarefas"])
app.include_router(prompts.router, prefix="/api", tags=["Prompts"])
app.include_router(logs.router, prefix="/api", tags=["Logs"])
app.include_router(settings.router, prefix="/api", tags=["Configuracoes"])
app.include_router(studio.router, prefix="/api", tags=["Studio"])

# Serve frontend estatico em producao
FRONTEND_DIST = RAIZ / "web" / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
