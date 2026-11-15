# nba-stats: site novo (API FastAPI + React) na porta 8000 e, com outro
# comando, o site antigo (Streamlit) na 8501. Banco num volume em /app/data.
#   docker build -t nba-stats .
#   docker run -d -p 8000:8000 -v $PWD/data:/app/data -e NBASTATS_PASSWORD=... nba-stats
#   docker run -d -p 8501:8501 ... nba-stats streamlit run src/nbastats/web/app.py \
#       --server.address=0.0.0.0 --server.headless=true

FROM node:22-slim AS front
WORKDIR /front
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    NBASTATS_DB=/app/data/nba.db TZ=America/Sao_Paulo

# fuso: "hoje" no site segue o horário de Brasília, não o UTC do contêiner
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[web,nbaapi,injury,api]" \
    && useradd --create-home --uid 1000 app \
    && mkdir -p /app/data && chown app /app/data
COPY config ./config
COPY .streamlit ./.streamlit
COPY --from=front /front/dist ./frontend/dist

USER app
EXPOSE 8000 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c \
    "import urllib.request as u; [u.urlopen(f'http://localhost:{p}') for p in ('8000/api/saude',)]" \
    || python -c "import urllib.request as u; u.urlopen('http://localhost:8501/_stcore/health')"
CMD ["uvicorn", "nbastats.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
