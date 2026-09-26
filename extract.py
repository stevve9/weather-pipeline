"""
extract.py
----------
Mengambil data cuaca saat ini (Current Weather Data) dari OpenWeather API
untuk beberapa kota, lalu menyimpannya sebagai file JSON mentah (raw layer).

"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# ----------------------------------------------------------------------
# Konfigurasi
# ----------------------------------------------------------------------

load_dotenv()  # baca API key dari file .env

API_KEY = os.getenv("OPENWEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# Kota yang mau dipantau. 
CITIES = [
    {"name": "Jakarta", "lat": -6.2088, "lon": 106.8456},
    {"name": "Bekasi", "lat": -6.2383, "lon": 107.0000},
    {"name": "Bandung", "lat": -6.9175, "lon": 107.6191},
    {"name": "Bogor", "lat": -6.5950, "lon": 106.8166},
    {"name": "Medan", "lat": 3.5952, "lon": 98.6722},
]

RAW_DATA_DIR = Path(__file__).parent / "data" / "raw"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
REQUEST_TIMEOUT_SECONDS = 10

# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "pipeline.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Fungsi utama
# ----------------------------------------------------------------------

def fetch_weather(city: dict) -> dict | None:
    """Ambil data cuaca untuk satu kota dari OpenWeather API."""
    params = {
        "lat": city["lat"],
        "lon": city["lon"],
        "appid": API_KEY,
        "units": "metric",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                BASE_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            logger.info(f"Berhasil ambil data cuaca untuk {city['name']}")
            return response.json()

        except requests.exceptions.HTTPError as e:
            logger.error(
                f"HTTP error untuk {city['name']} (percobaan {attempt}/{MAX_RETRIES}): {e}"
            )
            if response.status_code == 401:
                logger.error("API key tidak valid atau belum aktif. Cek file .env kamu.")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(
                f"Gagal konek untuk {city['name']} (percobaan {attempt}/{MAX_RETRIES}): {e}"
            )

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_SECONDS)

    logger.error(f"Gagal ambil data cuaca untuk {city['name']} setelah {MAX_RETRIES} percobaan.")
    return None


def save_raw_response(city_name: str, payload: dict, run_timestamp: str) -> Path:
    """Simpan response mentah dari API sebagai file JSON."""
    filename = f"{city_name.lower()}_{run_timestamp}.json"
    filepath = RAW_DATA_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return filepath


def run() -> list[Path]:
    """Menjalankan proses extract untuk semua kota di CITIES."""
    if not API_KEY:
        logger.error(
            "OPENWEATHER_API_KEY tidak ditemukan. "
            "Pastikan file .env sudah dibuat dan berisi API key."
        )
        return []

    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    saved_files = []

    logger.info(f"Mulai extract untuk {len(CITIES)} kota (run: {run_timestamp})")

    for city in CITIES:
        data = fetch_weather(city)
        if data is not None:
            # OpenWeather kadang membalas nama lokasi terdekat dari database
            # internalnya (misal nama kelurahan), bukan nama kota yang kita
            # minta. Supaya konsisten dengan tabel "cities" di database,
            # kita simpan nama kota yang KITA minta, bukan yang API balas.
            data["_queried_city"] = city["name"]
            filepath = save_raw_response(city["name"], data, run_timestamp)
            saved_files.append(filepath)

    logger.info(
        f"Selesai. {len(saved_files)}/{len(CITIES)} kota berhasil diambil datanya."
    )
    return saved_files


if __name__ == "__main__":
    run()