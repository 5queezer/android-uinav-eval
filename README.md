# android-eval

Measures how well local Ollama decision models (System One API, `POST /v1/systemone`) navigate
Android over many steps, using the same questions, criteria order, candidate ranking, unsafe
blocklist and gate as uinav (`src/decide.rs`, `src/a11y.rs`), so findings carry back to uinav.

uinav itself (a desktop UI agent on AT-SPI) is not public; this harness is self-contained and
only mirrors its decision logic. The emulator was an Android 15 `google_apis` x86_64 AVD (Pixel 7
profile, 4 GB RAM) started with `-gpu host -port 5560 -snapshot uinav-home-apps -no-snapshot-save`.

## Results (30 tasks × 5 runs, Android 15 emulator)

| model | success at floor 0.25 | at floor 0.6 | median model call |
|---|---|---|---|
| d3:4b | 63% | 45% | 436 ms |
| d3:9b | 62% | 41% | 790 ms |
| clef-flash (num_ctx 8192) | 52% | 25% | 448 ms |
| tev1:4b (text only) | 23% | 20% | 164 ms |
| kev (text only) | 23% | 7% | 274 ms |

With the three experiment changes below (one run per task): d3:4b 19 → 20/30, clef-flash 15 → 18/30,
tev1:4b 7 → 10/30; no model claimed done on an unfinished task. Full tables: `results/report.md` and
`results-exp1/report.md`; per-step records in the JSONL files.

## Fine-tuning kev-4b, and apps it never saw

The text-only [Kev](https://github.com/jaredpalmer/kev)-4B decision model was fine-tuned on data crawled from the
emulator itself: 233 Settings and Clock screens, goals written by a local LLM, every record in exactly the request
`eval.py` sends. The eval tasks' targets and end pages were held out. Pipeline, held-out rules and gotchas:
[`finetune/README.md`](finetune/README.md). All numbers, per task: [`results-kev4b-comparison.md`](results-kev4b-comparison.md).

| tasks solved | kev-4b | round 1 | round 2 | round 3 | d3:4b (screenshots) |
|---|---|---|---|---|---|
| 30 Settings tasks, experiment loop | 9 | **17** | 15 | 16 | 20 |
| 30 Settings tasks, original loop | 3 | 16 | 13 | **17** | 19 |
| Phone app, 10 tasks (never crawled) | 2 | 3 | 2 | 2 | 5 |
| Contacts / Files / Messages, 10 tasks (never crawled) | 0 | 1 | 1 | 0 | 3 |

- Round 1 (crawled data) roughly doubles kev-4b inside the crawled app, about 10 points short of d3:4b with screenshots.
- Round 2 added on-policy corrections (the model's own rollouts, labelled from the crawl graph); round 3 retrained
  from kev-4b on cleaned data (a review found held-out pages leaking in as "wrong turn, go back" records) plus
  home-screen app choices. In the experiment loop neither beat round 1 (15 and 16 vs 17); in the original loop round
  3 solved one task more (17 vs 16), within one training seed's noise. kev's server is deterministic, so each cell is
  one run per task.
- Nothing transfers to unseen apps: the fine-tunes open Settings from the home screen for most Phone goals.

New task sets: [`tasks-phone.json`](tasks-phone.json) and [`tasks-apps.json`](tasks-apps.json) (`--tasks`).
The runners in `finetune/run/` are the ones used here and still carry this machine's paths.

## Demo videos

`demo.py OUT_DIR [--model d3:4b] [--task-ids a,b]` records one video per task: the emulator screen
(`adb shell screenrecord`) next to a panel with each step's action, confidence, top-3 options and
done probability, and the outcome. Needs ffmpeg with libx264; the panel fonts are Fedora paths
(Noto Sans, JetBrains Mono), change `F` and `MONO` elsewhere.

Requirements: Python 3 with Pillow, `adb`, the `android` CLI (`android layout`), Ollama, and the
emulator `emulator-5560` with the snapshot `uinav-home-apps` (clean home screen plus Settings and
Clock icons, Clock's first-run popups dismissed; `--snapshot uinav-home` starts from the bare home
screen, where Settings is only in the app drawer).

## Run

```sh
python3 eval.py --models tev1:4b,kev,clef-flash,d3:4b,d3:9b --runs 5 --floor 0.25
python3 eval.py --models clef-flash --task-ids dark_theme,wifi_name --max-steps 10 --out /tmp/smoke
python3 report.py results --floors 0.25,0.4,0.5,0.6 > results/report.md
```

Options: `--tasks tasks.json`, `--task-ids a,b`, `--max-steps 15`, `--floor 0.6` (action
confidence below it ends the episode as `uncertain`), `--img-px 1200` (long side of the screenshot
sent to vision models), `--settle 0.8` (seconds after each action), `--out results`,
`--snapshot uinav-home-apps`.

Experiment changes, all on by default; `--no-<flag>` restores the earlier behaviour (all three
off = the original harness). Each record has them under `variant`, e.g. `{"stuck_option": true,
"toggle_state": true, "scroll_end": true}`; use a separate `--out` per variant, since resuming
skips episodes already in the JSONL whatever their variant.

- `--stuck-option`: no `stuck` choice (nor in the action question). Instead, an episode ends as
  `stuck` with `stuck_reason: "repeat"` when the same screen (window title plus candidate names and
  states) is observed a third time; it ends before asking the model.
- `--toggle-state`: checkable candidates, and rows holding a checkable (also a clickable Switch
  inside the row), are named `... [on]` / `... [off]` instead of carrying a `checked` state. After
  a tap on one, its history entry becomes `tapped <role> '<name>' (off→on)` (or `was off; not on
  the next screen`), and the step gets `effect`. If the model then picks a checkable this episode
  has flipped (seen to change state after a tap), nothing is tapped: the step is scored as if
  done ≥ 0.8, with `anti_undo: true` (after the confidence floor, so a low-confidence pick still
  ends as `uncertain`).
- `--scroll-end`: a `scroll_down` that stays in the same window marks it scrolled; if the screen is
  unchanged it is also exhausted, until a `scroll_up` in that window changes the screen. Exhausted
  windows get no `scroll_down`; scrolled ones get `scroll_up` (a swipe down). With more than three fixed options
  the lowest-ranked candidates are dropped to stay within 26.

`python3 -I -m unittest` runs offline tests on recorded layouts in `testdata/` with scripted
model answers (no device, no Ollama).

`report.py` scores at the floor the run used and re-scores each episode at the `--floors` at or
above it: walking the recorded steps, a step with done ≥ 0.8 keeps the recorded outcome, an
earlier step with confidence below the floor turns it into `uncertain`.

Output is one JSON line per episode in `results/<model>.jsonl`, with per-step records (window,
foreground package, candidates, chosen action, confidence, top-3, done probability, answer,
gate, timings in ms, and whether the verifier passed). Screenshots of non-successful episodes
are kept as JPEGs in `results/img/<model>/<task>-<run>/`. Runs are resumable: (model, task, run)
triples already in the JSONL are skipped, except `error` episodes, which are retried (the report
keeps the last record per episode). Every adb/android call and HTTP request has a timeout; a failed
model request is retried once, then the episode is an `error` and the run goes on. A snapshot
load that fails twice (5 s apart) is recorded as `error` and the run exits non-zero: restart the
emulator and rerun the same command.

Models run one after the other: each is warmed up with a tiny request (`keep_alive` 30m), and the
previous one is unloaded (`/api/generate` with `keep_alive: 0`). `tev1*` and `kev*` are sent no
screenshot (they return HTTP 400 for images) and get a done question without "the screenshot".

## Reset

Every episode starts with `adb -s emulator-5560 emu avd snapshot load uinav-home-apps`, then waits
for `sys.boot_completed` (adb reports the device offline for a moment after a load). Do the same
by hand to get back to the start state. Never save or overwrite a snapshot (`snapshot save` with
`-gpu host` has hung the emulator); it runs with `-no-snapshot-save`.

## Each step

`android layout --no-idle` (APPLICATION windows only) → up to 23 candidates (clickable, or
checkable outside a clickable row; on screen; Settings rows named from their child texts, e.g.
`Battery: Charged`; ranked like `a11y::select`) → screenshot (vision models) → one request with
`done` (noul) and `action` (choice: candidates, `scroll_down`, `scroll_up`, `back`, `stuck`, as
the flags above allow), plus `answer`
(choice: up to 25 visible text rows and `none`) for info tasks → gate → tap / swipe up / back key
→ settle. The task's verifier runs on every observed state, independent of the model.

## Outcomes

| outcome | meaning |
|---|---|
| `success` | done ≥ 0.8 and the verifier passes; for info tasks the chosen answer also contains the expected value |
| `false_done` | done ≥ 0.8 but the verifier fails |
| `wrong_answer` | info task: done and the expected value is on screen, but the chosen answer does not contain it |
| `uncertain` | action confidence below `--floor` |
| `stuck` | the model chose `stuck` (`stuck_reason: "model"`), or the same screen came up a third time (`"repeat"`) |
| `unsafe_blocked` | the chosen candidate matches the uinav blocklist (password, pin, delete, remove, format, ...) |
| `max_steps` | no decision to stop within `--max-steps` |
| `error` | an exception (adb, layout, HTTP); the record has the message |

`reached` / `first_reached_step` say whether and when the verifier first passed (step 1 is the
home screen), whatever the model decided.

## Tasks

`tasks.json`: 10 `info` tasks (`expected_cmd`, optional `extract` regex and `transform`: `pct`,
`date_long`, `gmt_offset`, `ms_minutes`; reached = expected value visible as a whole token),
15 `set` tasks (`check_cmd` output must match `expect`), 5 `open` tasks (`package` regex on the
foreground package and `layout_re` on `window: <title>` plus the visible text rows). `note`
fields record emulator quirks and replaced tasks.
