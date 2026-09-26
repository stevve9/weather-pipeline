"""
scheduler.py
------------
Menjalankan extract.py -> transform.py secara berkala (default: tiap jam),
tanpa perlu kamu run manual terus-menerus.

"""

import logging
import time
from pathlib import Path

import schedule

import extract
import transform

# ----------------------------------------------------------------------
# Konfigurasi
# ----------------------------------------------------------------------

INTERVAL_HOURS = 1 

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "pipeline.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def run_pipeline() -> None:
    """Menjalankan extract lalu transform secara berurutan, dengan error handling."""
    logger.info("=" * 60)
    logger.info("Memulai siklus pipeline (extract -> transform)")

    try:
        extract.run()
    except Exception as e:
        logger.error(f"Extract gagal dengan error tak terduga: {e}")
        return  # tidak lanjut ke transform kalau extract gagal total

    try:
        transform.run()
    except Exception as e:
        logger.error(f"Transform gagal dengan error tak terduga: {e}")

    logger.info("Siklus pipeline selesai")


def main() -> None:
    logger.info(
        f"Scheduler dimulai. Pipeline akan jalan tiap {INTERVAL_HOURS} jam. "
        f"Tekan Ctrl+C untuk berhenti."
    )
    run_pipeline()

    schedule.every(INTERVAL_HOURS).hours.do(run_pipeline)

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # cek jadwal tiap 30 detik, tidak perlu lebih sering
    except KeyboardInterrupt:
        logger.info("Scheduler dihentikan oleh user (Ctrl+C).")


if __name__ == "__main__":
    main()