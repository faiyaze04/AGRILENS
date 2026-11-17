#!/bin/bash
# AGRILENS exhibition launcher: runs the kiosk offline, writes a log with a health line every minute
# (CPU temperature, throttling, kiosk memory and CPU), and starts the kiosk again whenever it stops.
#   bash exhibition_launcher.sh               start now
#   bash exhibition_launcher.sh --autostart   start now AND make this launcher the boot application
# Why it restarts even after a normal exit: the Admin console opens without a password and has "CLOSE APPLICATION",
# so a visitor can close the kiosk. To stop the kiosk on purpose:  touch ~/.agrilens_stop   then close it (or Escape).
# The stop file is removed when the launcher next starts.
# At every start the rejection-gate values saved through the Admin sliders are removed from the settings files, so the kiosk
# always runs with the model's calibration (confidence 0.40, margin 0.12, logit 2.10). Language and camera settings are kept.
# Logs: ~/AGRILENS_logs/agrilens_<date>_<time>.log (the newest 30 are kept). More than 5 crashes (non-zero exits) within
# 10 minutes stops the launcher.
# Environment overrides (for testing): AGRILENS_APP_DIR, AGRILENS_LOG_DIR, AGRILENS_HEALTH_SECONDS, AGRILENS_PYTHON, AGRILENS_RESTART_DELAY
set -u
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
DIR="${AGRILENS_APP_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
LOGDIR="${AGRILENS_LOG_DIR:-$HOME/AGRILENS_logs}"
EVERY="${AGRILENS_HEALTH_SECONDS:-60}"
PY="${AGRILENS_PYTHON:-python3}"
DELAY="${AGRILENS_RESTART_DELAY:-3}"
STOP="$HOME/.agrilens_stop"
AUTOSTART=0; [ "${1:-}" = "--autostart" ] && AUTOSTART=1
[ -f "$DIR/main.py" ] || { echo "no main.py in $DIR"; exit 1; }
mkdir -p "$LOGDIR"
ls -1t "$LOGDIR"/agrilens_*.log 2>/dev/null | tail -n +31 | while read -r old; do rm -f "$old"; done
LOG="$LOGDIR/agrilens_$(date +%Y%m%d_%H%M%S).log"
rm -f "$STOP"
touch "$HOME/.agrilens_ota_hold"          # the 5.0.0 code skips its automatic boot update while this file exists
note() { echo "[launcher $(date '+%F %T')] $*" >> "$LOG"; }

reset_gates() {   # drop Admin-saved gate thresholds so the model calibration applies
  for f in "$HOME/.agrilens_kiosk_config.json" "$DIR/kiosk_config.json"; do
    [ -f "$f" ] || continue
    "$PY" - "$f" >> "$LOG" 2>&1 <<'EOF'
import json, sys
p = sys.argv[1]
try:
    d = json.load(open(p, encoding="utf-8"))
except Exception as e:
    print(f"[launcher] settings file {p} unreadable ({e}); the kiosk will use its defaults"); sys.exit(0)
keys = [k for k in ("confidence_threshold", "ood_margin", "ood_logit", "calibration_model_sha256") if k in d]
if keys:
    for k in keys: d.pop(k)
    json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
    print(f"[launcher] removed saved gate values {keys} from {p}")
EOF
  done
}

health() {   # $1 = kiosk pid
  while kill -0 "$1" 2>/dev/null; do
    sleep "$EVERY"; kill -0 "$1" 2>/dev/null || break
    T=$(vcgencmd measure_temp 2>/dev/null | cut -d= -f2); [ -z "$T" ] && T=$(awk '{printf "%.1fC", $1/1000}' /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
    TH=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
    RSS=$(ps -o rss= -p "$1" 2>/dev/null | tr -d ' '); CPU=$(ps -o %cpu= -p "$1" 2>/dev/null | tr -d ' ')
    MEM=$(awk '/MemAvailable/ {printf "%d MB", $2/1024}' /proc/meminfo 2>/dev/null)
    note "health temp=${T:-n/a} throttled=${TH:-n/a} kiosk_rss_kb=${RSS:-n/a} kiosk_cpu=${CPU:-n/a}% mem_available=${MEM:-n/a}"
  done
}

own_autostart() {   # main.py rewrites ~/.config/autostart/agrilens.desktop at every start; point it back at this launcher
  sleep 20
  D="$HOME/.config/autostart/agrilens.desktop"; mkdir -p "$(dirname "$D")"
  printf '[Desktop Entry]\nType=Application\nName=AGRILENS Kiosk (exhibition)\nComment=AGRILENS exhibition launcher\nExec=/bin/bash "%s" --autostart\nPath=%s\nTerminal=false\nX-GNOME-Autostart-enabled=true\n' "$SELF" "$DIR" > "$D"
  chmod 755 "$D"; note "boot application set to this launcher ($D)"
}

note "start: app $DIR, version $(grep -m1 '^APP_VERSION' "$DIR/main.py" | cut -d'"' -f2), model $(sha256sum "$DIR/agrilens.onnx" 2>/dev/null | cut -c1-16)..., host $(hostname)"
note "network: $(ip -brief addr 2>/dev/null | grep -v '^lo' | tr '\n' ';')"
note "camera: $(ls /dev/video* 2>/dev/null | tr '\n' ' ') $(lsusb 2>/dev/null | grep -i -E 'logitech|046d' | head -1)"
CRASH_TIMES=()
while true; do
  reset_gates
  note "starting kiosk"
  (cd "$DIR" && exec "$PY" -u main.py) >> "$LOG" 2>&1 &
  PID=$!
  health "$PID" &
  HPID=$!
  [ $AUTOSTART -eq 1 ] && { own_autostart & }
  wait "$PID"; CODE=$?
  kill "$HPID" 2>/dev/null
  note "kiosk exited with code $CODE"
  if [ -e "$STOP" ]; then rm -f "$STOP"; note "stop file present; launcher stops"; exit 0; fi
  if [ "$CODE" -ne 0 ]; then
    NOW=$(date +%s); RECENT=()
    for t in "${CRASH_TIMES[@]:-}"; do [ -n "$t" ] && [ $((NOW - t)) -lt 600 ] && RECENT+=("$t"); done
    RECENT+=("$NOW"); CRASH_TIMES=("${RECENT[@]}")
    if [ "${#CRASH_TIMES[@]}" -gt 5 ]; then note "more than 5 crashes in 10 minutes; launcher stops. Check this log, then restart the Pi."; exit 1; fi
    note "crash ${#CRASH_TIMES[@]} in the last 10 minutes; restarting in ${DELAY} s"
  else
    note "closed normally (no stop file); restarting in ${DELAY} s"
  fi
  sleep "$DELAY"
done
