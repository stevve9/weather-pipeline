CREATE TABLE IF NOT EXISTS cities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    lat NUMERIC(9, 6) NOT NULL,
    lon NUMERIC(9, 6) NOT NULL
);

CREATE TABLE IF NOT EXISTS weather_readings (
    id SERIAL PRIMARY KEY,
    city_id INTEGER NOT NULL REFERENCES cities(id),
    temperature NUMERIC(5, 2),
    humidity INTEGER,
    pressure INTEGER,
    wind_speed NUMERIC(5, 2),
    weather_description VARCHAR(255),
    recorded_at TIMESTAMPTZ NOT NULL,
    inserted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_weather_city_time
    ON weather_readings (city_id, recorded_at);

INSERT INTO cities (name, lat, lon) VALUES
    ('Jakarta', -6.2088, 106.8456),
    ('Bekasi', -6.2383, 107.0000),
    ('Bandung', -6.9175, 107.6191),
    ('Bogor', -6.5950, 106.8166),
    ('Medan', 3.5952, 98.6722)
ON CONFLICT (name) DO NOTHING;