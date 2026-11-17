#!/bin/bash
# AGRILENS - Raspberry Pi 5 performance check of 5.0.0 and (for comparison) the existing installation, with the kiosk stopped.
# Read-only for both installations. Results: ~/AGRILENS_exhibition_results/<date>/
#   bash pi_benchmark.sh               100 timed diagnoses per model + 10-minute soak of 5.0.0
#   SOAK_SECONDS=1800 bash pi_benchmark.sh
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
NEW="${AGRILENS_NEW_DIR:-$HOME/AGRILENS_5.0.0}"
OLD="${AGRILENS_OLD_DIR:-$HOME/AGRILENS_RaspberryPi}"
OUT="$HOME/AGRILENS_exhibition_results/$(date +%Y%m%d_%H%M%S)"
SOAK="${SOAK_SECONDS:-600}"
mkdir -p "$OUT"
BENCH="$HERE/benchmark_pi5.py"; [ -f "$BENCH" ] || { echo "benchmark_pi5.py missing next to this script"; exit 1; }
if pgrep -f "main.py" >/dev/null; then
  echo "The kiosk is running. Stop it for a clean measurement (y = stop it now)?"; read -r a
  [ "$a" = "y" ] && pkill -f "main.py" && sleep 2
fi
[ -f "$HERE/collect_pi_environment.sh" ] && bash "$HERE/collect_pi_environment.sh" > "$OUT/pi_environment.txt" 2>&1
for v in new old; do
  D=$NEW; [ $v = old ] && D=$OLD
  [ -f "$D/main.py" ] || continue
  S=0; [ $v = new ] && S=$SOAK
  echo "[benchmark] $v installation $D (soak ${S}s)"
  python3 "$BENCH" --app-path "$D/main.py" --model "$D/agrilens.onnx" --labels "$D/labels.txt" --samples-dir "$D/diagnosis_samples" \
    --runs 100 --soak-seconds "$S" --note "kiosk stopped; $v installation" --out "$OUT/benchmark_$v.json" 2>&1 | tee "$OUT/benchmark_$v.txt"
done
echo "[benchmark] results in $OUT  (valid_for_pi5_reporting must be true in the JSON files)"
