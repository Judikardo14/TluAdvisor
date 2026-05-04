FROM python:3.11-slim

# Métadonnées HF Spaces
LABEL maintainer="Judikardo"
LABEL description="Jury IA — Génie en Herbe Bot"

WORKDIR /app

# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code
COPY app.py .
COPY rules.txt .

# Port exposé (HF Spaces attend le port 7860)
EXPOSE 7860

# Lancement
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
