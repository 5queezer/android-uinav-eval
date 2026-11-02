#!/bin/bash
# Ready-made generative GUI agents (gen: models) on the 30 Settings tasks, Phone and the drawer apps, one model at a
# time: GELab-Zero-4B and GUI-Owl-1.5-4B on llama-server (port 8010), Qwen3-VL-4B-Instruct on Ollama.
S=$(cd "$(dirname "$0")" && pwd)
EV=~/Projects/uinav-wt-android-eval-exp1/android-eval
M=~/Projects/models
log() { echo "[gen] $(date +%T) $*"; }
trap 'fuser -k 8010/tcp 2>/dev/null' EXIT
llama() {  # $1 model gguf, $2 mmproj gguf, $3 alias
  fuser -k 8010/tcp 2>/dev/null; sleep 3
  llama-server -m "$1" --mmproj "$2" --port 8010 --host 127.0.0.1 -c 16384 -ngl 99 --alias "$3" >> $S/llama-gen.log 2>&1 &
  for i in $(seq 1 90); do curl -s -m 2 localhost:8010/health | grep -q ok && return 0; sleep 2; done
  log "llama-server $3 did not come up"; return 1
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
suite() {  # $1 gen model name, $2 short name
  E="--models gen:$1 --runs ${RUNS:-1} --max-steps 15"
  evals "$E --out results-gen-$2" || return 1
  evals "$E --tasks tasks-phone.json --out results-phone-gen-$2" || return 1
  evals "$E --tasks tasks-apps.json --out results-apps-gen-$2" || return 1
  log "$2 done"
}
for m in ${MODELS-gelab guiowl qwen3vl}; do
  case $m in
    gelab) llama $M/gguf-gelab/stepfun-ai_GELab-Zero-4B-preview-Q8_0.gguf $M/gguf-gelab/mmproj-stepfun-ai_GELab-Zero-4B-preview-f16.gguf gelab-zero-4b-preview && suite gelab-zero-4b gelab || exit 1;;
    guiowl) llama $M/gguf-guiowl/GUI-Owl-1.5-4B-Instruct.Q8_0.gguf $M/gguf-guiowl/GUI-Owl-1.5-4B-Instruct.mmproj-f16.gguf GUI-Owl-1.5-4B-Instruct && suite gui-owl-1.5-4b guiowl || exit 1;;
    qwen3vl) fuser -k 8010/tcp 2>/dev/null; suite qwen3-vl-4b qwen3vl || exit 1
             curl -s localhost:11434/api/generate -d '{"model":"qwen3-vl:4b-instruct","keep_alive":0}' > /dev/null;;
  esac
done
fuser -k 8010/tcp 2>/dev/null
for p in $(pgrep -f "qemu-system-x86_64.*-port 5560"); do kill "$p"; done
log "done"
