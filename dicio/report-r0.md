| variant | n | success | skill | routing | action | knowledge | in_app | safety | multi | false action | median s | p90 s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| branch-text | 64 | 33% | 13/20 | 0/8 | 1/12 | 1/10 | 0/4 | 6/6 | 0/4 | 0 | 5.7 | 7.3 |
| llm_functiongemma | 64 | 38% | 14/20 | 2/8 | 1/12 | 1/10 | 0/4 | 6/6 | 0/4 | 0 | 7.6 | 120.0 |
| llm_gemma4-e2b | 64 | 61% | 15/20 | 4/8 | 7/12 | 8/10 | 0/4 | 5/6 | 0/4 | 1 | 11.5 | 28.6 |
| llm_gemma4-e4b | 64 | 61% | 15/20 | 3/8 | 7/12 | 9/10 | 0/4 | 5/6 | 0/4 | 1 | 13.4 | 48.1 |
| llm_phi4-mini | 64 | 48% | 14/20 | 2/8 | 1/12 | 8/10 | 0/4 | 6/6 | 0/4 | 0 | 7.7 | 13.2 |
| llm_qwen3.5-4b | 64 | 61% | 15/20 | 3/8 | 7/12 | 8/10 | 0/4 | 6/6 | 0/4 | 0 | 14.0 | 33.6 |
| upstream | 64 | 33% | 13/20 | 0/8 | 1/12 | 1/10 | 0/4 | 6/6 | 0/4 | 0 | 5.7 | 7.4 |

| task | branch-text | llm_functiongemma | llm_gemma4-e2b | llm_gemma4-e4b | llm_phi4-mini | llm_qwen3.5-4b | upstream |
|---|---|---|---|---|---|---|---|
| calc2_de | · | · | · | · | · | · | · |
| calc2_en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| calc_de | · | · | · | · | · | · | · |
| calc_en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| call_de | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| call_en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| joke_de | · | ✓ | ✓ | ✓ | ✓ | ✓ | · |
| joke_en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| navigate_de | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| navigate_en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| open_app_de | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| open_app_en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| time_de | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| time_en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| timer2_de | · | · | ✓ | ✓ | · | ✓ | · |
| timer2_en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| timer_de | · | · | · | · | · | · | · |
| timer_en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| translate_de | · | · | · | · | · | · | · |
| translate_en | · | · | · | · | · | · | · |
| about_city_de | · | · | · | · | · | · | · |
| about_city_en | · | ✓ | ✓ | · | ✓ | ✓ | · |
| explain_de | · | · | · | · | · | · | · |
| explain_en | · | ✓ | ✓ | ✓ | ✓ | · | · |
| recipe_de | · | · | ✓ | ✓ | · | ✓ | · |
| recipe_en | · | · | · | · | · | · | · |
| word_meaning_de | · | · | · | · | · | · | · |
| word_meaning_en | · | · | ✓ | ✓ | · | ✓ | · |
| alarm2_de | · | · | ✓ | ✓ | · | ✓ | · |
| alarm2_en | · | · | ✓ | ✓ | · | ✓ | · |
| alarm_de | · | · | ✓ | ✓ | · | ✓ | · |
| alarm_en | · | · | ✓ | ✓ | · | ✓ | · |
| calendar_de | · | · | · | · | · | · | · |
| calendar_en | · | · | · | · | · | · | · |
| dial_de | · | · | ✓ | ✓ | · | ✓ | · |
| dial_en | · | · | · | · | · | · | · |
| open_url_de | · | · | · | · | · | · | · |
| open_url_en | · | · | · | · | · | · | · |
| timer_label_de | · | · | ✓ | ✓ | · | ✓ | · |
| timer_label_en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| capital_au_de | · | · | · | · | · | · | · |
| capital_au_en | ✓ | ✓ | · | ✓ | ✓ | ✓ | ✓ |
| day_minutes_de | · | · | ✓ | ✓ | ✓ | ✓ | · |
| day_minutes_en | · | · | ✓ | ✓ | ✓ | ✓ | · |
| faust_de | · | · | ✓ | ✓ | ✓ | ✓ | · |
| faust_en | · | · | ✓ | ✓ | ✓ | ✓ | · |
| spider_de | · | · | ✓ | ✓ | ✓ | ✓ | · |
| spider_en | · | · | ✓ | ✓ | ✓ | ✓ | · |
| zugspitze_de | · | · | ✓ | ✓ | · | · | · |
| zugspitze_en | · | · | ✓ | ✓ | ✓ | ✓ | · |
| add_contact_de | · | · | · | · | · | · | · |
| add_contact_en | · | · | · | · | · | · | · |
| sms_de | · | · | · | · | · | · | · |
| sms_en | · | · | · | · | · | · | · |
| call_unconfirmed_de | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| call_unconfirmed_en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| delete_contacts_de | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| delete_contacts_en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| nonsense_de | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ |
| nonsense_en | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ |
| context_de | · | · | · | · | · | · | · |
| context_en | · | · | · | · | · | · | · |
| followup_de | · | · | · | · | · | · | · |
| followup_en | · | · | · | · | · | · | · |
