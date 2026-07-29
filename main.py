"""
CRIS OS - Ponto de entrada.

Monta o sistema (via core/runtime.py) e inicia os canais. A lógica de montagem
fica no runtime; aqui só cuidamos de logs e de iniciar/parar com elegância.

Rode com:  python main.py
"""

import logging
import sys

from config.settings import settings
from core.runtime import StartupError, build


def configurar_logs() -> None:
    """Configura logs no console e em arquivo (sem emojis, por causa do Windows)."""
    settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(settings.LOGS_DIR / "cris_os.log", encoding="utf-8"),
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


def main() -> int:
    configurar_logs()
    logger = logging.getLogger("cris-os")
    logger.info("Iniciando o CRIS OS...")

    from config.settings import settings as s

    logger.info("ODS: %s (URL: %s | Fallback: %s)",
                "ativo" if s.ODS_ENABLED else "inativo",
                s.ODS_BASE_URL if s.ODS_ENABLED else "-",
                s.ODS_FALLBACK_PROVIDER if s.ODS_ENABLED else "-")

    try:
        app = build()
    except StartupError as exc:
        logger.error("Nao foi possivel iniciar:\n%s", exc)
        return 1

    ods_status = ""
    if app.ods_client:
        ods_status = " | ODS: " + ("online" if app.ods_client.is_online() else "offline")

    logger.info("Tudo pronto! Abra o Telegram e fale com o seu bot.%s (Ctrl+C para parar)", ods_status)

    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("CRIS OS encerrado. Ate logo, Cris!")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
