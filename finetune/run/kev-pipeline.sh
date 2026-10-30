#!/bin/bash
# Overnight: crawl data -> kev-4b fine-tune -> dev benchmark -> eval (base vs fine-tuned, both loops, 5 runs).
# Every stage skips itself when its output exists, so the script can be rerun after a failure.
S=$(cd "$(dirname "$0")" && pwd)
FT=~/Projects/uinav-wt-android-eval-exp1/android-eval/finetune
EV=~/Projects/uinav-wt-android-eval-exp1/android-eval
KEV=~/Projects/kev
RUN=$KEV/runs/android-v1
BASE_REV=1001bb4d826a52d1f399e183466143f4da7b741b
log() { echo "[pipeline] $(date +%T) $*"; }
trap 'fuser -k 8008/tcp 2>/dev/null' EXIT  # never leave a kev.serve holding the GPU

# 1. data (gemma writes 3 goals per target; cached, so a rerun only fills gaps)
if [ ! -s $FT/data/v1/train.jsonl ] || [ $FT/data/screens.jsonl -nt $FT/data/v1/train.jsonl ]; then
  log "building data"
  (cd $FT && python3 -u build_data.py data/screens.jsonl data/v1 --goals-per-target 3) || { log "data failed"; exit 1; }
fi
curl -s localhost:11434/api/generate -d '{"model":"gemma4:12b-it-q8_0","keep_alive":0}' > /dev/null

# 2. fine-tune from the released kev-4b
if [ ! -f $RUN/head.pt ]; then
  log "training"
  (cd $KEV && uv run python -m kev.train --data $FT/data/v1/train.jsonl --base Qwen/Qwen3.5-4B-Base \
     --base_revision $BASE_REV --init_from jaredpalmer/kev-4b --epochs 1 --lr 2e-5 --batch 1 --accum 8 \
     --dtype bf16 --weights_dtype bf16 --checkpointing 1 --device cuda --max_state 1536 --out $RUN) \
     || { log "training failed"; exit 1; }
fi
[ -f $RUN/head.pt ] || { log "no checkpoint at $RUN"; exit 1; }

# 3. held-out pages, scored offline (bf16 like kev.serve; fp32 does not fit next to the desktop on 16 GB)
export KEV_DTYPE=bf16
for m in base ft; do
  [ $m = base ] && R=jaredpalmer/kev-4b || R=$RUN
  if [ ! -d $KEV/runs/android-dev-$m ]; then
    log "benchmark $m"
    (cd $KEV && uv run python $S/kev_bench_long.py --run $R --data $FT/data/v1/dev.jsonl --out runs/android-dev-$m) \
      || log "benchmark $m failed (continuing)"
  fi
done

# 3b. the fine-tune keeps kev-4b's temperature; fit one on the held-out pages so the confidence floor means something
#     (in distribution: same app, other pages; recorded in head.pt by the script)
if [ ! -f $RUN/.calibrated ]; then
  log "calibrating"
  (cd $KEV && uv run python scripts/calibrate_checkpoint.py --run $RUN --rows runs/android-dev-ft/rows.json \
     --allow-in-distribution) > $S/kev-calibrate.log 2>&1 && touch $RUN/.calibrated || { log "calibration failed"; exit 1; }
  tail -15 $S/kev-calibrate.log
fi

# 4. live eval: each model on its own kev.serve, both loops, 5 runs each
serve() {
  (cd $KEV && KEV_CUDA_GRAPHS=0 exec uv run --extra serve python -m kev.serve --run "$1" --port 8008) > $S/kev-serve-$2.log 2>&1 &
  SERVER=$!
  for i in $(seq 1 120); do curl -s -m 2 localhost:8008/v1/models > /dev/null && return 0; sleep 3; done
  log "kev.serve $2 did not come up"; return 1
}
complete() { [ -f "$1/kev.jsonl" ] && [ "$(python3 -c "
import json,sys
rs={}
for l in open('$1/kev.jsonl'):
    r=json.loads(l); rs[(r['task'],r['run'])]=r['outcome']
print(sum(v!='error' for v in rs.values()))")" -ge 150 ]; }
for m in base ft; do
  [ $m = base ] && R=jaredpalmer/kev-4b || R=$RUN
  if complete $EV/results-kev4b-$m && complete $EV/results-kev4b-$m-exp1; then continue; fi
  serve $R $m || exit 1
  export OLLAMA_HOST=http://127.0.0.1:8008
  ok=
  for attempt in $(seq 1 15); do
    "$S/emu-headless.sh" || exit 2
    (cd $EV && python3 -u eval.py --models kev --runs 5 --floor 0.25 --max-steps 15 --out results-kev4b-$m-exp1 \
      && python3 -u eval.py --models kev --runs 5 --floor 0.25 --max-steps 15 --out results-kev4b-$m \
           --no-stuck-option --no-toggle-state --no-scroll-end) && { ok=1; break; }
    log "eval $m interrupted, restarting the emulator (attempt $attempt)"
  done
  [ -n "$ok" ] || { log "eval $m failed after 15 attempts"; exit 1; }
  kill $SERVER; wait $SERVER 2>/dev/null; fuser -k 8008/tcp 2>/dev/null; sleep 5
done

# 5. reports
cd $EV
for d in results-kev4b-base results-kev4b-ft results-kev4b-base-exp1 results-kev4b-ft-exp1; do
  python3 report.py $d --floors 0.25,0.4,0.6 > $d/report.md
done
log "done"
