#!/bin/bash
# GPU window 2 of round 2: train android-v2 from android-v1 on labelled rollouts + replay, calibrate, eval, free the GPU.
S=$(cd "$(dirname "$0")" && pwd)
FT=~/Projects/uinav-wt-android-eval-exp1/android-eval/finetune
EV=~/Projects/uinav-wt-android-eval-exp1/android-eval
KEV=~/Projects/kev
RUN=$KEV/runs/android-v2
log() { echo "[r2] $(date +%T) $*"; }
trap 'fuser -k 8008/tcp 2>/dev/null' EXIT
export KEV_DTYPE=bf16
if [ ! -f $RUN/head.pt ]; then
  log "training"
  (cd $KEV && uv run python -m kev.train --data $FT/data/v2/train.jsonl --base Qwen/Qwen3.5-4B-Base \
     --base_revision 1001bb4d826a52d1f399e183466143f4da7b741b --init_from $KEV/runs/android-v1 --epochs 1 --lr 2e-5 \
     --batch 1 --accum 8 --dtype bf16 --weights_dtype bf16 --checkpointing 1 --device cuda --max_state 1536 --out $RUN) \
     || { log "training failed"; exit 1; }
fi
if [ ! -f $RUN/.calibrated ]; then
  log "benchmark + calibration"
  (cd $KEV && uv run python $S/kev_bench_long.py --run $RUN --data $FT/data/v1/dev.jsonl --out runs/android-dev-ft2) || exit 1
  (cd $KEV && uv run python scripts/calibrate_checkpoint.py --run $RUN --rows runs/android-dev-ft2/rows.json \
     --allow-in-distribution) > $S/kev-calibrate-r2.log 2>&1 && touch $RUN/.calibrated || { log "calibration failed"; exit 1; }
  grep -E "^fit rows|wrote" $S/kev-calibrate-r2.log
fi
serve() {  # $1 checkpoint
  fuser -k 8008/tcp 2>/dev/null; sleep 3
  (cd $KEV && KEV_CUDA_GRAPHS=0 exec uv run --extra serve python -m kev.serve --run "$1" --port 8008) >> $S/kev-serve-r2w2.log 2>&1 &
  for i in $(seq 1 120); do curl -s -m 2 localhost:8008/v1/models > /dev/null && return 0; sleep 3; done
  log "kev.serve $1 did not come up"; return 1
}
evals() {  # $1 = eval.py arguments, run with emulator restarts (eval.py resumes)
  for attempt in $(seq 1 20); do
    timeout 5 adb -s emulator-5560 shell echo ok > /dev/null 2>&1 || "$S/emu-gpu.sh" || return 2
    (cd $EV && eval "python3 -u eval.py $1") && return 0
    log "eval interrupted, restarting the emulator (attempt $attempt)"
    "$S/emu-gpu.sh" || return 2
  done
  return 1
}
P="--tasks tasks-phone.json --runs 1 --floor 0.25 --max-steps 15"
serve $RUN || exit 1
export OLLAMA_HOST=http://127.0.0.1:8008
evals "--models kev --runs 1 --floor 0.25 --max-steps 15 --out results-kev4b-ft2-exp1" || exit 1
evals "--models kev --runs 1 --floor 0.25 --max-steps 15 --out results-kev4b-ft2 --no-stuck-option --no-toggle-state --no-scroll-end" || exit 1
evals "--models kev $P --out results-phone-kev4b-ft2" || exit 1
ok=
for attempt in $(seq 1 10); do  # demo videos of the round-2 model (demo.py skips finished tasks)
  timeout 5 adb -s emulator-5560 shell echo ok > /dev/null 2>&1 || "$S/emu-gpu.sh" || break
  python3 -u $S/demo.py $S/demo-kev-ft2 --model kev --floor 0.25 && { ok=1; break; }
  "$S/emu-gpu.sh" || break
done
[ -n "$ok" ] || { log "demo videos failed"; exit 1; }
serve $KEV/runs/android-v1 || exit 1
evals "--models kev $P --out results-phone-kev4b-ft" || exit 1
serve jaredpalmer/kev-4b || exit 1
evals "--models kev $P --out results-phone-kev4b-base" || exit 1
fuser -k 8008/tcp 2>/dev/null
unset OLLAMA_HOST
evals "--models d3:4b --tasks tasks-phone.json --runs 3 --floor 0.25 --max-steps 15 --out results-phone-d3" || exit 1
curl -s localhost:11434/api/generate -d '{"model":"d3:4b","keep_alive":0}' > /dev/null
log "done"
