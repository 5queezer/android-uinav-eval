#!/bin/bash
# Append round 4 (v4, three seeds) to results-kev4b-comparison.md: the live dev suite decides the checkpoint (success,
# then reached-to-success conversion); the 30 test tasks are reported for every seed but not used for the choice.
cd "$(dirname "$0")/../.." || exit 1
SEEDS=$(ls -d results-dev-kev4b-v4-s* 2>/dev/null | sed 's/.*-s//' | sort -n)
[ -n "$SEEDS" ] || { echo "no round-4 results"; exit 1; }
dev_cols="" test_cols=""
for m in base ft ft3; do [ -f results-dev-kev4b-$m/kev.jsonl ] && dev_cols="$dev_cols ${m/base/kev-4b}=results-dev-kev4b-$m/kev.jsonl"; done
dev_cols="${dev_cols//ft3=/v3=}"; dev_cols="${dev_cols//ft=/v1=}"
for s in $SEEDS; do
  dev_cols="$dev_cols v4-s$s=results-dev-kev4b-v4-s$s/kev.jsonl"
  [ -f results-kev4b-v4-s$s-exp1/kev.jsonl ] && test_cols="$test_cols v4-s$s=results-kev4b-v4-s$s-exp1/kev.jsonl"
done
best=$(python3 - $SEEDS <<'PY'
import json, sys
sys.path.insert(0, "finetune")
from compare import latest, metrics
tasks = {t["id"] for t in json.load(open("tasks-dev.json"))}
score = {}
for s in sys.argv[1:]:
    m = metrics([r for (t, _), r in latest(f"results-dev-kev4b-v4-s{s}/kev.jsonl").items() if t in tasks])
    score[s] = (m["success"] / max(1, m["n"]), m["success"] / max(1, m["reached"]))
print(max(score, key=score.get))
PY
)
{
echo
echo "## Round 4 (v4): three seeds, selected on the live dev suite"
echo
echo "v4 = kev-4b retrained on the cleaned round-1 data in the experiment-loop format only, path labels on the on-policy"
echo "states plus one goal-swapped copy each, terminal records written twice, messy-history terminal records, at most 6"
echo "records per goal and action class (\`data/v4/train-all.jsonl\`, 10,398 records), seeds ${SEEDS//$'\n'/, }."
echo "Selection uses only \`tasks-dev.json\` (17 tasks on the 12 dev pages); the chosen seed is **v4-s$best**."
echo
echo "### Live dev suite (selection)"
echo
python3 finetune/compare.py --tasks tasks-dev.json --metrics $dev_cols | sed -n '/| name/,$p'
echo
echo "### 30 test tasks, experiment loop (reported, not used for selection)"
echo
python3 finetune/compare.py --tasks tasks.json --metrics v1=results-kev4b-ft-exp1/kev.jsonl v3=results-kev4b-ft3-exp1/kev.jsonl $test_cols d3:4b=results-exp1/d3_4b.jsonl | sed -n '/| name/,$p'
echo
python3 finetune/compare.py --tasks tasks.json v1=results-kev4b-ft-exp1/kev.jsonl v3=results-kev4b-ft3-exp1/kev.jsonl $test_cols | tail -2
} >> results-kev4b-comparison.md
tail -40 results-kev4b-comparison.md
