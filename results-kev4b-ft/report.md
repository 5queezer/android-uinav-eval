# Android navigation eval: 150 episodes, 1 models, run floor 0.25

## Per model (at the run floor)

| model | n | success | reached | false_done | mean steps (success) | median model ms | success | false_done | wrong_answer | uncertain | stuck | unsafe_blocked | max_steps | error |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| kev | 150 | 53% | 63% | 3% | 5.7 | 170 | 80 | 5 | 0 | 40 | 0 | 0 | 25 | 0 |

## Success at other floors (re-scored from the recorded steps; - = below the run floor)

| model | floor 0.25 | floor 0.4 | floor 0.6 |
|---|---|---|---|
| kev | 53% | 43% | 40% |

## Median time per step (ms; settle after each action comes on top)

| model | steps | layout | screenshot | model | act | verify | mean s / episode |
|---|---|---|---|---|---|---|---|
| kev | 1115 | 795 | - | 170 | 16 | 14 | 15.7 |

## Success by task (successes / runs)

| task | kev |
|---|---|
| android_version | 0/5 |
| build_number | 0/5 |
| device_model | 5/5 |
| battery_level | 0/5 |
| security_update | 0/5 |
| kernel_version | 0/5 |
| wifi_name | 5/5 |
| ip_address | 5/5 |
| screen_timeout_info | 5/5 |
| time_zone | 5/5 |
| dark_theme | 5/5 |
| airplane_mode | 5/5 |
| screen_timeout_5min | 5/5 |
| battery_saver | 0/5 |
| battery_percentage | 5/5 |
| do_not_disturb | 5/5 |
| wifi_off | 0/5 |
| color_inversion | 0/5 |
| extra_dim | 0/5 |
| bold_text | 0/5 |
| clock_24h | 0/5 |
| location_off | 0/5 |
| bluetooth_off | 5/5 |
| high_contrast_text | 0/5 |
| font_size_max | 5/5 |
| bluetooth_page | 5/5 |
| stopwatch_open | 5/5 |
| stopwatch_start | 0/5 |
| notification_history | 5/5 |
| all_apps_list | 5/5 |

## Most common failure patterns

| count | pattern | models |
|---|---|---|
| 10 | max_steps @ 'System' (scroll_down) | kev 10 |
| 5 | uncertain @ 'Battery' (list item 'Battery percentage: Show battery percentage in status bar') | kev 5 |
| 5 | uncertain @ 'System & updates' (back) | kev 5 |
| 5 | max_steps @ 'System' (list item 'Software updates: Your Pixel is up to date') | kev 5 |
| 5 | false_done @ 'Battery Saver' (list item 'Use Battery Saver') | kev 5 |
| 5 | uncertain @ 'Internet' (list item 'Wi-Fi') | kev 5 |
| 5 | uncertain @ 'Colors' (back) | kev 5 |
| 5 | uncertain @ 'Display & touch' (scroll_down) | kev 5 |
| 5 | uncertain @ 'Accessibility' (scroll_down) | kev 5 |
| 5 | uncertain @ 'Display & touch' (list item 'Screen saver: On / Clock') | kev 5 |
| 5 | max_steps @ 'Apps' (back) | kev 5 |
| 5 | uncertain @ 'Color and motion' (list item 'Color correction: Off') | kev 5 |
| 5 | max_steps @ 'Home' (button 'Clock') | kev 5 |
