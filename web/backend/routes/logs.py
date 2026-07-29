"""
Rotas de logs — filtros, consulta, metricas.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/logs")
def listar_logs(limite: int = 100, agente: str = "", erro: bool = False):
    from services.activity_logger import ActivityLogger
    al = ActivityLogger()
    if erro:
        return al.erros(limite)
    if agente:
        return al.por_agente(agente, limite)
    return al.ultimos(limite)


@router.get("/logs/metricas")
def metricas():
    """Metricas agregadas dos logs."""
    from database.connection import get_connection
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) as t FROM logs_atividade").fetchone()[0]
    erros = conn.execute("SELECT COUNT(*) as t FROM logs_atividade WHERE erro!=''").fetchone()[0]
    media_tempo = conn.execute("SELECT COALESCE(AVG(duracao_ms), 0) as m FROM logs_atividade").fetchone()[0]
    top_agentes = conn.execute(
        "SELECT agente, COUNT(*) as total FROM logs_atividade "
        "WHERE agente!='' GROUP BY agente ORDER BY total DESC LIMIT 5"
    ).fetchall()
    top_ferramentas = conn.execute(
        "SELECT ferramenta, COUNT(*) as total FROM logs_atividade "
        "WHERE ferramenta!='' GROUP BY ferramenta ORDER BY total DESC LIMIT 5"
    ).fetchall()
    return {
        "total": total,
        "erros": erros,
        "media_tempo_ms": round(media_tempo, 1),
        "top_agentes": [dict(r) for r in top_agentes],
        "top_ferramentas": [dict(r) for r in top_ferramentas],
    }
