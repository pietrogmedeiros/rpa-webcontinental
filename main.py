import logging
import os
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from pipedrive import run as pipedrive_run
from gdrive import upload as gdrive_upload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

RUN_HOUR   = int(os.environ.get("RUN_HOUR", 7))
RUN_MINUTE = int(os.environ.get("RUN_MINUTE", 0))
TIMEZONE   = os.environ.get("TZ", "America/Sao_Paulo")


def job():
    logger.info("═══ Iniciando job RPA ═══")
    try:
        csv_path = pipedrive_run()
        link     = gdrive_upload(csv_path)
        logger.info(f"✅ Concluído! Arquivo disponível em: {link}")
    except Exception as exc:
        logger.error(f"❌ Job falhou: {exc}", exc_info=True)


if __name__ == "__main__":
    logger.info(f"Agendador iniciado — rodará todo dia às {RUN_HOUR:02d}:{RUN_MINUTE:02d} ({TIMEZONE})")

    if os.environ.get("RUN_ON_START", "false").lower() == "true":
        logger.info("RUN_ON_START=true → executando agora...")
        job()

    scheduler = BlockingScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        job,
        CronTrigger(hour=RUN_HOUR, minute=RUN_MINUTE, timezone=TIMEZONE),
    )
    scheduler.start()
