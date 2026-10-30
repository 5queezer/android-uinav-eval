# Android navigation eval: 150 episodes, 1 models, run floor 0.25

## Per model (at the run floor)

| model | n | success | reached | false_done | mean steps (success) | median model ms | success | false_done | wrong_answer | uncertain | stuck | unsafe_blocked | max_steps | error |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| kev | 150 | 30% | 40% | 3% | 4.8 | 160 | 45 | 5 | 0 | 100 | 0 | 0 | 0 | 0 |

## Success at other floors (re-scored from the recorded steps; - = below the run floor)

| model | floor 0.25 | floor 0.4 | floor 0.6 |
|---|---|---|---|
| kev | 30% | 13% | 3% |

## Median time per step (ms; settle after each action comes on top)

| model | steps | layout | screenshot | model | act | verify | mean s / episode |
|---|---|---|---|---|---|---|---|
| kev | 515 | 797 | - | 160 | 16 | 23 | 7.5 |

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
| screen_timeout_info | 5/5 |
| time_zone | 0/5 |
| dark_theme | 5/5 |
| airplane_mode | 5/5 |
| screen_timeout_5min | 5/5 |
| battery_saver | 0/5 |
| battery_percentage | 0/5 |
| do_not_disturb | 0/5 |
| wifi_off | 5/5 |
| color_inversion | 0/5 |
| extra_dim | 0/5 |
| bold_text | 0/5 |
| clock_24h | 0/5 |
| location_off | 0/5 |
| bluetooth_off | 5/5 |
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
| 25 | uncertain @ 'Home' (button 'Settings') | kev 25 |
| 20 | uncertain @ 'Settings' (scroll_down) | kev 20 |
| 15 | uncertain @ 'Home' (list item '') | kev 15 |
| 5 | uncertain @ 'Security & privacy' (scroll_down) | kev 5 |
| 5 | uncertain @ 'Network details' (scroll_up) | kev 5 |
| 5 | false_done @ 'Battery Saver' (list item 'Extreme Battery Saver: Includes all changes listed above. Also pauses non-essential apps and their notifications. [on]') | kev 5 |
| 5 | uncertain @ 'Do Not Disturb' (list item 'Schedules: None') | kev 5 |
| 5 | uncertain @ 'Display & touch' (scroll_down) | kev 5 |
| 5 | uncertain @ 'Clock' (back) | kev 5 |
| 5 | uncertain @ 'Apps' (list item 'Special app access') | kev 5 |
| 5 | uncertain @ 'Color inversion' (list item 'Use color inversion [off]') | kev 5 |
| 5 | uncertain @ 'Stopwatch' (scroll_down) | kev 5 |
