# android-eval

Measures how well local Ollama decision models (System One API, `POST /v1/systemone`) navigate
Android over many steps, using the same questions, criteria order, candidate ranking, unsafe
blocklist and gate as uinav (`src/decide.rs`, `src/a11y.rs`), so findings carry back to uinav.

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

## Generative agents (`gen:` models)

`--models gen:gelab-zero-4b,gen:qwen3-vl-4b,gen:gui-owl-1.5-4b` runs ready-made GUI agents that take a
screenshot and reply with action text (`gen_agents.py`, one adapter per family). The episode loop is the
same as for decision models: the same snapshot reset, `--max-steps`, `verify()` on every observation, the
repeat-screen `stuck` rule (`--stuck-option`), the unsafe blocklist (on the element under a tap), record and
step fields, `results/<model>.jsonl` (e.g. `gen_qwen3-vl-4b.jsonl`), `--tasks` / `--runs` / `--out`. Each step
sends the model its own prompt (goal, its own short history, the screenshot at `--img-px`) and executes the
parsed action at the model's coordinates (its own grounding).

| `--models` | served by | prompt and action format (source) | coordinates |
|---|---|---|---|
| `gen:gelab-zero-4b` | llama-server, `$GELAB_BASE_URL` | `CLICK` / `SLIDE` / `COMPLETE` ... tab-separated, with its own `summary` as history ([gelab-zero](https://github.com/stepfun-ai/gelab-zero), `copilot_tools/parser_0920_summary.py`) | 0-1000 |
| `gen:qwen3-vl-4b` | Ollama `qwen3-vl:4b-instruct` | `mobile_use` tool call ([Qwen3-VL cookbook](https://github.com/QwenLM/Qwen3-VL/blob/main/cookbooks/mobile_agent.ipynb)) | 0-999 |
| `gen:gui-owl-1.5-4b` | llama-server or vLLM, `$GUI_OWL_BASE_URL` | `mobile_use` tool call ([Mobile-Agent-v3.5](https://github.com/X-PLUG/MobileAgent/tree/main/Mobile-Agent-v3.5) `mobile_use/utils.py`, text-only history) | 0-1000 |

Serving (one llama-server model at a time on port 8010, the default of both base URLs):

```sh
ollama pull qwen3-vl:4b-instruct   # not qwen3-vl:4b, which is the thinking variant
G=~/Projects/models/gguf-gelab; llama-server -m $G/stepfun-ai_GELab-Zero-4B-preview-Q8_0.gguf \
  --mmproj $G/mmproj-stepfun-ai_GELab-Zero-4B-preview-f16.gguf --port 8010 -c 16384 -ngl 99 --alias gelab-zero-4b-preview
O=~/Projects/models/gguf-guiowl; llama-server -m $O/GUI-Owl-1.5-4B-Instruct.Q8_0.gguf \
  --mmproj $O/GUI-Owl-1.5-4B-Instruct.mmproj-f16.gguf --port 8010 -c 16384 -ngl 99 --alias GUI-Owl-1.5-4B-Instruct
python3 eval.py --models gen:gelab-zero-4b --out results-gen   # with the GELab server up; then GUI-Owl the same way
```

GELab's official Ollama route (`ollama create` from the Modelfile in its Hugging Face repo) does not import
on Ollama 0.40.11: the safetensors import goes through MLX, which rejects `Qwen3VLForConditionalGeneration`.
Environment: `GELAB_BASE_URL`, `GUI_OWL_BASE_URL` (default `http://localhost:8010/v1`), `GELAB_MODEL`,
`GUI_OWL_MODEL`, `QWEN3VL_MODEL` (served names), `GELAB_API_KEY`, `GUI_OWL_API_KEY`, `OLLAMA_HOST`.

Scoring: the model's finish (`COMPLETE`, `terminate` with success, GUI-Owl's `answer`) is scored like done
≥ 0.8: `success` if the verifier passes, else `false_done`; on info tasks the finish answer must contain the
expected value (else `wrong_answer`; Qwen3-VL gives its `answer` a step before `terminate`, the last one
counts). Giving up (`ABORT`, `terminate` with failure) is `stuck` with `stuck_reason: "model"`. A reply that
does not parse, opening an app by name (`AWAKE`, `open`) and asking the user (`INFO`, `interact`) are no-op
steps (`gate: "noop"`); they use up a step and leave the screen unchanged, so the repeat rule can end the
episode. Steps record `reply` (raw text), `parsed` (the normalised action), `action` (e.g. `tap(540,1817)`),
and as `chosen` the a11y element under a tap, for analysis; `conf` and `top3` are null, `done` is 1.0 on the
finish step and 0.0 otherwise.

Not comparable with the decision models in these ways: they see only the screenshot (no layout or candidate
list, and none of the experiment flags' hints); there is no confidence, so no floor applies (records say
`floor: 0.0` and the report's re-scoring at other floors gives the same outcome); they cannot launch an app
by name although their prompts offer it; the screenshot is downscaled to `--img-px` (normalised coordinates
make that safe; `--img-px 2400` sends the native size); they reply with long text (GELab thinks first), so
model latency is not comparable; and they run as Q8_0 GGUF on llama-server or Ollama's quantised tag, not the
bf16 weights of their papers.

## Dicio (voice assistant) benchmark

`dicio_eval.py` measures debug builds of [Dicio](https://github.com/DicioTeam/dicio-android) on the same
emulator: it sends an utterance through a debug-only broadcast (`org.stypox.dicio.EVAL_INPUT`, a receiver in
Dicio's `src/debug`, any Unicode text), waits until Dicio's reply has not changed for ~2 s (or another app took
the foreground), and checks the reply and the device state. `tasks-dicio.json` (written by
`dicio/make_tasks.py`) holds 32 tasks in German and English each: `skill` (Dicio's own skills), `routing` (LLM
requests a skill could grab), `action` (only the LLM tools can do them), `knowledge`, `in_app` (need a GUI
agent, for later), `safety` (no side effect allowed) and `multi` (two utterances in one conversation).

```sh
dicio/setup.sh                                   # the `dicio` snapshot: the APKs of dicio/variants.json, three contacts
dicio/run.sh --variant upstream                  # dicio_eval.py with emulator restarts; also branch-text
dicio/models.sh                                  # the LLM fallback per model (llama-server on port 8011, NGL=0 = CPU)
python3 dicio/report.py --tasks                  # success per category, false actions, latency, task matrix
```

Each episode loads the `dicio` snapshot, writes the variant's settings (`dicio/variants.json`: field numbers
of `user_settings.proto`, plus the task's language) into Dicio's DataStore with `run-as`, starts Dicio and
records a fingerprint before and after: the next alarm, running Clock timers, calendar events, contacts, the
numbers in the call log (the emulator hangs up at once) and the foreground app. A change the task does not
`allow` makes the episode a `false_action`. Checks: `reply` (regex on Dicio's answer), `state` (a fingerprint
field), `screen` (the text of another app in the foreground; Dicio's own screen never counts) and `any`.
Variants: `upstream` (DicioTeam main + the receiver), `branch-text` (the LLM branch, text fallback) and
`llm:<model>` (the branch's remote LLM engine against `http://10.0.2.2:8011/v1`, the host's llama-server).
Records hold the turns with reply and seconds, the effects, the final fingerprint and the log lines of the LLM
engine and its tools.

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

`tasks-phone.json`: 10 tasks in the Phone app (9 `open`, 1 `info`), which the fine-tune never saw.
`tasks-apps.json`: 10 tasks in Contacts, Files and Messages, opened from the app drawer (no results yet).

## Results

All at floor 0.25 and `--max-steps 15` on the 30 tasks in `tasks.json`, unless a row says otherwise.
Two loops: **original** (all three experiment flags off) and **exp1** (all on, the default). A
number from one loop is not comparable with a number from the other. The per-run reports
(`results*/report.md`, from `report.py`) are not in git; the tables below are copied from them.

### Main eval (original loop, 5 models x 5 runs = 750 episodes)

| model | input | success | reached | false_done |
|---|---|---|---|---|
| d3:4b | layout + screenshot | 63% (94/150) | 63% | 0/150 |
| d3:9b | layout + screenshot | 62% (93/150) | 62% | 0/150 |
| clef-flash-8k | layout + screenshot | 52% (78/150) | 59% | 0/150 |
| kev | layout | 23% (34/150) | 33% | 4/150 (3%, all `battery_saver`) |
| tev1:4b | layout | 23% (35/150) | 39% | 0/150 |

At floor 0.6 d3:4b keeps 45%. The most common failure was the model choosing `stuck` on the home
screen (60 episodes) or the Settings list (41, all tev1:4b).

### Exp1 loop (no `stuck` option, switch state and tap effect, scroll end)

| model | original loop | exp1 loop |
|---|---|---|
| d3:4b | 63% (5 runs) | 67% (20/30, 1 run) |
| clef-flash-8k | 52% (5 runs) | 60% (18/30, 1 run) |
| tev1:4b | 23% (5 runs) | 33% (10/30, 1 run) |
| kev-4b on `kev.serve` | 10% (5 runs) | 30% (5 runs) |

No false_done for the three Ollama models in the exp1 run (kev-4b: 5/150, all `battery_saver`). The
flags were only tested together, so the gain is not attributable to one of them, and the Ollama
rows compare 5 runs with 1.

### Open-Jev 2B / 9B

[Open-Jev](https://github.com/Zefan-Cai/Open-Jev) decision models, sent the layout only.

| model | loop | runs | floor | success | reached | false_done |
|---|---|---|---|---|---|---|
| Open-Jev-2B | original | 5 | 0.25 | 0% | 0% | 0 |
| Open-Jev-2B | exp1 | 1 | 0.25 | 0% | 0% | 0 |
| Open-Jev-9B | original | 5 | 0.25 | 0% | 3% | 0 |
| Open-Jev-9B | exp1 | 1 | 0.25 | 0% | 10% | 0 |
| Open-Jev-9B | exp1 | 1 | 0.0 | 20% (6/30) | 37% | 2/30 |

Open-Jev-2B ends every original-loop episode at step 1 on the home screen (130 `uncertain`, 20
`stuck`). Without a floor the 9B solves 6 tasks, but each of
those episodes has a step below 0.25.

### Kev-4B fine-tune

Training data crawled from the emulator's Settings and Clock screens (233 screens, 7,277 records),
with the 30 test tasks' targets and end pages held out; kev-4b fine-tuned for 1 epoch (v1 = round 1),
then 1 epoch more on on-policy corrections plus replayed v1 records (v2 = round 2); v3 (round 3) is
retrained from kev-4b on the cleaned holdout. Pipeline, holdout and gotchas:
[finetune/README.md](finetune/README.md); full tables and per-task results:
[results-kev4b-comparison.md](results-kev4b-comparison.md). All Kev models are served by
`kev.serve` (bf16), layout only.

| held-out pages (1,092 records) | kev-4b | v1 | v2 |
|---|---|---|---|
| choice accuracy | 0.560 | 0.807 | 0.821 |
| done accuracy | 0.883 | 0.965 | 0.967 |
| ECE | 0.112 | 0.026 | 0.020 |

| model | original loop | exp1 loop |
|---|---|---|
| kev-4b | 3/30 tasks, 10% (5 runs) | 9/30, 30% (5 runs) |
| v1 | 16/30, 53% (5 runs) | 17/30, 57% (5 runs) |
| v2 | 13/30, 43% (1 run) | 15/30, 50% (1 run) |
| v3 | 17/30, 57% (1 run) | 16/30, 53% (1 run) |
| d3:4b (screenshots, for reference) | 63% (5 runs, main eval) | 20/30, 67% (1 run) |

false_done: v1 5/150 in the original loop (all `battery_saver`), 0 in exp1; v2 1/30 in the original
loop, 0 in exp1; v3 2/30 in the original loop, 0 in exp1. Round 2 did not help: it lost `wifi_name`
and `ip_address` (on the right page it went back or picked the wrong answer). In the exp1 loop
neither round 2 nor round 3 beat round 1; in the original loop round 3 solves one task more than
round 1 (17/30 against 16/30), within one seed's noise. On held-out pages v3 leads on done accuracy
(0.975) but not on choice (0.814 against v2's 0.821, whose dev pages are contaminated, see below).

### A new app: Phone (exp1 loop)

| model | runs | tasks solved | success | false_done |
|---|---|---|---|---|
| kev-4b | 1 | 2/10 | 20% | 0 |
| v1 | 1 | 3/10 | 30% | 2/10 |
| v2 | 1 | 2/10 | 20% | 0 |
| v3 | 1 | 2/10 | 20% | 1/10 |
| d3:4b | 3 | 5/10 | 47% (14/30) | 3/30 (`phone_voicemail`, every run) |

The fine-tune did not transfer to an app it never saw: 3/10, 2/10 and 2/10 against 2/10 for the base model.
v2 and v3 tapped Settings on the home screen for 8 of the 10 goals; the training data only ever started in
Settings or Clock.

### What the numbers do and do not show

- Success is not the model's own claim: it needs done ≥ 0.8 *and* the task's verifier (`verify()`
  in `eval.py`: adb shell output such as `settings get`, `getprop` or `dumpsys`, or the foreground
  package and layout),
  which runs on every observed state, independent of the model (see Each step, Outcomes, Tasks).
- false_done is rare, not absent: kev 4 of 150 episodes (3%) in the main eval, the other four
  models 0; v1 5/150 and v3 2/30 (original loop); on Phone, d3:4b 3/30, v1 2/10 and v3 1/10.
- `kev.serve` is deterministic: every Kev task scores 0/5 or 5/5, so 5 runs are effectively 1 and
  one task is 3.3 points. The Ollama `kev` of the main eval (23%) is a different serving setup from
  kev-4b on `kev.serve` (10%, same loop); the fine-tune is compared only with the latter.
- The 30 test tasks share intermediate Settings pages (the Settings list, Display, System, ...) with
  the training data: the 30-task score measures generalisation within Settings. Phone measures a new app.
- Holdout leak: held-out pages were excluded as targets but not as wrong turns. v1 learned "not
  done, back" on the Battery (14 records), About emulated device (12), Stopwatch (11) and Location
  (7) pages, the end pages of `battery_level`, `android_version`/`build_number`, `stopwatch_start`
  and `location_off`, which no fine-tune solved. 42 records passing through the held-out
  Notifications page likely helped `notification_history`. Round 2's rollouts included dev-page
  goals, so v2's held-out scores are not clean either.
- One training seed per round; a difference of one or two tasks is weak evidence.
- Round 3 (no record on or through a held-out page, fewer `back` corrections, home-screen records
  for five other apps, trained from kev-4b) is on par with v1, and no kev variant transfers to the
  `tasks-apps.json` drawer apps (0-1/10, d3:4b 3/10); round 4 is planned (results-kev4b-comparison.md).
