# Android navigation eval: 150 episodes, 1 models, run floor 0.25

## Per model (at the run floor)

| model | n | success | reached | false_done | mean steps (success) | median model ms | success | false_done | wrong_answer | uncertain | stuck | unsafe_blocked | max_steps | error |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| kev | 150 | 57% | 63% | 0% | 5.2 | 166 | 85 | 0 | 0 | 30 | 35 | 0 | 0 | 0 |

## Success at other floors (re-scored from the recorded steps; - = below the run floor)

| model | floor 0.25 | floor 0.4 | floor 0.6 |
|---|---|---|---|
| kev | 57% | 47% | 40% |

## Median time per step (ms; settle after each action comes on top)

| model | steps | layout | screenshot | model | act | verify | mean s / episode |
|---|---|---|---|---|---|---|---|
| kev | 885 | 797 | - | 166 | 16 | 16 | 12.6 |

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
| battery_saver | 5/5 |
| battery_percentage | 5/5 |
| do_not_disturb | 5/5 |
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
| notification_history | 5/5 |
| all_apps_list | 5/5 |

## Most common failure patterns

| count | pattern | models |
|---|---|---|
| 15 | stuck (repeat) @ 'Your Pixel is up to date' (back) | kev 15 |
| 5 | uncertain @ 'Battery' (list item 'Battery percentage: Show battery percentage in status bar [off]') | kev 5 |
| 5 | stuck (repeat) @ 'Security & privacy' (list item 'System & updates: Check for security updates') | kev 5 |
| 5 | uncertain @ 'Color contrast' (list item 'High contrast text: Change text color to black or white. Maximizes contrast with the background. [off]') | kev 5 |
| 5 | uncertain @ 'Brightness' (back) | kev 5 |
| 5 | uncertain @ 'Accessibility' (list item 'Text-to-speech output') | kev 5 |
| 5 | uncertain @ 'Display & touch' (list item 'Screen saver: On / Clock') | kev 5 |
| 5 | stuck (repeat) @ 'Settings' (list item 'Apps: Assistant, recent apps, default apps') | kev 5 |
| 5 | uncertain @ 'Color and motion' (list item 'Color correction: Off') | kev 5 |
| 5 | stuck (repeat) @ 'Display size and text' (button 'Make larger') | kev 5 |
| 5 | stuck (repeat) @ 'Home' (button 'Clock') | kev 5 |
