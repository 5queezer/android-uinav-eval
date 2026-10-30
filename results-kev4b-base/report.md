# Android navigation eval: 150 episodes, 1 models, run floor 0.25

## Per model (at the run floor)

| model | n | success | reached | false_done | mean steps (success) | median model ms | success | false_done | wrong_answer | uncertain | stuck | unsafe_blocked | max_steps | error |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| kev | 150 | 10% | 17% | 0% | 4.0 | 186 | 15 | 0 | 0 | 60 | 75 | 0 | 0 | 0 |

## Success at other floors (re-scored from the recorded steps; - = below the run floor)

| model | floor 0.25 | floor 0.4 | floor 0.6 |
|---|---|---|---|
| kev | 10% | 7% | 3% |

## Median time per step (ms; settle after each action comes on top)

| model | steps | layout | screenshot | model | act | verify | mean s / episode |
|---|---|---|---|---|---|---|---|
| kev | 340 | 795 | - | 186 | 16 | 16 | 5.2 |

## Success by task (successes / runs)

| task | kev |
|---|---|
| android_version | 0/5 |
| build_number | 0/5 |
| device_model | 0/5 |
| battery_level | 0/5 |
| security_update | 0/5 |
| kernel_version | 0/5 |
| wifi_name | 0/5 |
| ip_address | 0/5 |
| screen_timeout_info | 0/5 |
| time_zone | 0/5 |
| dark_theme | 0/5 |
| airplane_mode | 0/5 |
| screen_timeout_5min | 0/5 |
| battery_saver | 0/5 |
| battery_percentage | 0/5 |
| do_not_disturb | 0/5 |
| wifi_off | 0/5 |
| color_inversion | 0/5 |
| extra_dim | 0/5 |
| bold_text | 0/5 |
| clock_24h | 0/5 |
| location_off | 0/5 |
| bluetooth_off | 0/5 |
| high_contrast_text | 0/5 |
| font_size_max | 0/5 |
| bluetooth_page | 5/5 |
| stopwatch_open | 5/5 |
| stopwatch_start | 0/5 |
| notification_history | 0/5 |
| all_apps_list | 5/5 |

## Most common failure patterns

| count | pattern | models |
|---|---|---|
| 45 | stuck @ 'Settings' (stuck) | kev 45 |
| 25 | uncertain @ 'Home' (stuck) | kev 25 |
| 15 | stuck @ 'Home' (stuck) | kev 15 |
| 5 | uncertain @ 'Settings' (stuck) | kev 5 |
| 5 | uncertain @ 'Network & internet' (list item 'Internet: AndroidWifi') | kev 5 |
| 5 | uncertain @ 'Settings' (list item 'Network & internet: Mobile, Wi‑Fi, hotspot') | kev 5 |
| 5 | stuck @ 'Battery' (stuck) | kev 5 |
| 5 | uncertain @ 'Do Not Disturb' (stuck) | kev 5 |
| 5 | stuck @ 'Network & internet' (stuck) | kev 5 |
| 5 | uncertain @ 'Clock' (stuck) | kev 5 |
| 5 | uncertain @ 'Apps' (stuck) | kev 5 |
| 5 | uncertain @ 'Connected devices' (list item 'Connection preferences: Bluetooth, Android Auto') | kev 5 |
| 5 | stuck @ 'Stopwatch' (stuck) | kev 5 |
