# Kev-4B fine-tune for Android navigation (kev-4b vs android-v1)

Fine-tune: ~/Projects/kev/runs/android-v1, init_from jaredpalmer/kev-4b, 1 epoch, lr 2e-5, 7,277 records from 233 crawled screens (finetune/), temperature 1.66 fitted on held-out pages. Test tasks' targets and end pages held out of training. Both models served by kev.serve (bf16, no CUDA graphs), 30 tasks x 5 runs, floor 0.25.

## Held-out pages (kev.benchmark, 1,092 records)

| | kev-4b | fine-tuned |
|---|---|---|
| choice accuracy | 0.560 | 0.807 |
| done accuracy | 0.883 | 0.965 |
| ECE | 0.112 | 0.026 |

## Live eval, loop: original

## Per model (at the run floor)

| model | n | success | reached | false_done | mean steps (success) | median model ms | success | false_done | wrong_answer | uncertain | stuck | unsafe_blocked | max_steps | error |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| kev-4b-base | 150 | 10% | 17% | 0% | 4.0 | 186 | 15 | 0 | 0 | 60 | 75 | 0 | 0 | 0 |
| kev-4b-ft | 150 | 53% | 63% | 3% | 5.7 | 170 | 80 | 5 | 0 | 40 | 0 | 0 | 25 | 0 |

## Success at other floors (re-scored from the recorded steps; - = below the run floor)

| model | floor 0.25 | floor 0.4 | floor 0.6 |
|---|---|---|---|
| kev-4b-base | 10% | 7% | 3% |
| kev-4b-ft | 53% | 43% | 40% |

## Median time per step (ms; settle after each action comes on top)

| model | steps | layout | screenshot | model | act | verify | mean s / episode |
|---|---|---|---|---|---|---|---|
| kev-4b-base | 340 | 795 | - | 186 | 16 | 16 | 5.2 |
| kev-4b-ft | 1115 | 795 | - | 170 | 16 | 14 | 15.7 |

## Success by task (successes / runs)

| task | kev-4b-base | kev-4b-ft |
|---|---|---|
| android_version | 0/5 | 0/5 |
| build_number | 0/5 | 0/5 |
| device_model | 0/5 | 5/5 |
| battery_level | 0/5 | 0/5 |
| security_update | 0/5 | 0/5 |
| kernel_version | 0/5 | 0/5 |
| wifi_name | 0/5 | 5/5 |
| ip_address | 0/5 | 5/5 |
| screen_timeout_info | 0/5 | 5/5 |
| time_zone | 0/5 | 5/5 |
| dark_theme | 0/5 | 5/5 |
| airplane_mode | 0/5 | 5/5 |
| screen_timeout_5min | 0/5 | 5/5 |
| battery_saver | 0/5 | 0/5 |
| battery_percentage | 0/5 | 5/5 |
| do_not_disturb | 0/5 | 5/5 |
| wifi_off | 0/5 | 0/5 |
| color_inversion | 0/5 | 0/5 |
| extra_dim | 0/5 | 0/5 |
| bold_text | 0/5 | 0/5 |
| clock_24h | 0/5 | 0/5 |
| location_off | 0/5 | 0/5 |
| bluetooth_off | 0/5 | 5/5 |
| high_contrast_text | 0/5 | 0/5 |
| font_size_max | 0/5 | 5/5 |
| bluetooth_page | 5/5 | 5/5 |
| stopwatch_open | 5/5 | 5/5 |
| stopwatch_start | 0/5 | 0/5 |
| notification_history | 0/5 | 5/5 |
| all_apps_list | 5/5 | 5/5 |


## Live eval, loop-exp1

## Per model (at the run floor)

| model | n | success | reached | false_done | mean steps (success) | median model ms | success | false_done | wrong_answer | uncertain | stuck | unsafe_blocked | max_steps | error |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| kev-4b-base | 150 | 30% | 40% | 3% | 4.8 | 160 | 45 | 5 | 0 | 100 | 0 | 0 | 0 | 0 |
| kev-4b-ft | 150 | 57% | 63% | 0% | 5.2 | 166 | 85 | 0 | 0 | 30 | 35 | 0 | 0 | 0 |

## Success at other floors (re-scored from the recorded steps; - = below the run floor)

| model | floor 0.25 | floor 0.4 | floor 0.6 |
|---|---|---|---|
| kev-4b-base | 30% | 13% | 3% |
| kev-4b-ft | 57% | 47% | 40% |

## Median time per step (ms; settle after each action comes on top)

| model | steps | layout | screenshot | model | act | verify | mean s / episode |
|---|---|---|---|---|---|---|---|
| kev-4b-base | 515 | 797 | - | 160 | 16 | 23 | 7.5 |
| kev-4b-ft | 885 | 797 | - | 166 | 16 | 16 | 12.6 |

## Success by task (successes / runs)

| task | kev-4b-base | kev-4b-ft |
|---|---|---|
| android_version | 0/5 | 0/5 |
| build_number | 0/5 | 0/5 |
| device_model | 0/5 | 5/5 |
| battery_level | 0/5 | 0/5 |
| security_update | 0/5 | 0/5 |
| kernel_version | 0/5 | 0/5 |
| wifi_name | 0/5 | 5/5 |
| ip_address | 0/5 | 5/5 |
| screen_timeout_info | 5/5 | 5/5 |
| time_zone | 0/5 | 5/5 |
| dark_theme | 5/5 | 5/5 |
| airplane_mode | 5/5 | 5/5 |
| screen_timeout_5min | 5/5 | 5/5 |
| battery_saver | 0/5 | 5/5 |
| battery_percentage | 0/5 | 5/5 |
| do_not_disturb | 0/5 | 5/5 |
| wifi_off | 5/5 | 5/5 |
| color_inversion | 0/5 | 0/5 |
| extra_dim | 0/5 | 0/5 |
| bold_text | 0/5 | 0/5 |
| clock_24h | 0/5 | 0/5 |
| location_off | 0/5 | 0/5 |
| bluetooth_off | 5/5 | 5/5 |
| high_contrast_text | 0/5 | 0/5 |
| font_size_max | 0/5 | 0/5 |
| bluetooth_page | 5/5 | 5/5 |
| stopwatch_open | 5/5 | 5/5 |
| stopwatch_start | 0/5 | 0/5 |
| notification_history | 0/5 | 5/5 |
| all_apps_list | 5/5 | 5/5 |


## Round 2: on-policy corrections (android-v2)

android-v2 = android-v1 + 1 epoch on 1,333 states the v1 model visited on 200 training goals (labelled by the crawl-graph oracle: path step, shortcut, scroll or back) + 3,000 replayed v1 records. Temperature refitted on the held-out pages. kev.serve is deterministic, so one run per task is the whole answer.

| held-out pages | kev-4b | v1 | v2 |
|---|---|---|---|
| choice accuracy | 0.560 | 0.807 | 0.821 |
| done accuracy | 0.883 | 0.965 | 0.967 |
| ECE after calibration (kev-4b: shipped temperature) | 0.112 | 0.026 | 0.020 |

### 30 Settings tasks, experiment loop (success per task)

| task | kev-4b | v1 | v2 | d3:4b |
|---|---|---|---|---|
| android_version | 0/5 | 0/5 | 0/1 | 1/1 |
| build_number | 0/5 | 0/5 | 0/1 | 1/1 |
| device_model | 0/5 | 5/5 | 1/1 | 1/1 |
| battery_level | 0/5 | 0/5 | 0/1 | 1/1 |
| security_update | 0/5 | 0/5 | 0/1 | 0/1 |
| kernel_version | 0/5 | 0/5 | 0/1 | 0/1 |
| wifi_name | 0/5 | 5/5 | 0/1 | 1/1 |
| ip_address | 0/5 | 5/5 | 0/1 | 1/1 |
| screen_timeout_info | 5/5 | 5/5 | 1/1 | 1/1 |
| time_zone | 0/5 | 5/5 | 1/1 | 0/1 |
| dark_theme | 5/5 | 5/5 | 1/1 | 1/1 |
| airplane_mode | 5/5 | 5/5 | 1/1 | 1/1 |
| screen_timeout_5min | 5/5 | 5/5 | 1/1 | 1/1 |
| battery_saver | 0/5 | 5/5 | 1/1 | 1/1 |
| battery_percentage | 0/5 | 5/5 | 1/1 | 1/1 |
| do_not_disturb | 0/5 | 5/5 | 1/1 | 1/1 |
| wifi_off | 5/5 | 5/5 | 1/1 | 1/1 |
| color_inversion | 0/5 | 0/5 | 0/1 | 0/1 |
| extra_dim | 0/5 | 0/5 | 0/1 | 0/1 |
| bold_text | 0/5 | 0/5 | 0/1 | 0/1 |
| clock_24h | 0/5 | 0/5 | 0/1 | 0/1 |
| location_off | 0/5 | 0/5 | 0/1 | 0/1 |
| bluetooth_off | 5/5 | 5/5 | 1/1 | 1/1 |
| high_contrast_text | 0/5 | 0/5 | 0/1 | 0/1 |
| font_size_max | 0/5 | 0/5 | 0/1 | 0/1 |
| bluetooth_page | 5/5 | 5/5 | 1/1 | 1/1 |
| stopwatch_open | 5/5 | 5/5 | 1/1 | 1/1 |
| stopwatch_start | 0/5 | 0/5 | 0/1 | 1/1 |
| notification_history | 0/5 | 5/5 | 1/1 | 1/1 |
| all_apps_list | 5/5 | 5/5 | 1/1 | 1/1 |
| **tasks solved** | **9/30** | **17/30** | **15/30** | **20/30** |
| **success rate** | **30%** | **57%** | **50%** | **67%** |

### 30 Settings tasks, original loop

| **tasks solved** | **3/30** | **16/30** | **13/30** |
| **success rate** | **10%** | **53%** | **43%** |

## A new app: Phone (never crawled, 10 tasks, experiment loop)

| task | kev-4b | v1 | v2 | d3:4b |
|---|---|---|---|---|
| phone_keypad | 1/1 | 1/1 | 1/1 | 3/3 |
| phone_recents | 0/1 | 1/1 | 0/1 | 3/3 |
| phone_contacts | 0/1 | 0/1 | 1/1 | 3/3 |
| phone_voicemail | 0/1 | 1/1 | 0/1 | 0/3 |
| phone_settings | 0/1 | 0/1 | 0/1 | 3/3 |
| phone_call_history | 0/1 | 0/1 | 0/1 | 0/3 |
| phone_blocked | 1/1 | 0/1 | 0/1 | 2/3 |
| phone_quick_responses | 0/1 | 0/1 | 0/1 | 0/3 |
| phone_call_settings | 0/1 | 0/1 | 0/1 | 0/3 |
| phone_sort_order | 0/1 | 0/1 | 0/1 | 0/3 |
| **tasks solved** | **2/10** | **3/10** | **2/10** | **5/10** |
| **success rate** | **20%** | **30%** | **20%** | **47%** |

## Conclusions (2026-10-29)

- **Round 1 (crawl data) is the win:** kev-4b goes from 9/30 to 17/30 Settings tasks (30% -> 57%, experiment loop) and
  from 3/30 to 16/30 in the original loop, without any vision. d3:4b with screenshots still leads (20/30).
- **Round 2 (on-policy corrections) did not help the live tasks:** 15/30. It is slightly better on held-out pages
  (choice 0.807 -> 0.821, calibration ECE 0.026 -> 0.020) but lost wifi_name and ip_address: on the right page it left
  (`back`) or picked the wrong answer. The rollout labels are 25% `back` (round 1: 7.5%), which likely shifted the
  model toward leaving pages. One training seed, so a 2-task difference is weak evidence either way, but the held-out
  pages agree: of 943 action questions (103 labelled back), kev-4b predicts back 38 times (20 wrongly), v1 144 (54),
  v2 172 (77); mean p(back) 0.09 / 0.15 / 0.18.
- **No transfer to a new app:** on the never-crawled Phone app the fine-tunes score 3/10 (v1) and 2/10 (v2) against
  2/10 for kev-4b and 5/10 for d3:4b. 8 of 10 Phone goals made v2 tap Settings on the home screen: the training data
  only ever started with Settings or Clock.
- **A review of the data pipeline found two problems that qualify rounds 1 and 2:**
  1. The held-out pages were excluded as *targets* but not as *wrong turns*: v1's training data holds 14 records
     "Battery page -> not done, back", 12 for About emulated device, 11 for Stopwatch and 7 for Location. Those are
     exactly the pages of battery_level, android_version/build_number, stopwatch_start and location_off, which no
     fine-tune ever solved (d3:4b solves most of them). The holdout actively taught the model to leave them.
     It also kept 42 records that pass *through* the held-out Notifications page to other targets, which likely
     helped notification_history (5/5).
  2. Round 2's rollouts included goals on the dev pages, so v2's dev scores (0.821 choice) are not clean.
- **Round 3 (prepared, not run, ~2.5 h GPU):** rebuilt without either problem (no record on a held-out page or on
  a path through one, rollouts on dev pages dropped, Wi‑Fi with Android's non-breaking hyphen caught, dialogs no
  longer "pages").  `finetune/data/v3/train.jsonl` (8,098 records) = all of the cleaned round-1 data
  (`data/v1b`, 6,751) + 987 on-policy corrections (half the `back` states) + 3 x 120 home-screen records teaching the
  right app icon for five other apps, trained from kev-4b (not from the leaky android-v1), ~2.6 h. Run
  `finetune/run/r3-window.sh` when the GPU is free; it also scores every model on 10 drawer-app tasks (Contacts, Files, Messages: `tasks-apps.json`).

## Round 3 (android-v3: balanced backs, more replay, home-screen app choice)

| held-out pages | v1 | v2 | v3 |
|---|---|---|---|
| choice accuracy | 0.807 | 0.821 | 0.814 |
| done accuracy | 0.965 | 0.967 | 0.975 |

### 30 Settings tasks, experiment loop

| **tasks solved** | **17/30** | **15/30** | **16/30** |
| **success rate** | **57%** | **50%** | **53%** |

### 30 Settings tasks, original loop

| **tasks solved** | **16/30** | **13/30** | **17/30** |
| **success rate** | **53%** | **43%** | **57%** |

### Phone app

| task | kev-4b | v1 | v2 | v3 | d3:4b |
|---|---|---|---|---|---|
| phone_keypad | 1/1 | 1/1 | 1/1 | 1/1 | 3/3 |
| phone_recents | 0/1 | 1/1 | 0/1 | 0/1 | 3/3 |
| phone_contacts | 0/1 | 0/1 | 1/1 | 1/1 | 3/3 |
| phone_voicemail | 0/1 | 1/1 | 0/1 | 0/1 | 0/3 |
| phone_settings | 0/1 | 0/1 | 0/1 | 0/1 | 3/3 |
| phone_call_history | 0/1 | 0/1 | 0/1 | 0/1 | 0/3 |
| phone_blocked | 1/1 | 0/1 | 0/1 | 0/1 | 2/3 |
| phone_quick_responses | 0/1 | 0/1 | 0/1 | 0/1 | 0/3 |
| phone_call_settings | 0/1 | 0/1 | 0/1 | 0/1 | 0/3 |
| phone_sort_order | 0/1 | 0/1 | 0/1 | 0/1 | 0/3 |
| **tasks solved** | **2/10** | **3/10** | **2/10** | **2/10** | **5/10** |
| **success rate** | **20%** | **30%** | **20%** | **20%** | **47%** |

### Drawer apps: Contacts, Files, Messages

| task | kev-4b | v1 | v2 | v3 | d3:4b |
|---|---|---|---|---|---|
| contacts_create | 0/1 | 0/1 | 0/1 | 0/1 | 0/3 |
| contacts_organize | 0/1 | 0/1 | 0/1 | 0/1 | 0/3 |
| contacts_favorites | 0/1 | 0/1 | 0/1 | 0/1 | 0/3 |
| contacts_settings | 0/1 | 0/1 | 0/1 | 0/1 | 1/3 |
| contacts_sort | 0/1 | 0/1 | 0/1 | 0/1 | 0/3 |
| files_downloads | 0/1 | 1/1 | 1/1 | 0/1 | 3/3 |
| files_roots | 0/1 | 0/1 | 0/1 | 0/1 | 0/3 |
| files_new_folder | 0/1 | 0/1 | 0/1 | 0/1 | 0/3 |
| files_sort | 0/1 | 0/1 | 0/1 | 0/1 | 0/3 |
| messages_no_account | 0/1 | 0/1 | 0/1 | 0/1 | 3/3 |
| **tasks solved** | **0/10** | **1/10** | **1/10** | **0/10** | **3/10** |
| **success rate** | **0%** | **10%** | **10%** | **0%** | **23%** |

### Round 3 conclusions (2026-10-30)

- **Held-out pages:** v3 is the best of the three on choice 0.814 and done 0.975 (calibrated T 2.05). These dev pages
  are clean for v1 and v3; v2's dev number is not (rollouts on dev pages).
- **30 Settings tasks:** v3 solves 16/30 with the experiment loop and 17/30 with the original loop. v1 solves 17 and
  16. So v3 is on par with v1, not better.
  - The clean holdout gained stopwatch_start, one of the leaked pages.
  - battery_level, android_version, build_number and location_off still fail, so the leak explains at most one of
    the five tasks it touched.
  - wifi_name and ip_address are lost in both rounds that include on-policy data (v2, v3).
- **New apps:** no transfer at all.
  - Phone: v3 solves 2/10 and still taps Settings first on 8 of 10 goals. The home-screen records named the app in
    most goals ("Open YouTube and ..."), while Phone goals ("Show my recent calls") do not.
  - Drawer apps: every kev variant solves 0-1/10, against d3:4b at 3/10 (23%).
- **Takeaway:** crawled in-app data takes text-only kev-4b from 30% to ~55% inside the app it was crawled from, about
  10 points behind d3:4b with screenshots. Neither on-policy corrections nor a few home-screen examples moved it
  further, and nothing transfers to unseen apps. More apps in the crawl, or a vision model, is the next lever.
