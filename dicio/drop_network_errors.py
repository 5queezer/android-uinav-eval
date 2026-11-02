#!/usr/bin/env python3
"""Remove the records of episodes whose LLM request never reached the server (OkHttp could not connect),
so that dicio_eval.py runs them again. usage: dicio/drop_network_errors.py results-dicio/llm_*.jsonl"""
import json, sys

for path in sys.argv[1:]:
    rows = [json.loads(l) for l in open(path)]
    keep = [r for r in rows if not any("connectTcp" in x or "ConnectException" in x for x in r["log"])]
    with open(path, "w") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in keep)
    print(f"{path}: dropped {len(rows) - len(keep)} of {len(rows)}")
