FROM python:3.12-slim

WORKDIR /app

# Copy requirements dulu (terpisah dari copy kode) supaya Docker bisa cache layer. 
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh kode Python project
COPY extract.py transform.py scheduler.py app.py ./

# Default command (dipakai kalau tidak di-override oleh docker-compose.yml)
CMD ["python", "scheduler.py"]
