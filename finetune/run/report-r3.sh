#!/bin/bash
# Append round 3 and the drawer-app test to results-kev4b-comparison.md (after r3-window.sh).
set -eo pipefail  # a failed report step (python, compare.py) fails the script, not just the final tail
cd ~/Projects/uinav-wt-android-eval-exp1/android-eval || exit 1
{
echo
echo "## Round 3 (android-v3: balanced backs, more replay, home-screen app choice)"
echo
python3 - <<'PY'
import json
r = {m: json.load(open(f"/home/christian/Projects/kev/runs/android-dev-{m}/report.json")) for m in ("ft", "ft2", "ft3")}
print("| held-out pages | v1 | v2 | v3 |\n|---|---|---|---|")
for k, name in (("custom_choice", "choice accuracy"), ("custom_noul", "done accuracy")):
    print(f"| {name} | " + " | ".join(f"{r[m]['tasks'][k]['acc']:.3f}" for m in ("ft", "ft2", "ft3")) + " |")
PY
echo
echo "### 30 Settings tasks, experiment loop"
echo
python3 finetune/compare.py --tasks tasks.json v1=results-kev4b-ft-exp1/kev.jsonl v2=results-kev4b-ft2-exp1/kev.jsonl v3=results-kev4b-ft3-exp1/kev.jsonl | tail -2
echo
echo "### 30 Settings tasks, original loop"
echo
python3 finetune/compare.py --tasks tasks.json v1=results-kev4b-ft/kev.jsonl v2=results-kev4b-ft2/kev.jsonl v3=results-kev4b-ft3/kev.jsonl | tail -2
echo
echo "### Phone app"
echo
python3 finetune/compare.py --tasks tasks-phone.json kev-4b=results-phone-kev4b-base/kev.jsonl v1=results-phone-kev4b-ft/kev.jsonl v2=results-phone-kev4b-ft2/kev.jsonl v3=results-phone-kev4b-ft3/kev.jsonl d3:4b=results-phone-d3/d3_4b.jsonl
echo
echo "### Drawer apps: Contacts, Files, Messages"
echo
python3 finetune/compare.py --tasks tasks-apps.json kev-4b=results-apps-kev4b-base/kev.jsonl v1=results-apps-kev4b-ft/kev.jsonl v2=results-apps-kev4b-ft2/kev.jsonl v3=results-apps-kev4b-ft3/kev.jsonl d3:4b=results-apps-d3/d3_4b.jsonl
} >> results-kev4b-comparison.md
tail -50 results-kev4b-comparison.md
