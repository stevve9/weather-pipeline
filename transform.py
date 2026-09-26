"""
transform.py
------------
Membaca semua file JSON mentah dari folder data/raw/ (hasil extract.py),
membersihkan/memformat datanya, lalu memasukkannya ke PostgreSQL.

"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

# ----------------------------------------------------------------------
# Konfigurasi koneksi database
# ----------------------------------------------------------------------

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "weather_db"),
    "user": os.getenv("DB_USER", "weather_user"),
    "password": os.getenv("DB_PASSWORD", "weather_pass"),
}

RAW_DATA_DIR = Path(__file__).parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------
# Logging (pakai file log yang sama dengan extract.py)
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
# Fungsi transform
# ----------------------------------------------------------------------

def parse_weather_json(raw: dict) -> dict | None:
    """
    Ambil field yang kita butuhkan dari response mentah OpenWeather API,
    lalu bentuk jadi dict yang siap dimasukkan ke database.
    Mengembalikan None kalau data tidak lengkap/tidak valid.
    """
    try:
        city_name = raw.get("_queried_city", raw.get("name"))
        temperature = raw["main"]["temp"]
        humidity = raw["main"]["humidity"]
        pressure = raw["main"]["pressure"]
        wind_speed = raw["wind"]["speed"]
        description = raw["weather"][0]["description"]
        # field "dt" dari API adalah unix timestamp (UTC)
        recorded_at = datetime.fromtimestamp(raw["dt"], tz=timezone.utc)

        # Data quality check sederhana: suhu di luar rentang wajar
        # kemungkinan besar data korup/salah parsing.
        if not (-50 <= temperature <= 60):
            logger.warning(
                f"Suhu tidak wajar untuk {city_name}: {temperature}°C — data dilewati"
            )
            return None

        return {
            "city_name": city_name,
            "temperature": temperature,
            "humidity": humidity,
            "pressure": pressure,
            "wind_speed": wind_speed,
            "description": description,
            "recorded_at": recorded_at,
        }

    except (KeyError, IndexError, TypeError) as e:
        logger.warning(f"Gagal parsing file JSON, field tidak lengkap: {e}")
        return None


def load_raw_files() -> list[dict]:
    """Membaca semua file JSON di data/raw/, parse, dan mengembalikan list data bersih."""
    raw_files = list(RAW_DATA_DIR.glob("*.json"))

    if not raw_files:
        logger.warning(f"Tidak ada file JSON ditemukan di {RAW_DATA_DIR}")
        return []

    logger.info(f"Ditemukan {len(raw_files)} file JSON untuk diproses")

    parsed_records = []
    for filepath in raw_files:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)

        record = parse_weather_json(raw)
        if record is not None:
            record["_source_file"] = filepath.name
            parsed_records.append(record)

    return parsed_records


# ----------------------------------------------------------------------
# Fungsi load ke PostgreSQL
# ----------------------------------------------------------------------

def get_city_id_map(conn) -> dict[str, int]:
    """
    Ambil mapping {nama_kota: city_id} dari tabel cities.
    Dipakai untuk tahu city_id mana yang harus dipasang di weather_readings,
    karena tabel itu hanya menyimpan city_id (foreign key), bukan nama kota.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM cities;")
        rows = cur.fetchall()
    return {name: city_id for city_id, name in rows}


def insert_weather_readings(conn, records: list[dict], city_id_map: dict[str, int]) -> int:
    """
    Masukkan semua record ke tabel weather_readings.
    Kalau ada kota di data JSON yang tidak ditemukan di tabel cities
    (misal kota lama yang sudah dihapus dari init.sql), record itu dilewati
    dengan warning, bukan bikin seluruh proses gagal.
    """
    inserted_count = 0

    with conn.cursor() as cur:
        for record in records:
            city_id = city_id_map.get(record["city_name"])

            if city_id is None:
                logger.warning(
                    f"Kota '{record['city_name']}' tidak ditemukan di tabel cities "
                    f"(file: {record['_source_file']}) — data dilewati. "
                    f"Cek apakah init.sql sudah sesuai dengan daftar kota terbaru."
                )
                continue

            cur.execute(
                """
                INSERT INTO weather_readings
                    (city_id, temperature, humidity, pressure,
                     wind_speed, weather_description, recorded_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    city_id,
                    record["temperature"],
                    record["humidity"],
                    record["pressure"],
                    record["wind_speed"],
                    record["description"],
                    record["recorded_at"],
                ),
            )
            inserted_count += 1

    conn.commit()
    return inserted_count


def archive_processed_files(records: list[dict]) -> None:
    """
    Pindahkan file JSON yang sudah berhasil diproses ke folder data/processed/.
    ini agar mencegah file yang sama diproses ulang kalau transform.py dijalankan
    lagi nanti, sekaligus jadi arsip data mentah untuk keperluan audit/debug.
    """
    for record in records:
        source_path = RAW_DATA_DIR / record["_source_file"]
        if source_path.exists():
            destination_path = PROCESSED_DIR / record["_source_file"]
            source_path.rename(destination_path)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def run() -> None:
    records = load_raw_files()

    if not records:
        logger.info("Tidak ada data valid untuk diproses. Selesai.")
        return

    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as e:
        logger.error(
            f"Gagal konek ke database: {e}\n"
            f"Pastikan PostgreSQL sudah jalan (docker compose up -d) "
            f"dan konfigurasi di DB_CONFIG sudah benar."
        )
        return

    try:
        city_id_map = get_city_id_map(conn)
        inserted_count = insert_weather_readings(conn, records, city_id_map)
        logger.info(
            f"Berhasil insert {inserted_count}/{len(records)} record ke weather_readings."
        )

        archive_processed_files(records)
        logger.info(f"File JSON yang berhasil diproses dipindah ke {PROCESSED_DIR}")

    finally:
        conn.close()


if __name__ == "__main__":
    run()