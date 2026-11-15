#!/usr/bin/env bash
# Sobe (ou atualiza) o site numa VPS com Docker, com o código do commit atual.
#
#   deploy/vps.sh subir     [root@IP]   # código novo; banco inteiro só na 1ª vez, depois só as estatísticas
#   deploy/vps.sh dados     [root@IP]   # só as estatísticas do computador (sem reiniciar o site)
#   deploy/vps.sh ajustes   [root@IP]   # envia data/ajustes (configurações da Administração) e reinicia
#   deploy/vps.sh status    [root@IP]   # contêiner, última atualização dos dados e endereço
#   deploy/vps.sh pausar    [root@IP]   # tira do ar sem apagar nada ("em manutenção" no endereço)
#   deploy/vps.sh retomar   [root@IP]   # volta ao ar
#   deploy/vps.sh desativar [root@IP]   # baixa o banco da VPS para data/backup e remove tudo
#                                       # (contêiner, imagem, /opt/nba-stats e o site no Caddy)
#   deploy/vps.sh senha     [root@IP]   # senha única (só vale enquanto não houver usuários)
#
# Banco: na primeira subida vai o data/nba.db inteiro (com os usuários). Depois,
# a VPS é a dona do que se faz no site (logins, sessões, apostas, linhas,
# favoritos) e do computador só vão as estatísticas: `nbastats importar-dados`
# faz upsert das tabelas de dados e não toca nas de uso (src/nbastats/db).
#
# Variáveis: VPS (padrão root@45.159.173.222), SSH_KEY (~/.ssh/netsentinel-vps),
# PORTA (8100), PORTA_ANTIGO (vazio = não sobe o Streamlit; 8501 para subir),
# DOMINIO (com HTTPS atrás de um Caddy: o contêiner entra na rede REDE, padrão
# netsentinel_default, com o nome nba-stats, e a porta fica só em 127.0.0.1;
# fica gravado na VPS, então só precisa ser passado uma vez).
set -euo pipefail
cd "$(dirname "$0")/.."

ACAO="${1:-subir}"
VPS="${2:-${VPS:-root@45.159.173.222}}"
KEY="${SSH_KEY:-$HOME/.ssh/netsentinel-vps}"
PORTA="${PORTA:-8100}"
PORTA_ANTIGO="${PORTA_ANTIGO-}"
DOMINIO="${DOMINIO:-}"
REDE="${REDE:-netsentinel_default}"
DIR=/opt/nba-stats
PY="${PY:-.venv/bin/python}"
r() { ssh -i "$KEY" -o BatchMode=yes "$VPS" "$@"; }
# O domínio fica gravado na VPS: quem rodar o script sem DOMINIO não tira o
# site do Caddy por engano. DOMINIO=- volta para HTTP na porta (teste).
if [ "$ACAO" != senha ]; then
  if [ -z "$DOMINIO" ]; then DOMINIO=$(r "cat $DIR/dominio 2>/dev/null" || true)
  elif [ "$DOMINIO" = - ]; then DOMINIO=""; r "rm -f $DIR/dominio"
  else r "mkdir -p $DIR && echo '$DOMINIO' > $DIR/dominio"; fi
fi

# Cópia consistente mesmo com o cron gravando (API de backup do SQLite).
copia_local() {
  [ -f data/nba.db ] || { echo "data/nba.db não existe: rode nbastats atualizar antes"; exit 1; }
  "$PY" - "$1" <<'EOF'
import sqlite3, sys
src = sqlite3.connect("file:data/nba.db?mode=ro", uri=True)
dst = sqlite3.connect(sys.argv[1])
src.backup(dst)
dst.close(); src.close()
EOF
}

# Caddy do NetSentinel: o bloco do site fica em /config/sites (volume
# caddy-config). Recarrega a partir de uma cópia do Caddyfile do host, porque
# o contêiner pode estar preso a uma versão antiga do arquivo (0013).
CADDY=netsentinel-caddy-1
SITES=/var/lib/docker/volumes/netsentinel_caddy-config/_data/sites
recarregar_caddy() {
  r "set -e; V=\$(dirname $SITES)
     cp /opt/netsentinel/deploy/Caddyfile \$V/Caddyfile.ativo
     docker exec $CADDY caddy validate --config /config/Caddyfile.ativo --adapter caddyfile >/dev/null 2>&1
     docker exec $CADDY caddy reload --config /config/Caddyfile.ativo --adapter caddyfile >/dev/null 2>&1"
  echo "Caddy recarregado."
}

tem_banco() { r "test -s $DIR/data/nba.db"; }

banco_inteiro() {
  local tmp; tmp=$(mktemp --suffix=.db); copia_local "$tmp"
  r "mkdir -p $DIR/data"
  scp -q -i "$KEY" "$tmp" "$VPS:$DIR/data/nba.db"; rm -f "$tmp"
  r "chown -R 1000:1000 $DIR/data"
  echo "Banco inteiro enviado (primeira subida: leva os usuários)."
}

so_estatisticas() {
  local tmp; tmp=$(mktemp --suffix=.db); copia_local "$tmp"
  scp -q -i "$KEY" "$tmp" "$VPS:$DIR/data/entrada.db"; rm -f "$tmp"
  r "chown 1000:1000 $DIR/data/entrada.db
     docker exec nba-stats nbastats importar-dados /app/data/entrada.db; rm -f $DIR/data/entrada.db"
}

enviar_ajustes() {
  [ -d data/ajustes ] && ls data/ajustes/*.yaml >/dev/null 2>&1 || { echo "Sem data/ajustes para enviar."; return; }
  r "mkdir -p $DIR/data/ajustes"
  scp -q -i "$KEY" data/ajustes/*.yaml "$VPS:$DIR/data/ajustes/"
  r "chown -R 1000:1000 $DIR/data/ajustes"
  echo "Configurações da Administração enviadas."
}

reiniciar() {
  local pub="-p $PORTA:8000" rede=""
  if [ -n "$DOMINIO" ]; then
    pub="-p 127.0.0.1:$PORTA:8000"
    rede="--network $REDE --network-alias nba-stats"
  fi
  r "docker rm -f nba-stats nba-stats-antigo >/dev/null 2>&1 || true
     docker run -d --name nba-stats --restart unless-stopped --memory 512m --cpus 0.5 $rede \
       $pub --env-file $DIR/.env -v $DIR/data:/app/data nba-stats:atual >/dev/null
     if [ -n '$PORTA_ANTIGO' ]; then
       docker run -d --name nba-stats-antigo --restart unless-stopped --memory 384m --cpus 0.5 \
         -p $PORTA_ANTIGO:8501 --env-file $DIR/.env -v $DIR/data:/app/data nba-stats:atual \
         streamlit run src/nbastats/web/app.py --server.address=0.0.0.0 --server.headless=true \
         --browser.gatherUsageStats=false >/dev/null
     fi
     for i in \$(seq 60); do curl -sf localhost:$PORTA/api/saude >/dev/null && break; sleep 1; done
     docker ps --filter name=nba-stats --format '{{.Names}} {{.Status}}'"
  endereco
}

endereco() {
  if [ -n "$DOMINIO" ]; then echo "Site: https://$DOMINIO"
  else echo "Site: http://${VPS#*@}:$PORTA (HTTP sem cadeado: só para teste)"; fi
  [ -n "$PORTA_ANTIGO" ] && echo "Site antigo: http://${VPS#*@}:$PORTA_ANTIGO"
  return 0
}

case "$ACAO" in
  subir)
    [ -z "$(git status --porcelain -- src config frontend Dockerfile pyproject.toml)" ] \
      || echo "Aviso: há mudanças não commitadas; sobe o último commit ($(git rev-parse --short HEAD))."
    r "mkdir -p $DIR/src && rm -rf $DIR/src/*"
    git archive HEAD | r "tar -x -C $DIR/src"
    r "cd $DIR && [ -f .env ] || (umask 077; echo NBASTATS_PASSWORD=\$(openssl rand -base64 18 | tr -d '/+=') > .env)"
    primeira=0; tem_banco || primeira=1
    [ "$primeira" = 1 ] && { banco_inteiro; enviar_ajustes; }
    r "docker build -q -t nba-stats:atual $DIR/src >/dev/null"
    reiniciar
    if [ -n "$DOMINIO" ] && ! r "cmp -s $SITES/nba.caddy -" < <(sed "s/^DOMINIO {/$DOMINIO {/" deploy/nba.caddy); then
      sed "s/^DOMINIO {/$DOMINIO {/" deploy/nba.caddy | r "mkdir -p $SITES && cat > $SITES/nba.caddy"
      recarregar_caddy
    fi
    [ "$primeira" = 1 ] || so_estatisticas ;;
  dados) so_estatisticas ;;
  ajustes) enviar_ajustes; reiniciar ;;
  status)
    r "docker ps --filter name=nba-stats --format '{{.Names}} {{.Status}}'
       docker exec nba-stats python -c \"import sqlite3; c = sqlite3.connect('/app/data/nba.db'); print('dados de', c.execute(\\\"SELECT MAX(finished_at) FROM sync_log WHERE kind = 'refresh' AND status = 'ok'\\\").fetchone()[0], 'UTC')\""
    endereco ;;
  pausar)
    r "docker stop nba-stats >/dev/null && echo 'Site parado (dados mantidos em $DIR/data).'"
    [ -n "$DOMINIO" ] && echo "https://$DOMINIO mostra \"em manutenção\". Para voltar: deploy/vps.sh retomar"
    ;;
  retomar)
    r "docker start nba-stats >/dev/null
       for i in \$(seq 60); do curl -sf localhost:$PORTA/api/saude >/dev/null && break; sleep 1; done
       docker ps --filter name=nba-stats --format '{{.Names}} {{.Status}}'"
    endereco ;;
  desativar)
    mkdir -p data/backup
    copia="data/backup/vps-$(date +%Y%m%d-%H%M).db"
    if r "test -s $DIR/data/nba.db"; then
      r "docker exec nba-stats python -c \"import sqlite3; s = sqlite3.connect('/app/data/nba.db'); d = sqlite3.connect('/app/data/saida.db'); s.backup(d); d.close()\"" 2>/dev/null \
        || r "cp $DIR/data/nba.db $DIR/data/saida.db"
      scp -q -i "$KEY" "$VPS:$DIR/data/saida.db" "$copia" && echo "Banco da VPS (logins, apostas, linhas) salvo em $copia"
    fi
    r "docker rm -f nba-stats nba-stats-antigo >/dev/null 2>&1 || true; docker rmi nba-stats:atual nba-stats:teste >/dev/null 2>&1 || true; rm -rf $DIR"
    if r "test -f $SITES/nba.caddy"; then r "rm -f $SITES/nba.caddy"; recarregar_caddy; fi
    echo "Desativado em $VPS. Para subir de novo: DOMINIO=... deploy/vps.sh subir (o Caddy precisa do bloco em $SITES)." ;;
  senha) r "cut -d= -f2- $DIR/.env" ;;
  *) sed -n '2,19p' "$0"; exit 1 ;;
esac
