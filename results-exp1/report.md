# Android navigation eval: 90 episodes, 3 models, run floor 0.25

## Per model (at the run floor)

| model | n | success | reached | false_done | mean steps (success) | median model ms | success | false_done | wrong_answer | uncertain | stuck | unsafe_blocked | max_steps | error |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| clef-flash-8k | 30 | 60% | 63% | 0% | 5.4 | 402 | 18 | 0 | 0 | 11 | 1 | 0 | 0 | 0 |
| d3:4b | 30 | 67% | 67% | 0% | 4.8 | 439 | 20 | 0 | 0 | 4 | 5 | 1 | 0 | 0 |
| tev1:4b | 30 | 33% | 47% | 0% | 4.9 | 156 | 10 | 0 | 0 | 4 | 15 | 0 | 1 | 0 |

## Success at other floors (re-scored from the recorded steps; - = below the run floor)

| model | floor 0.25 | floor 0.4 | floor 0.5 | floor 0.6 |
|---|---|---|---|---|
| clef-flash-8k | 60% | 43% | 30% | 30% |
| d3:4b | 67% | 63% | 57% | 53% |
| tev1:4b | 33% | 30% | 20% | 20% |

## Median time per step (ms; settle after each action comes on top)

| model | steps | layout | screenshot | model | act | verify | mean s / episode |
|---|---|---|---|---|---|---|---|
| clef-flash-8k | 154 | 780 | 184 | 402 | 21 | 20 | 13.6 |
| d3:4b | 162 | 778 | 183 | 439 | 18 | 22 | 16.2 |
| tev1:4b | 158 | 779 | - | 156 | 21 | 20 | 12.4 |

## Success by task (successes / runs)

| task | clef-flash-8k | d3:4b | tev1:4b |
|---|---|---|---|
| android_version | 0/1 | 1/1 | 0/1 |
| build_number | 1/1 | 1/1 | 0/1 |
| device_model | 0/1 | 1/1 | 0/1 |
| battery_level | 1/1 | 1/1 | 0/1 |
| security_update | 0/1 | 0/1 | 0/1 |
| kernel_version | 0/1 | 0/1 | 0/1 |
| wifi_name | 1/1 | 1/1 | 0/1 |
| ip_address | 1/1 | 1/1 | 0/1 |
| screen_timeout_info | 1/1 | 1/1 | 1/1 |
| time_zone | 1/1 | 0/1 | 0/1 |
| dark_theme | 1/1 | 1/1 | 1/1 |
| airplane_mode | 1/1 | 1/1 | 0/1 |
| screen_timeout_5min | 0/1 | 1/1 | 1/1 |
| battery_saver | 1/1 | 1/1 | 0/1 |
| battery_percentage | 1/1 | 1/1 | 0/1 |
| do_not_disturb | 1/1 | 1/1 | 1/1 |
| wifi_off | 1/1 | 1/1 | 1/1 |
| color_inversion | 0/1 | 0/1 | 0/1 |
| extra_dim | 0/1 | 0/1 | 0/1 |
| bold_text | 0/1 | 0/1 | 0/1 |
| clock_24h | 0/1 | 0/1 | 0/1 |
| location_off | 0/1 | 0/1 | 0/1 |
| bluetooth_off | 1/1 | 1/1 | 1/1 |
| high_contrast_text | 0/1 | 0/1 | 1/1 |
| font_size_max | 1/1 | 0/1 | 0/1 |
| bluetooth_page | 1/1 | 1/1 | 1/1 |
| stopwatch_open | 1/1 | 1/1 | 1/1 |
| stopwatch_start | 1/1 | 1/1 | 0/1 |
| notification_history | 0/1 | 1/1 | 0/1 |
| all_apps_list | 1/1 | 1/1 | 1/1 |

## Most common failure patterns

| count | pattern | models |
|---|---|---|
| 7 | stuck (repeat) @ 'Settings' (scroll_up) | tev1:4b 6, clef-flash-8k 1 |
| 4 | stuck (repeat) @ 'All apps' (scroll_up) | tev1:4b 4 |
| 2 | uncertain @ 'Settings Services' (back) | clef-flash-8k 2 |
| 1 | uncertain @ 'Settings' (scroll_down) | clef-flash-8k 1 |
| 1 | uncertain @ 'Settings' (list item 'Security & privacy: App security, device lock, permissions') | clef-flash-8k 1 |
| 1 | uncertain @ 'About emulated device' (scroll_up) | clef-flash-8k 1 |
| 1 | uncertain @ 'Settings' (list item 'Accessibility: Display, interaction, audio') | clef-flash-8k 1 |
| 1 | uncertain @ 'Brightness' (scroll_down) | clef-flash-8k 1 |
| 1 | uncertain @ 'Home' (button 'Settings') | clef-flash-8k 1 |
| 1 | uncertain @ 'Settings' (list item 'Style: Digital') | clef-flash-8k 1 |
| 1 | uncertain @ 'Location' (button 'More options') | clef-flash-8k 1 |
| 1 | uncertain @ 'Notification history' (scroll_down) | clef-flash-8k 1 |
| 1 | uncertain @ 'Settings Services' (button 'Back') | d3:4b 1 |
| 1 | stuck (repeat) @ 'About emulated device' (list item 'Build number: sdk_gphone64_x86_64-userdebug 15 AE3A.240806.043 12960925 dev-keys') | d3:4b 1 |
| 1 | stuck (repeat) @ '' (button 'Cancel') | d3:4b 1 |
