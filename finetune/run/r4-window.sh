#!/bin/bash
# Round 4 (v4): three training seeds from kev-4b on data/v4/train-all.jsonl (experiment-loop format, path labels,
# terminal copies, messy histories, on-policy + 1 goal swap). Per seed: train, calibrate on the dev pages, live dev
# suite (selection), 30 test tasks (reported, not used for selection). Then the dev suite for kev-4b, v1 and v3.
S=$(cd "$(dirname "$0")" && pwd)
FT=~/Projects/uinav-wt-android-eval-exp1/android-eval/finetune
EV=~/Projects/uinav-wt-android-eval-exp1/android-eval
KEV=~/Projects/kev
log() { echo "[r4] $(date +%T) $*"; }
trap 'fuser -k 8008/tcp 2>/dev/null' EXIT
export KEV_DTYPE=bf16
serve() {  # $1 checkpoint
  fuser -k 8008/tcp 2>/dev/null; sleep 3
  (cd $KEV && KEV_CUDA_GRAPHS=0 exec uv run --extra serve python -m kev.serve --run "$1" --port 8008) >> $S/kev-serve-r4.log 2>&1 &
  for i in $(seq 1 120); do curl -s -m 2 localhost:8008/v1/models > /dev/null && return 0; sleep 3; done
  log "kev.serve $1 did not come up"; return 1
}
evals() {  # $1 = eval.py arguments, with emulator restarts (eval.py resumes)
  for attempt in $(seq 1 20); do
    timeout 5 adb -s emulator-5560 shell echo ok > /dev/null 2>&1 || "$S/emu-headless.sh" || return 2
    (cd $EV && eval "python3 -u eval.py $1") && return 0
    log "eval interrupted, restarting the emulator (attempt $attempt)"
    "$S/emu-headless.sh" || return 2
  done
  log "eval failed after 20 attempts: $1"; return 1
}
E="--runs 1 --floor 0.25 --max-steps 15"
export OLLAMA_HOST=http://127.0.0.1:8008
for seed in ${SEEDS:-0 1 2}; do
  RUN=$KEV/runs/android-v4-s$seed
  if [ ! -f $RUN/head.pt ]; then
    log "training seed $seed"
    (cd $KEV && uv run python -m kev.train --data $FT/data/v4/train-all.jsonl --base Qwen/Qwen3.5-4B-Base \
       --base_revision 1001bb4d826a52d1f399e183466143f4da7b741b --init_from jaredpalmer/kev-4b --epochs 1 --lr 2e-5 \
       --batch 1 --accum 8 --dtype bf16 --weights_dtype bf16 --checkpointing 1 --device cuda --max_state 1536 \
       --seed $seed --out $RUN) || { log "training seed $seed failed"; exit 1; }
  fi
  if [ ! -f $RUN/.calibrated ]; then
    log "benchmark + calibration seed $seed"
    (cd $KEV && uv run python $S/kev_bench_long.py --run $RUN --data $FT/data/v1/dev.jsonl --out runs/android-dev-v4-s$seed) || exit 1
    (cd $KEV && uv run python scripts/calibrate_checkpoint.py --run $RUN --rows runs/android-dev-v4-s$seed/rows.json \
       --allow-in-distribution) > $S/kev-calibrate-r4-s$seed.log 2>&1 && touch $RUN/.calibrated \
       || { log "calibration seed $seed failed"; exit 1; }
    grep -E "^fit rows|wrote" $S/kev-calibrate-r4-s$seed.log
  fi
  serve $RUN || exit 1
  evals "--models kev --tasks tasks-dev.json $E --out results-dev-kev4b-v4-s$seed" || exit 1
  evals "--models kev $E --out results-kev4b-v4-s$seed-exp1" || exit 1
  fuser -k 8008/tcp 2>/dev/null
  log "seed $seed done"
done
for m in base:jaredpalmer/kev-4b ft:$KEV/runs/android-v1 ft3:$KEV/runs/android-v3; do  # the dev suite for the earlier models
  serve "${m#*:}" || exit 1
  evals "--models kev --tasks tasks-dev.json $E --out results-dev-kev4b-${m%%:*}" || exit 1
done
fuser -k 8008/tcp 2>/dev/null
for p in $(pgrep -f "qemu-system-x86_64.*-port 5560"); do kill "$p"; done
log "done"
