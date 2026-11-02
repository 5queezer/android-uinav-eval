#!/bin/bash
# dicio_eval.py with emulator restarts (it resumes from the JSONL): dicio/run.sh <dicio_eval.py arguments>
S=$(cd "$(dirname "$0")" && pwd)
EMU=$S/../finetune/run/emu-headless.sh
for attempt in $(seq 1 10); do
  timeout 5 adb -s emulator-5560 shell echo ok > /dev/null 2>&1 || "$EMU" || exit 2
  (cd "$S/.." && python3 -u dicio_eval.py "$@") && exit 0
  echo "[dicio] eval interrupted, restarting the emulator (attempt $attempt)"
  "$EMU" || exit 2
done
exit 1
