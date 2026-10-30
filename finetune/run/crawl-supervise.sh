#!/bin/bash
S=$(cd "$(dirname "$0")" && pwd)
cd ~/Projects/uinav-wt-android-eval-exp1/android-eval/finetune || exit 1
for attempt in $(seq 1 15); do
  "$S/emu-headless.sh" || exit 2
  python3 -u crawl.py data/screens.jsonl --resume $CRAWL_ARGS && exit 0
  echo "[supervise] $(date +%T) crawl exited, restarting (attempt $attempt)"
done
exit 1
