#!/bin/bash
# The drawer-app test on the CPU (fp32, no GPU): kev-4b, v1, v2 served one after another on port 8009.
S=$(cd "$(dirname "$0")" && pwd)
EV=~/Projects/uinav-wt-android-eval-exp1/android-eval
KEV=~/Projects/kev
log() { echo "[cpu] $(date +%T) $*"; }
trap 'fuser -k 8009/tcp 2>/dev/null' EXIT
for m in ft2 ft base; do
  case $m in ft2) R=$KEV/runs/android-v2;; ft) R=$KEV/runs/android-v1;; base) R=jaredpalmer/kev-4b;; esac
  fuser -k 8009/tcp 2>/dev/null; sleep 3
  (cd $KEV && KEV_CUDA_GRAPHS=0 CUDA_VISIBLE_DEVICES= exec uv run --extra serve python $S/kev_serve_nofla.py --run $R --port 8009 --device cpu) >> $S/kev-serve-cpu.log 2>&1 &
  for i in $(seq 1 120); do curl -s -m 2 localhost:8009/v1/models > /dev/null && break; sleep 3; done
  log "serving $m"
  for attempt in $(seq 1 10); do
    timeout 5 adb -s emulator-5560 shell echo ok > /dev/null 2>&1 || "$S/emu-headless.sh" || exit 2
    (cd $EV && OLLAMA_HOST=http://127.0.0.1:8009 python3 -u eval.py --models kev --tasks tasks-apps.json --runs 1 \
       --floor 0.25 --max-steps 15 --out results-apps-cpu-kev4b-$m) && break
    log "eval interrupted (attempt $attempt)"; "$S/emu-headless.sh" || exit 2
  done
  log "done $m"
done
