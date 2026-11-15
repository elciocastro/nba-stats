#!/usr/bin/env bash
# Sobe (ou atualiza) o site numa VPS com Docker, com o código do commit atual
# e o banco local (data/nba.db). Também desativa.
#
#   deploy/vps.sh subir     [root@IP]   # código + dados novos, reconstrói e reinicia
#   deploy/vps.sh dados     [root@IP]   # só copia o banco novo e reinicia
#   deploy/vps.sh desativar [root@IP]   # remove contêiner, imagem e /opt/nba-stats
#   deploy/vps.sh senha     [root@IP]   # mostra a senha do site (gerada na VPS)
#
# Variáveis: VPS (padrão root@45.159.173.222), SSH_KEY (~/.ssh/netsentinel-vps),
# PORTA (8501). A senha é gerada na VPS na primeira subida e fica em
# /opt/nba-stats/.env; nunca sai da VPS nem vai para o Git.
set -euo pipefail
cd "$(dirname "$0")/.."

ACAO="${1:-subir}"
VPS="${2:-${VPS:-root@45.159.173.222}}"
KEY="${SSH_KEY:-$HOME/.ssh/netsentinel-vps}"
PORTA="${PORTA:-8501}"
DIR=/opt/nba-stats
r() { ssh -i "$KEY" -o BatchMode=yes "$VPS" "$@"; }

copiar_dados() {
  [ -f data/nba.db ] || { echo "data/nba.db não existe: rode nbastats atualizar antes"; exit 1; }
  sqlite3 data/nba.db ".backup /tmp/nba-deploy.db" 2>/dev/null || cp data/nba.db /tmp/nba-deploy.db
  r "mkdir -p $DIR/data"
  scp -q -i "$KEY" /tmp/nba-deploy.db "$VPS:$DIR/data/nba.db"
  rm -f /tmp/nba-deploy.db
  r "chown -R 1000:1000 $DIR/data"
}

reiniciar() {
  r "docker rm -f nba-stats >/dev/null 2>&1 || true
     docker run -d --name nba-stats --restart unless-stopped --memory 512m --cpus 0.5 \
       -p $PORTA:8501 --env-file $DIR/.env -v $DIR/data:/app/data nba-stats:atual >/dev/null
     for i in \$(seq 40); do curl -sf localhost:$PORTA/_stcore/health >/dev/null && break; sleep 1; done
     docker ps --filter name=nba-stats --format '{{.Status}}'"
  echo "No ar: http://${VPS#*@}:$PORTA  (senha: deploy/vps.sh senha)"
}

case "$ACAO" in
  subir)
    [ -z "$(git status --porcelain -- src config .streamlit Dockerfile pyproject.toml)" ] \
      || echo "Aviso: há mudanças não commitadas; sobe o último commit ($(git rev-parse --short HEAD))."
    r "mkdir -p $DIR/src && rm -rf $DIR/src/*"
    git archive HEAD | r "tar -x -C $DIR/src"
    r "cd $DIR && [ -f .env ] || (umask 077; echo NBASTATS_PASSWORD=\$(openssl rand -base64 18 | tr -d '/+=') > .env)"
    copiar_dados
    r "docker build -q -t nba-stats:atual $DIR/src >/dev/null"
    reiniciar ;;
  dados) copiar_dados; reiniciar ;;
  desativar)
    r "docker rm -f nba-stats >/dev/null 2>&1 || true; docker rmi nba-stats:atual nba-stats:teste >/dev/null 2>&1 || true; rm -rf $DIR"
    echo "Desativado em $VPS." ;;
  senha) r "cut -d= -f2- $DIR/.env" ;;
  *) sed -n '2,12p' "$0"; exit 1 ;;
esac
