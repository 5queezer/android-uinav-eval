#!/usr/bin/env python3
"""Round-2 training set: the labelled on-policy records plus a replay sample of round 1, shuffled.

usage: merge_v2.py data/v2/onpolicy.jsonl data/v1/train.jsonl data/v2/train.jsonl [--replay 3000]
"""
import argparse, random

p = argparse.ArgumentParser()
p.add_argument("onpolicy")
p.add_argument("replay_from")
p.add_argument("out")
p.add_argument("--replay", type=int, default=3000)
a = p.parse_args()
rng = random.Random(2)
on = open(a.onpolicy).read().splitlines()
old = open(a.replay_from).read().splitlines()
recs = on + rng.sample(old, min(a.replay, len(old)))
rng.shuffle(recs)
with open(a.out, "w") as f:
    f.write("\n".join(recs) + "\n")
print(f"{len(on)} on-policy + {min(a.replay, len(old))} replay = {len(recs)} records -> {a.out}")
