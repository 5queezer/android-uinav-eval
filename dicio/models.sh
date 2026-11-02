#!/bin/bash
# The LLM fallback through the remote engine for each model in MODELS (GGUF files in ~/Projects/models/gguf-dicio,
# served one at a time by llama-server on port 8011; NGL=0 runs on the CPU, NGL=99 on the GPU), all tasks;
# results go to ${OUT:-results-dicio}. ARGS are passed to dicio_eval.py.
cd "$(dirname "$0")/.." || exit 1
G=~/Projects/models/gguf-dicio
L=~/Projects/models/llama-b12024/llama-b12024  # a llama.cpp release that knows gemma4
declare -A FILE=([gemma4-e4b]=gemma-4-E4B-it-Q4_K_M.gguf [gemma4-e2b]=gemma-4-E2B-it-Q4_K_M.gguf
                 [qwen3.5-4b]=Qwen3.5-4B-Q4_K_M.gguf [phi4-mini]=microsoft_Phi-4-mini-instruct-Q4_K_M.gguf
                 [functiongemma]=functiongemma-270m-it-Q8_0.gguf)
trap 'fuser -k 8011/tcp 2>/dev/null' EXIT
for m in ${MODELS:-gemma4-e4b qwen3.5-4b gemma4-e2b phi4-mini functiongemma}; do
  echo "[models] $(date +%T) $m"
  fuser -k 8011/tcp 2>/dev/null; sleep 2
  LD_LIBRARY_PATH=$L CUDA_VISIBLE_DEVICES=$([ "${NGL:-0}" = 0 ] && echo "" || echo 0) $L/llama-server -m "$G/${FILE[$m]}" --port 8011 \
    --host 127.0.0.1 -c 16384 -ngl "${NGL:-0}" -t "${THREADS:-12}" --jinja --alias "$m" ${LLAMA_ARGS} >> dicio/llama.log 2>&1 &
  for i in $(seq 1 120); do curl -s -m 2 localhost:8011/health | grep -q ok && break; sleep 2; done
  dicio/run.sh --variant "llm:$m" --out "${OUT:-results-dicio}" ${ARGS} || exit 1
done
echo "[models] $(date +%T) done"
