# Android navigation eval: 750 episodes, 5 models, run floor 0.25

## Per model (at the run floor)

| model | n | success | reached | false_done | mean steps (success) | median model ms | success | false_done | wrong_answer | uncertain | stuck | unsafe_blocked | max_steps | error |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| clef-flash-8k | 150 | 52% | 59% | 0% | 5.0 | 448 | 78 | 0 | 0 | 49 | 15 | 0 | 8 | 0 |
| d3:4b | 150 | 63% | 63% | 0% | 4.8 | 436 | 94 | 0 | 0 | 15 | 26 | 5 | 10 | 0 |
| d3:9b | 150 | 62% | 62% | 0% | 4.9 | 790 | 93 | 0 | 0 | 20 | 22 | 0 | 15 | 0 |
| kev | 150 | 23% | 33% | 3% | 4.4 | 274 | 34 | 4 | 0 | 92 | 20 | 0 | 0 | 0 |
| tev1:4b | 150 | 23% | 39% | 0% | 4.6 | 164 | 35 | 0 | 0 | 18 | 84 | 0 | 13 | 0 |

## Success at other floors (re-scored from the recorded steps; - = below the run floor)

| model | floor 0.25 | floor 0.4 | floor 0.5 | floor 0.6 |
|---|---|---|---|---|
| clef-flash-8k | 52% | 43% | 33% | 25% |
| d3:4b | 63% | 60% | 55% | 45% |
| d3:9b | 62% | 59% | 53% | 41% |
| kev | 23% | 17% | 8% | 7% |
| tev1:4b | 23% | 21% | 20% | 20% |

## Median time per step (ms; settle after each action comes on top)

| model | steps | layout | screenshot | model | act | verify | mean s / episode |
|---|---|---|---|---|---|---|---|
| clef-flash-8k | 743 | 779 | 192 | 448 | 22 | 21 | 13.6 |
| d3:4b | 805 | 779 | 184 | 436 | 19 | 23 | 14.7 |
| d3:9b | 833 | 779 | 182 | 790 | 20 | 23 | 17.4 |
| kev | 514 | 779 | - | 274 | 18 | 22 | 8.0 |
| tev1:4b | 740 | 778 | - | 164 | 20 | 15 | 10.8 |

## Success by task (successes / runs)

| task | clef-flash-8k | d3:4b | d3:9b | kev | tev1:4b |
|---|---|---|---|---|---|
| android_version | 5/5 | 5/5 | 5/5 | 0/5 | 0/5 |
| build_number | 5/5 | 5/5 | 5/5 | 0/5 | 0/5 |
| device_model | 4/5 | 5/5 | 0/5 | 0/5 | 0/5 |
| battery_level | 5/5 | 5/5 | 5/5 | 0/5 | 0/5 |
| security_update | 0/5 | 0/5 | 5/5 | 0/5 | 0/5 |
| kernel_version | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| wifi_name | 5/5 | 5/5 | 5/5 | 5/5 | 0/5 |
| ip_address | 5/5 | 5/5 | 5/5 | 0/5 | 0/5 |
| screen_timeout_info | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| time_zone | 4/5 | 0/5 | 5/5 | 0/5 | 1/5 |
| dark_theme | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| airplane_mode | 5/5 | 5/5 | 5/5 | 5/5 | 0/5 |
| screen_timeout_5min | 0/5 | 5/5 | 5/5 | 5/5 | 2/5 |
| battery_saver | 2/5 | 5/5 | 3/5 | 0/5 | 1/5 |
| battery_percentage | 0/5 | 5/5 | 0/5 | 4/5 | 0/5 |
| do_not_disturb | 5/5 | 4/5 | 5/5 | 0/5 | 5/5 |
| wifi_off | 3/5 | 5/5 | 5/5 | 0/5 | 0/5 |
| color_inversion | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| extra_dim | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| bold_text | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| clock_24h | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| location_off | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| bluetooth_off | 0/5 | 5/5 | 5/5 | 0/5 | 0/5 |
| high_contrast_text | 0/5 | 0/5 | 0/5 | 0/5 | 1/5 |
| font_size_max | 1/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| bluetooth_page | 5/5 | 5/5 | 5/5 | 0/5 | 5/5 |
| stopwatch_open | 5/5 | 5/5 | 5/5 | 0/5 | 5/5 |
| stopwatch_start | 4/5 | 5/5 | 5/5 | 0/5 | 0/5 |
| notification_history | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| all_apps_list | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |

## Most common failure patterns

| count | pattern | models |
|---|---|---|
| 60 | stuck @ 'Home' (stuck) | d3:9b 20, tev1:4b 20, clef-flash-8k 10, d3:4b 10 |
| 41 | stuck @ 'Settings' (stuck) | tev1:4b 41 |
| 22 | uncertain @ 'Settings' (scroll_down) | kev 17, clef-flash-8k 5 |
| 16 | uncertain @ 'Home' (button 'Settings') | kev 16 |
| 15 | uncertain @ 'Home' (stuck) | kev 15 |
| 15 | stuck @ 'Stopwatch' (stuck) | kev 10, tev1:4b 5 |
| 11 | uncertain @ 'Settings Services' (back) | clef-flash-8k 11 |
| 10 | stuck @ 'About emulated device' (stuck) | clef-flash-8k 5, d3:4b 5 |
| 10 | uncertain @ 'Brightness' (stuck) | clef-flash-8k 5, d3:9b 5 |
| 10 | stuck @ 'Brightness' (stuck) | d3:4b 5, kev 5 |
| 10 | uncertain @ 'Popup Window' (stuck) | d3:9b 5, kev 5 |
| 9 | uncertain @ 'Location' (button 'More options') | d3:9b 5, clef-flash-8k 4 |
| 9 | uncertain @ 'Connected devices' (stuck) | kev 9 |
| 8 | max_steps @ 'Accessibility' (scroll_down) | d3:4b 5, tev1:4b 3 |
| 7 | uncertain @ 'Internet' (scroll_down) | kev 5, clef-flash-8k 2 |
