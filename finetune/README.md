# Fine-tuning Kev for Android navigation

Builds training data for a [Kev](https://github.com/jaredpalmer/kev) decision model from the emulator's own screens,
in exactly the requests `../eval.py` sends, so the fine-tune is scored by the same harness as every other model.

## Pipeline

| step | script | GPU | output |
|---|---|---|---|
| 1. crawl Settings and Clock from the eval's start snapshot | `crawl.py data/screens.jsonl` | no | raw layouts per screen and scroll position, with the path from the home screen |
| 2. targets, LLM goals, per-step records | `build_data.py data/screens.jsonl data/v1` | Ollama (gemma4:12b) | `train.jsonl`, `dev.jsonl` (held-out pages), `goals.json` |
| 3. fine-tune | `uv run python -m kev.train --data data/v1/train.jsonl --init_from jaredpalmer/kev-4b ...` (in `~/Projects/kev`) | ~12.5 GB | `runs/android-v1` |
| 4. calibrate | `kev.benchmark` on `dev.jsonl`, then `scripts/calibrate_checkpoint.py --allow-in-distribution` | ~9 GB | temperature in `head.pt` |
| 5. on-policy rollouts (DAgger) | `rollout.py data/v1 data/onpolicy.jsonl` against `kev.serve` | ~9 GB | every request the model made on training goals |
| 6. label them from the crawl graph | `label_onpolicy.py data/onpolicy.jsonl data/v2/onpolicy.jsonl` | no | the right action per visited state (path step, shortcut, scroll or back) |
| 7. round-2 set | `merge_v2.py data/v2/onpolicy.jsonl data/v1/train.jsonl data/v2/train.jsonl` | no | on-policy + replay |
| 8. round-3 extras | `home_apps.py data/screens.jsonl data/v3/home.jsonl` | no (LLM on CPU) | home-screen records: the right app icon for Gmail, Photos, YouTube, Messages, Chrome goals |

`compare.py` puts several results files side by side per task. `run/` holds the runners used so far (they expect to sit
next to each other): `kev-pipeline.sh` (round 1 end to end), `r2-window1.sh` / `r2-window2.sh` (round 2: rollouts, then
train + calibrate + eval + Phone test + demo videos), `r3-window.sh` (round 3, prepared, not run), the emulator
starters (`emu-headless.sh` = llvmpipe without a window, `emu-gpu.sh` = NVIDIA in a window) and `report-r2.sh`.
Results: `../results-kev4b-comparison.md`.

## Held out from training

- Targets whose name or page matches `build_data.HOLDOUT` (the 30 eval tasks' features: Wi-Fi, Bluetooth, battery, dark
  theme, Android version, ...), and every target on the pages where the eval tasks end (`HOLDOUT_PAGES`).
- Goals the LLM phrased with a held-out feature.
- 10% of the remaining pages, as `dev.jsonl`.
- The Phone app (`../tasks-phone.json`) was never crawled: a test of a new app. `../tasks-apps.json` adds 10 tasks in
  Contacts, Files and Messages, opened from the app drawer (Messages appears in round 3's home-screen records, so
  `messages_no_account` is not fully new for that model).

Intermediate pages (the Settings list, Display & touch, System, ...) are shared with the eval tasks' paths, so the
30-task score measures generalisation within the Settings app, not to unseen apps; the Phone tasks do that.

## Gotchas

- `kev.benchmark --data` admits states only up to the 384-token training context: `kev_bench_long.py` (scratchpad)
  patches `kev.benchmark.CONTEXT` to the serving context. It also needs `KEV_DTYPE=bf16` on a 16 GB card.
- `kev.serve` needs `KEV_CUDA_GRAPHS=0` on 16 GB (the graph buffers do not fit beside the model).
- CPU serving needs flash-linear-attention hidden (`sys.modules["fla"] = None`); it is ~45 s per request.
- The emulator hangs on snapshot loads now and then (llvmpipe under CPU load, gfxstream with the GPU): every runner
  restarts it and resumes.
