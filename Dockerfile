# Site nba-stats (Streamlit). O banco fica num volume em /app/data.
#   docker build -t nba-stats .
#   docker run -d -p 8501:8501 -v $PWD/data:/app/data -e NBASTATS_PASSWORD=... nba-stats
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    NBASTATS_DB=/app/data/nba.db TZ=America/Sao_Paulo

# fuso: "hoje" no site segue o horário de Brasília, não o UTC do contêiner
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[web,nbaapi,injury]" \
    && useradd --create-home --uid 1000 app \
    && mkdir -p /app/data && chown app /app/data
COPY config ./config
COPY .streamlit ./.streamlit

USER app
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["streamlit", "run", "src/nbastats/web/app.py", "--server.address=0.0.0.0", \
     "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
