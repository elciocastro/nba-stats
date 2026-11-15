#!/usr/bin/env bash
# Atualização automática no WSL (ou Linux) via cron.
#
#   deploy/cron.sh instalar   # grava as linhas no crontab do usuário
#   deploy/cron.sh remover    # tira só as linhas do nba-stats
#   deploy/cron.sh mostrar    # o que está instalado
#
# Horários em America/Sao_Paulo (jogos da NBA vão até ~02h):
#   a cada 15 min, 10h-02h: atualizar (estatísticas, agenda, injury report, confere apostas)
#   06:00: sync-daily (fecha os jogos da madrugada)
#   06:30: backup do banco (mantém 14 cópias em data/backup)
#   12:00: saude (escreve ALERTA no log se a carga falhou ou está velha)
# flock evita duas cargas ao mesmo tempo. Logs em logs/cron.log.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
TAG="# nba-stats"
BIN="$DIR/.venv/bin/nbastats"
LOCK="/tmp/nba-stats.lock"
LOG="$DIR/logs/cron.log"

linhas() {
  local run="cd $DIR && flock -n $LOCK $BIN"
  cat <<EOF
*/15 0-2,10-23 * * * $run atualizar >> $LOG 2>&1 $TAG
0 6 * * * $run sync-daily >> $LOG 2>&1 $TAG
30 6 * * * cd $DIR && $BIN backup >> $LOG 2>&1 $TAG
0 12 * * * cd $DIR && $BIN saude >> $LOG 2>&1 $TAG
EOF
}

atual() { crontab -l 2>/dev/null | grep -v "$TAG" || true; }

case "${1:-mostrar}" in
  instalar)
    [ -x "$BIN" ] || { echo "Não achei $BIN (crie o .venv e rode pip install -e .)"; exit 1; }
    mkdir -p "$DIR/logs"
    { atual; linhas; } | crontab -
    echo "Instalado:"; crontab -l | grep "$TAG"
    systemctl is-active --quiet cron 2>/dev/null || service cron status >/dev/null 2>&1 \
      || echo "Atenção: o serviço cron não parece ativo (sudo service cron start)."
    ;;
  remover)
    atual | crontab -
    echo "Linhas do nba-stats removidas do crontab."
    ;;
  mostrar)
    crontab -l 2>/dev/null | grep "$TAG" || echo "(nada instalado)"
    ;;
  *)
    echo "uso: $0 instalar|remover|mostrar"; exit 2
    ;;
esac
