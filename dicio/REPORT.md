# Dicio mit LLM-Fallback: Benchmark und gemessene Fixes (Phase 1 + 2)

Stand: 2026-11-02. Alles lokal committet, nichts gepusht oder gepostet.

## Kurzfassung

- **Phase 1:** Ein Benchmark für Dicio im android-eval-Harness.
  - 64 Aufgaben, 32 deutsch und 32 englisch.
  - Geprüft wird der Gerätezustand: Wecker, Timer, Anrufliste, Kalender, Kontakte, Vordergrund-App. Zusätzlich die Antwort.
  - Jede Nebenwirkung, die eine Aufgabe nicht erlaubt, zählt als **falsche Aktion**.
- **Phase 2:**
  - `RemoteLlmEngine`: der LLM-Fallback über einen beliebigen OpenAI-kompatiblen Server, etwa Ollama oder llama.cpp im Heimnetz.
  - Fünf Modelle verglichen.
  - Sieben Fix-Stufen einzeln gemessen.
- **Ergebnis:**

  | Variante | Erfolg |
  |---|---|
  | Upstream-Dicio (ohne LLM) | 33% |
  | Dein Branch, Stand vor meinen Fixes, über den Remote-Server (Gemma 4 E4B / Qwen 3.5 4B, je 3 bzw. 2 Läufe) | 63% / 61% |
  | Nach allen Fixes (3 Läufe) | **72% / 73%** |

  Die Spannweiten der Einzelläufe überschneiden sich nicht: R0 59–64%, nach den Fixes 70–75%.

  - Die drei guten Modelle (Gemma 4 E4B, Gemma 4 E2B, Qwen 3.5 4B) liegen gleichauf.
  - Keines verliert eine Aufgabe, die vorher ging.
- **Was noch fehlt, liegt fast nicht am LLM:** 17 Aufgaben scheitern in jedem Lauf bei allen drei Modellen. Ursachen:
  - Upstream-Skills fangen die Anfrage ab, bevor das LLM sie bekommt (10).
  - Die Übersetzungs-API von Upstream ist tot (3 der 10, über Übersetzungs-Anfragen).
  - Es fehlt ein Werkzeug für Kontakte (Phase 4).
  - Ein Kontext-Loch zwischen Skills und LLM.
  - Die Kalender-App im Emulator.
- **Gemma 4 E2B** (2,5 GB) ist so gut wie E4B und schneller. Das ist der sinnvolle Standard für Geräte mit 8 GB RAM.
- **Latenz:** Der Median pro Aufgabe steigt von R0 nach s7 (Gemma 12,9 s → 17,7 s). Grund: Mehr Aufgaben erreichen jetzt das LLM statt einer schnellen Fehlermeldung. Pro LLM-Anfrage ist s7 schneller als s6, weil der Prompt-Cache wieder greift.

## Aufbau

- **Treiber `dicio_eval.py`**
  - Sendet einen Satz über einen Debug-Broadcast an Dicio. Der Receiver liegt nur in `src/debug` und kann beliebiges Unicode.
  - Wartet, bis sich die Antwort nicht mehr ändert, und prüft dann Antwort und Gerätezustand.
  - Jede Episode startet vom Emulator-Snapshot `dicio`: beide APKs installiert, drei Kontakte.
  - Die Einstellungen werden pro Episode per `run-as` direkt in Dicios DataStore geschrieben (Sprache, Fallback-Modus, Server).
- **Aufgaben** (`tasks-dicio.json`), je auf Deutsch und Englisch:

  | Kategorie | Anzahl | Inhalt |
  |---|---|---|
  | skill | 10 | Was Dicio selbst kann: Rechnen, Timer, Uhrzeit, App öffnen, Anrufen, Navigation, Witz, Übersetzen |
  | routing | 4 | LLM-Anfragen, die ein Skill wegschnappen könnte: „Erkläre … in einfachen Worten“, „Erzähl mir in zwei Sätzen …“ |
  | action | 6 | Nur mit LLM-Werkzeugen möglich: Wecker, Timer mit Name, Kalender, Webseite, Nummer wählen |
  | knowledge | 5 | Zugspitze, Canberra, Goethe, Spinnenbeine, Minuten pro Tag |
  | in_app | 2 | Kontakt anlegen, SMS. Braucht eigentlich Phase 4 |
  | safety | 3 | Unsinn, „Lösch alle Kontakte“, Anruf ohne Bestätigung. Keine Nebenwirkung erlaubt |
  | multi | 2 | Zwei Sätze in einem Gespräch |

- **Modelle**
  - Laufen als Q4_K_M-GGUF auf einem eigenen llama-server, Release b12024. Das ist nötig, weil der installierte llama.cpp `gemma4` nicht kennt.
  - Auf der CPU, weil die GPU die ganze Zeit von crp-rag-77 belegt war.
  - Dicio im Emulator erreicht den Server über `adb reverse`. Die Emulator-NAT `10.0.2.2` verlor nach Snapshot-Loads sporadisch Verbindungen; die betroffenen Episoden wurden verworfen und neu gemessen.

## Ergebnisse

Erfolgsquote über 64 Aufgaben. „1×“ heißt ein Lauf, „3×“ drei Läufe (192 Episoden).

| Stufe (kumulativ) | Text-Fallback | Gemma 4 E4B | Qwen 3.5 4B | Gemma 4 E2B | Phi-4-mini | FunctionGemma |
|---|---|---|---|---|---|---|
| Upstream (DicioTeam main) | 33% | – | – | – | – | – |
| R0: dein Branch + Remote-Engine | 33% | 61% (1×) | 61% (1×) | 61% | 48% | 38% |
| s1: Übersetzungs-Skill-Fix | 33% | 66% | 64% | | | |
| s2: + Temperatur 0,2 | | 64% | 64% | | | |
| s5: + 3 Werkzeuge, Review-Fixes | | 66% | 67% | | | |
| s6: + strengeres Routing, Datum im Prompt | 33% | 72% | 73% | | | |
| **s7: + Datum in der Nutzernachricht** | 33% | **72% (3×)** | **73% (3×)** | **73%** | 53% | 31% |
| R0 wiederholt | | 63% (3×: 64/61/64) | 61% (2×: 63/59) | | | |

### Nach Kategorie (s7, 3 Läufe)

| Modell | skill | routing | action | knowledge | in_app | safety | multi | falsche Aktionen | Median | p90 |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen 3.5 4B | 48/60 | 18/24 | 26/36 | 27/30 | 3/12 | 18/18 | 0/12 | 0 | 18,1 s | 34,7 s |
| Gemma 4 E4B | 48/60 | 18/24 | 27/36 | 24/30 | 3/12 | 18/18 | 1/12 | 3 | 17,7 s | 41,6 s |
| Gemma 4 E2B (1×) | 16/20 | 6/8 | 9/12 | 9/10 | 1/4 | 6/6 | 0/4 | 0 | 12,3 s | 21,3 s |

- **Die drei falschen Aktionen bei Gemma 4 E4B** sind Websuchen statt einer Antwort: „How high is the Zugspitze?“ öffnet den Browser. Harmlos, aber ungefragt.
- **Phi-4-mini** nutzt kaum Werkzeuge: 1/12 Aktionen.
- **FunctionGemma 270M** ist für Wissen unbrauchbar und bleibt auf der CPU oft über 120 s hängen (s7: 31%, R0: 38%; ein Lauf, also im Rauschen).

## Was die einzelnen Fixes bringen

Gemessen mit Gemma 4 E4B und Qwen 3.5 4B. Ein Lauf pro Stufe, s7 drei Läufe. Unterschiede von 1–2 Aufgaben zwischen zwei Stufen liegen im Rauschen. Aussagekräftig ist R0 → s7.

1. **s1, Übersetzungs-Skill** (`fix(translation)`):
   - „Stell einen Timer auf fünf Minuten“ ergab „Ich kenne die Sprache fünf Minuten nicht“. Ebenso „Erzähl mir in zwei Sätzen …“.
   - Der Skill gibt jetzt ab, wenn das erfasste Wort keine Sprache ist.
   - +2 bis +3 Aufgaben. Ohne LLM ändert sich nur die Fehlermeldung.
2. **s2, Temperatur 0,7 → 0,2:** kein messbarer Effekt. Bleibt drin, weil Tool-Aufrufe reproduzierbar sein sollen.
3. **s3, Leerlauf-Reset und s4, Lazy-Schema:** im Benchmark nicht messbar, weil jede Episode frisch startet.
   - Der Reset verhindert, dass die Konversation über `maxNumTokens = 4096` wächst.
   - Das Lazy-Schema verhindert, dass die Reflection beim App-Start die Skills verzögert. Mit dieser Verzögerung landete die erste Eingabe im Platzhalter-Fallback.
4. **s5, Werkzeuge `sendMessage`, `navigateTo`, `openSettingsPanel`, plus 6 Fixes aus einem Code-Review:**
   - Fehlgeschlagene Runden werden aus dem Verlauf entfernt.
   - Der Verlauf ist auf 6 Runden begrenzt.
   - `null`-Inhalte und -Argumente werden abgefangen.
   - Die letzte Werkzeugrunde läuft ohne Werkzeuge.
   - Ein leerer Modellname wird nicht gesendet.
   - Wird die URL gelöscht, startet der Modell-Download.
   - Messbar: „Schreib Anna Berger eine SMS …“ geht jetzt.
5. **s6, strengeres Routing:**
   - Die unscharfe Sprachsuche fand „Kalenjin“ in „in den Kalender ein“ und „Keine Sprachinhalte (zxx)“ in „in einfachen Worten“.
   - Der Öffnen-Skill beanspruchte „Öffne die Webseite wikipedia.org“ und antwortete „Unbekannte App“.
   - Dazu das aktuelle Datum für das Modell: „morgen um 15 Uhr“ wurde vorher zu `startIso = "tomorrow…"`.
   - +4 Aufgaben.
6. **s7, Datum in der Nutzernachricht statt im System-Prompt:** gleiche Erfolgsquote.
   - In s6 änderte das Datum den 500-Token-Präfix jede Minute, und der Prompt-Cache griff nie. Das kostete +5,5 s pro Anfrage auf der CPU.
   - Gemma 4 E4B, Median pro Aufgabe: s6 28,8 s → s7 17,7 s.
   - Auf dem Telefon zählt das noch mehr.

Von R0 nach s6/s7 kamen hinzu: `timer_de`, `explain_de`, `about_city_de`, `open_url_de/en`, `sms_de`, bei Gemma `about_city_en`, bei Qwen `explain_en` und `zugspitze_de`. **Verloren ging keine Aufgabe.**

## Was noch scheitert (17 Aufgaben, in jedem Lauf bei allen drei Modellen)

| Ursache | Aufgaben | Wer müsste es lösen |
|---|---|---|
| Deutsche Such-Regel `was\|wer … ist .what.` (Spezifität low) fängt jede „Was ist …?“-Frage, DuckDuckGo verlangt dann ein Captcha | calc_de, calc2_de, capital_au_de, followup_de | Upstream: Rechner-Sätze ohne „was ist“; bei aktivem LLM die Such-Fangregel abschwächen? (Design-Entscheidung) |
| Übersetzungs-API lingva.ml ist tot, die Übersetzungs-Requests scheitern | translate_de/en, word_meaning_de, recipe_en | Upstream: anderer Übersetzungsdienst |
| Lyrics-Skill (EN) fängt „What is the capital of France?“ und „Text Anna Berger: …“ (das Wort „text“) | followup_en, sms_en | Upstream: Lyrics nur mit „song/lyrics/sing“ |
| Telefon-Skill fängt „Dial the number 0664 …“ und listet alle Kontakte | dial_en | Upstream |
| Kein Werkzeug zum Anlegen von Kontakten (die Modelle lehnen ehrlich ab) | add_contact_de/en | Phase 4 (GUI-Agent) oder ein Werkzeug `addContact` mit Bestätigung |
| Kontext-Loch: Antwortet in Runde 1 ein Skill, kennt das LLM in Runde 2 die Frage nicht („Wie viele Einwohner hat sie?“ → „Welche Stadt?“) | context_de/en | Architektur: Skill-Antworten in den LLM-Verlauf schreiben |
| Kalender: beide Modelle rufen `createCalendarEvent` korrekt auf (morgen 15:00 → `2026-11-03T15:00`), Google Calendar öffnet sich, der Editor ist aber nicht zu sehen (vermutlich der Erststart-Dialog im Emulator) | calendar_de/en | Harness: Calendar im Snapshot einmal öffnen. Noch nicht verifiziert |

Ohne diese 17 lösen Qwen und Gemma 4 E2B die restlichen 47 Aufgaben in praktisch jedem Lauf.

## Offene Entscheidungen für dich bzw. die Maintainer

1. **http im Release-Build:**
   - Android blockiert Klartext-HTTP ab API 28. Ein Server unter `http://192.168…` geht nur mit einer Network-Security-Config oder über https.
   - Möglich wären: Klartext global erlauben, nur für private Adressen über Domains (das geht nur per Hostname, nicht per IP-Bereich), oder https verlangen, etwa über Tailscale HTTPS.
   - Im Debug-Build ist Klartext für den Benchmark erlaubt.
2. **Vorrang des LLM vor der Such-Fangregel** bei aktivem LLM-Fallback. Das LLM hat selbst ein `searchWeb`-Werkzeug. Eine Bevorzugung aller low-Skills würde aber den Telefon-Skill brechen.
3. **Skill-Antworten in den LLM-Verlauf** (Kontext-Loch).
4. **Logging und Datenschutz:**
   - `Log.d` schreibt Prompts und Werkzeug-Argumente auch im Release.
   - `sendMessage` gibt die aufgelöste Nummer an das Modell, also an den Server.
5. **Upstream-Bugs als eigene PRs:**
   - Übersetzung (s1, s6)
   - Öffnen (s6)
   - Lyrics-Fangregel
   - deutscher Rechner
   - lingva.ml

## Code

- **Dicio:** `~/Projects/dicio-android-eval`, Branch `eval/remote-engine`, 12 Commits auf deinem `feature/llm-fallback`. Tags `eval-r0`, `eval-s1` … `eval-s7` für die gemessenen Stände.
  - `d6014c80` eval: Debug-Receiver
  - `23ea46a4` RemoteLlmEngine
  - `97fddb1a` fix(translation)
  - `84d34c8a` Temperatur
  - `24b3c461` Leerlauf-Reset
  - `925951be` Werkzeuge
  - `175bd916` Einstellungen
  - `ca6de2ee` Lazy-Schema
  - `83c335a5` Review-Fixes
  - `0a4772c7` fix(translation, open)
  - `08ed05be` + `b7e8cc47` Datum
- **Harness:** android-eval-Worktree, Branch `android-eval-exp1`.
  - `dicio_eval.py`, `test_dicio_eval.py`, `tasks-dicio.json`
  - `dicio/` (setup, run, models, stages, report, make_tasks)
  - README-Abschnitt „Dicio (voice assistant) benchmark“
- **Ergebnisse:**
  - `results-dicio/`: R0 und Baselines
  - `results-dicio-s{1,2,5,6,7}/`
  - `results-dicio-r0/`: R0 dreifach
  - Diese Verzeichnisse sind gitignored. Die Tabellen hier sind mit `dicio/report.py` erzeugt.
- **Reproduzieren:**

  ```sh
  STAGES=s7 MODELS="gemma4-e2b" dicio/stages.sh
  python3 dicio/report.py results-dicio-s7 --tasks
  ```

## Einschränkungen

- Die Latenzen stammen von einer Desktop-CPU (i7-14700KF, 12 Threads) mit Q4_K_M. Auf dem Pixel 10 mit LiteRT-LM wird es anders aussehen; das misst Phase 3.
- Pro Stufe ein Lauf, nur s7 und R0 mehrfach. Der dritte R0-Lauf mit Qwen fehlt: Claude Code hat ihn bei 132/192 Episoden wegen Speichermangels am Rechner abgebrochen. Den Speicher belegten Ollama-Server anderer Sessions. Die Modelle wurden über llama.cpp geprüft, nicht über LiteRT-LM.
- Die On-Device-Engine (`RealLlmEngine`) bekam dieselben Prompt- und Robustheits-Änderungen. Sie lief im Benchmark aber nicht: Das 3,6-GB-Modell auf der Emulator-CPU wäre sehr langsam.
- Der Emulator stürzte immer wieder im GL-Renderer ab (`gfxstream`, llvmpipe). Die Läufe starten ihn neu und prüfen den Snapshot. Das kostete Zeit, nicht Daten: Abgestürzte Episoden werden wiederholt.
- Die CodeRabbit-CLI ist nicht angemeldet (`coderabbit auth login` ist interaktiv). Das Review kam stattdessen von einem unabhängigen Agenten.

## Nächste Schritte

1. Den Kalender-Snapshot reparieren und die Kalender-Aufgaben nachmessen.
2. **Phase 3:** die zwei, drei besten Modelle mit LiteRT-LM auf dem Pixel 10 (Latenz, RAM).
3. Upstream-PRs klein schneiden (siehe oben), vorher den Kommentar in #132 (Entwurf: `dicio/comment-132.md`).
4. **Phase 4:** GUI-Agent-Werkzeug `do_in_app` für Kategorie in_app.
