#!/bin/bash
# Append round 2 (DAgger) and the Phone-app test to results-kev4b-comparison.md.
cd ~/Projects/uinav-wt-android-eval-exp1/android-eval || exit 1
KEV=~/Projects/kev/runs
{
echo
echo "## Round 2: on-policy corrections (android-v2)"
echo
echo "android-v2 = android-v1 + 1 epoch on 1,333 states the v1 model visited on 200 training goals (labelled by the crawl-graph oracle: path step, shortcut, scroll or back) + 3,000 replayed v1 records. Temperature refitted on the held-out pages. kev.serve is deterministic, so one run per task is the whole answer."
echo
python3 - <<'PY'
import json
print("| held-out pages | kev-4b | v1 | v2 |\n|---|---|---|---|")
r = {m: json.load(open(f"/home/christian/Projects/kev/runs/android-dev-{m}/report.json")) for m in ("base", "ft", "ft2")}
for k, name in (("custom_choice", "choice accuracy"), ("custom_noul", "done accuracy")):
    print(f"| {name} | " + " | ".join(f"{r[m]['tasks'][k]['acc']:.3f}" for m in ("base", "ft", "ft2")) + " |")
print("| ECE (as served) | " + " | ".join(f"{r[m]['clean']['ece']:.3f}" for m in ("base", "ft", "ft2")) + " |")
PY
echo
echo "### 30 Settings tasks, experiment loop (success per task)"
echo
python3 finetune/compare.py --tasks tasks.json kev-4b=results-kev4b-base-exp1/kev.jsonl v1=results-kev4b-ft-exp1/kev.jsonl v2=results-kev4b-ft2-exp1/kev.jsonl d3:4b=/home/christian/Projects/uinav-wt-android-eval-exp1/android-eval/results-exp1/d3_4b.jsonl
echo
echo "### 30 Settings tasks, original loop"
echo
python3 finetune/compare.py --tasks tasks.json kev-4b=results-kev4b-base/kev.jsonl v1=results-kev4b-ft/kev.jsonl v2=results-kev4b-ft2/kev.jsonl | tail -2
echo
echo "## A new app: Phone (never crawled, 10 tasks, experiment loop)"
echo
python3 finetune/compare.py --tasks tasks-phone.json kev-4b=results-phone-kev4b-base/kev.jsonl v1=results-phone-kev4b-ft/kev.jsonl v2=results-phone-kev4b-ft2/kev.jsonl d3:4b=results-phone-d3/d3_4b.jsonl
} >> results-kev4b-comparison.md
tail -60 results-kev4b-comparison.md
