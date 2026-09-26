"""
app.py
------
Dashboard Streamlit untuk memvisualisasikan data cuaca yang sudah
tersimpan di PostgreSQL (hasil dari extract.py -> transform.py).

"""

import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "weather_db"),
    "user": os.getenv("DB_USER", "weather_user"),
    "password": os.getenv("DB_PASSWORD", "weather_pass"),
}

st.set_page_config(
    page_title="Weather Data Pipeline",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------
# Custom CSS
# ----------------------------------------------------------------------
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        .app-title {
            font-size: 2.1rem;
            font-weight: 800;
            margin-bottom: 0.1rem;
        }
        .app-subtitle {
            color: rgba(250, 250, 250, 0.6);
            font-size: 0.95rem;
            margin-bottom: 1.6rem;
        }

        .weather-card {
            background: linear-gradient(145deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
            border: 1px solid rgba(255,255,255,0.08);
            border-left: 4px solid var(--accent-color, #4DABF7);
            border-radius: 14px;
            padding: 1.1rem 1.3rem;
            margin-bottom: 0.8rem;
        }
        .weather-card-city {
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.15rem;
        }
        .weather-card-desc {
            color: rgba(250, 250, 250, 0.55);
            font-size: 0.82rem;
            text-transform: capitalize;
            margin-bottom: 0.6rem;
        }
        .weather-card-temp {
            font-size: 2.1rem;
            font-weight: 800;
            line-height: 1;
            display: inline-block;
            margin-right: 0.5rem;
        }
        .weather-card-icon {
            font-size: 2.1rem;
            display: inline-block;
            vertical-align: middle;
        }
        .weather-card-meta {
            margin-top: 0.7rem;
            font-size: 0.8rem;
            color: rgba(250, 250, 250, 0.6);
            display: flex;
            gap: 1rem;
        }

        .summary-strip {
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        .summary-box {
            flex: 1;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 12px;
            padding: 0.9rem 1.1rem;
        }
        .summary-box-label {
            font-size: 0.78rem;
            color: rgba(250, 250, 250, 0.55);
            margin-bottom: 0.2rem;
        }
        .summary-box-value {
            font-size: 1.5rem;
            font-weight: 700;
        }

        .section-heading {
            font-size: 1.15rem;
            font-weight: 700;
            margin-top: 0.5rem;
            margin-bottom: 0.8rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

CITY_COLORS = [
    "#4DABF7",
    "#FF6B6B",
    "#69DB7C",
    "#FFD43B",
    "#DA77F2",
    "#FF922B",
]

PLOTLY_TEMPLATE = "plotly_dark"


def weather_icon(description: str) -> str:
    """Petakan deskripsi cuaca (teks bebas dari API) ke emoji yang representatif."""
    desc = (description or "").lower()
    if "thunder" in desc or "petir" in desc:
        return "⛈️"
    if "snow" in desc:
        return "🌨️"
    if "rain" in desc or "drizzle" in desc:
        return "🌧️"
    if "cloud" in desc:
        if "few" in desc or "scatter" in desc:
            return "🌤️"
        return "☁️"
    if "clear" in desc:
        return "☀️"
    if "mist" in desc or "fog" in desc or "haze" in desc:
        return "🌫️"
    return "🌡️"


@st.cache_data(ttl=60)
def load_weather_data() -> pd.DataFrame:
    """Ambil seluruh data weather_readings, join dengan nama kota."""
    connection_url = (
        f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
    )
    engine = create_engine(connection_url)

    query = """
        SELECT
            c.name AS city,
            w.temperature,
            w.humidity,
            w.pressure,
            w.wind_speed,
            w.weather_description,
            w.recorded_at
        FROM weather_readings w
        JOIN cities c ON w.city_id = c.id
        ORDER BY w.recorded_at ASC;
    """
    df = pd.read_sql(query, engine)
    engine.dispose()
    return df


st.markdown('<div class="app-title">Weather Data Pipeline</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Data cuaca real-time dari OpenWeather API — '
    "diproses lewat pipeline Python, disimpan di PostgreSQL, dan dijadwalkan "
    "otomatis tiap jam.</div>",
    unsafe_allow_html=True,
)

try:
    df = load_weather_data()
except Exception:
    st.error(
        "Gagal konek ke database. Pastikan PostgreSQL sudah jalan "
        "(`docker compose up -d`) dan konfigurasi koneksi sudah benar."
    )
    st.stop()

if df.empty:
    st.warning(
        "Belum ada data di database. Jalankan `extract.py` lalu `transform.py` "
        "dulu sebelum membuka dashboard ini."
    )
    st.stop()

st.sidebar.header("Filter")
all_cities = sorted(df["city"].unique())
color_map = {city: CITY_COLORS[i % len(CITY_COLORS)] for i, city in enumerate(all_cities)}

selected_cities = st.sidebar.multiselect(
    "Pilih kota", options=all_cities, default=all_cities
)

st.sidebar.divider()
st.sidebar.caption(
    f"Auto-refresh cache tiap 60 detik.\n\nTerakhir dimuat: "
    f"{datetime.now().strftime('%H:%M:%S')}"
)

df_filtered = df[df["city"].isin(selected_cities)]

if df_filtered.empty:
    st.info("Pilih minimal satu kota di sidebar untuk menampilkan data.")
    st.stop()

latest_per_city = (
    df_filtered.sort_values("recorded_at").groupby("city").tail(1).set_index("city")
)

summary_html = f"""
<div class="summary-strip">
    <div class="summary-box">
        <div class="summary-box-label">JUMLAH KOTA</div>
        <div class="summary-box-value">{len(selected_cities)}</div>
    </div>
    <div class="summary-box">
        <div class="summary-box-label">TOTAL PEMBACAAN DATA</div>
        <div class="summary-box-value">{len(df_filtered)}</div>
    </div>
    <div class="summary-box">
        <div class="summary-box-label">SUHU RATA-RATA TERKINI</div>
        <div class="summary-box-value">{latest_per_city['temperature'].mean():.1f}°C</div>
    </div>
    <div class="summary-box">
        <div class="summary-box-label">KELEMBABAN RATA-RATA</div>
        <div class="summary-box-value">{latest_per_city['humidity'].mean():.0f}%</div>
    </div>
</div>
"""
st.markdown(summary_html, unsafe_allow_html=True)

st.markdown('<div class="section-heading">Kondisi Terkini</div>', unsafe_allow_html=True)

card_cols = st.columns(min(len(selected_cities), 5) or 1)
for i, city in enumerate(latest_per_city.index):
    row = latest_per_city.loc[city]
    icon = weather_icon(row["weather_description"])
    accent = color_map.get(city, "#4DABF7")

    card_html = f"""
    <div class="weather-card" style="--accent-color: {accent};">
        <div class="weather-card-city">{city}</div>
        <div class="weather-card-desc">{row['weather_description']}</div>
        <span class="weather-card-icon">{icon}</span>
        <span class="weather-card-temp">{row['temperature']:.1f}°C</span>
        <div class="weather-card-meta">
            <span>Kelembaban: {row['humidity']:.0f}%</span>
            <span>Angin: {row['wind_speed']:.1f} m/s</span>
            <span>{row['recorded_at'].strftime('%H:%M')}</span>
        </div>
    </div>
    """
    card_cols[i % len(card_cols)].markdown(card_html, unsafe_allow_html=True)

st.divider()

tab_temp, tab_humidity, tab_raw = st.tabs(["Tren Suhu", "Tren Kelembaban", "Data Mentah"])

with tab_temp:
    fig_temp = px.line(
        df_filtered,
        x="recorded_at",
        y="temperature",
        color="city",
        color_discrete_map=color_map,
        template=PLOTLY_TEMPLATE,
        labels={"recorded_at": "Waktu", "temperature": "Suhu (°C)", "city": "Kota"},
        markers=True,
    )
    fig_temp.update_layout(
        margin=dict(l=10, r=10, t=20, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    fig_temp.update_traces(line=dict(width=2.5), marker=dict(size=6))
    st.plotly_chart(fig_temp, width="stretch")

with tab_humidity:
    fig_humidity = px.line(
        df_filtered,
        x="recorded_at",
        y="humidity",
        color="city",
        color_discrete_map=color_map,
        template=PLOTLY_TEMPLATE,
        labels={"recorded_at": "Waktu", "humidity": "Kelembaban (%)", "city": "Kota"},
        markers=True,
    )
    fig_humidity.update_layout(
        margin=dict(l=10, r=10, t=20, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    fig_humidity.update_traces(line=dict(width=2.5), marker=dict(size=6))
    st.plotly_chart(fig_humidity, width="stretch")

with tab_raw:
    display_cols = [
        "city", "temperature", "humidity", "pressure",
        "wind_speed", "weather_description", "recorded_at",
    ]
    st.dataframe(
        df_filtered[display_cols]
        .sort_values("recorded_at", ascending=False)
        .rename(
            columns={
                "city": "Kota",
                "temperature": "Suhu (°C)",
                "humidity": "Kelembaban (%)",
                "pressure": "Tekanan (hPa)",
                "wind_speed": "Angin (m/s)",
                "weather_description": "Deskripsi",
                "recorded_at": "Waktu Pembacaan",
            }
        ),
        width="stretch",
        hide_index=True,
    )