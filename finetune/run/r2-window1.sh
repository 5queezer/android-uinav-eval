#!/bin/bash
# GPU window 1 of round 2: serve the fine-tune, roll it out on 200 training goals, free the GPU.
S=$(cd "$(dirname "$0")" && pwd)
FT=~/Projects/uinav-wt-android-eval-exp1/android-eval/finetune
trap 'fuser -k 8008/tcp 2>/dev/null' EXIT
(cd ~/Projects/kev && KEV_CUDA_GRAPHS=0 exec uv run --extra serve python -m kev.serve --run runs/android-v1 --port 8008) > $S/kev-serve-r2.log 2>&1 &
for i in $(seq 1 120); do curl -s -m 2 localhost:8008/v1/models > /dev/null && break; sleep 3; done
curl -s -m 2 localhost:8008/v1/models > /dev/null || { echo "[r2] kev.serve did not come up"; exit 1; }
echo "[r2] $(date +%T) serving"
ok=
for attempt in $(seq 1 10); do
  timeout 5 adb -s emulator-5560 shell echo ok > /dev/null 2>&1 || "$S/emu-headless.sh" || exit 2
  (cd $FT && OLLAMA_HOST=http://127.0.0.1:8008 python3 -u rollout.py data/v1 data/onpolicy.jsonl --goals 200 --max-steps 12 --restart $S/emu-headless.sh) && { ok=1; break; }
  echo "[r2] $(date +%T) rollout interrupted, restarting the emulator (attempt $attempt)"
  "$S/emu-headless.sh" || exit 2
done
[ -n "$ok" ] || { echo "[r2] $(date +%T) rollout failed after 10 attempts"; exit 1; }
echo "[r2] $(date +%T) done: $(wc -l < $FT/data/onpolicy.jsonl) states"
