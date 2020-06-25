#!/usr/bin/env bash
# Agarda á rede antes de abrir o espello (arranque automatico na Pi).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export DISPLAY="${DISPLAY:-:0}"
LOG="$SCRIPT_DIR/smartmirror.log"

log() {
  echo "$(date -Iseconds) run-mirror: $*" >> "$LOG"
}

log "agardando rede..."
for i in $(seq 1 90); do
  if ping -c1 -W2 1.1.1.1 >/dev/null 2>&1 || ping -c1 -W2 8.8.8.8 >/dev/null 2>&1; then
    log "rede dispoñible (intento $i)"
    break
  fi
  if [[ "$i" -eq 90 ]]; then
    log "rede non detectada; iniciando igualmente"
  fi
  sleep 2
done

sleep 3
/usr/bin/xset s off -dpms s noblank 2>/dev/null || true
log "lanzando smartmirror.py"
exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/smartmirror.py"
