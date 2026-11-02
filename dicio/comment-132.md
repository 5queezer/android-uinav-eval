I've been working on an on-device LLM fallback for Dicio in my fork. To see whether it actually helps, I built a small benchmark that drives Dicio on an emulator. Here are the numbers, plus a question about how you'd like this split up.

**What the fallback does**
- When no skill matches, the fallback runs a small LLM with tool calls: timer, alarm, calendar event (the calendar app opens for confirmation), dial, open app or URL, web search, and composing a text message (Dicio only fills it in; the user presses send).
- No API keys and no Play Services:
  - On-device it uses [LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM) (Gemma 4 E2B/E4B and others, downloaded on first use).
  - Optionally it can use any OpenAI-compatible server the user runs themselves, e.g. Ollama or llama.cpp at home.

**How I measured it**
- 64 utterances, half German and half English, across Dicio's own skills, LLM-only actions, general knowledge, safety cases and two-turn conversations.
- Each one is sent to a debug build on an emulator. Success is checked from device state (alarm set, timer running, call log, foreground app) or from the reply.
- Any side effect the task doesn't allow counts as a failure.
- Models: Q4_K_M via llama.cpp. Each episode starts from a fresh snapshot.

| | success |
|---|---|
| current main (text fallback) | 33% |
| LLM fallback, first version (2–3 runs) | 61–63% |
| LLM fallback + the fixes below (3 runs) | **72–73%** |

- Gemma 4 E2B, Gemma 4 E4B and Qwen 3.5 4B score the same.
- Gemma 4 E2B is the fastest of the three, which makes it a sensible default for 8 GB phones.
- No task that worked before broke.
- Phi-4-mini rarely calls tools. FunctionGemma 270M can't answer knowledge questions.

**Most remaining failures are in the skills, not the LLM.** These fixes help with or without an LLM:
- **Translation:** the German "… auf/in <language>" sentences match "Stell einen Timer auf fünf Minuten" ("Ich kenne die Sprache fünf Minuten nicht") and "Trag das in den Kalender ein" (the language lookup is fuzzy enough to find "Kalenjin"). My fix makes the skill step back when the captured word isn't actually a language name.
- **Open:** "open the website wikipedia.org" answers "unknown app". The skill now steps back when no installed app matches.
- **Lyrics (en):** it catches "What is the capital of France?" and "Text Anna Berger: I'll be late".
- **Search (de):** the low-specificity `was|wer … ist .what.` catches every "Was ist …?", including "Was ist fünf mal vier?", which the German calculator sentences don't cover. DuckDuckGo then answers with a captcha.
- **Translation API:** lingva.ml no longer responds, so translation requests fail.

**Question:** would you be interested in this as a few small PRs rather than one big one?
1. The skill routing fixes above (independent of any LLM).
2. A fallback-mode setting (text / LLM). This overlaps with #370, and I'm happy to align with that.
3. The LLM engine interface with the LiteRT-LM implementation, plus the optional OpenAI-compatible server.
4. The tools.

**Two design questions where I'd like your opinion:**
- Release builds block plain `http` (API 28+), so a home server on `http://192.168…` won't work unless cleartext is allowed or the server uses https. What would you prefer?
- When the LLM fallback is enabled, should it take precedence over catch-all low-specificity matches like the search sentence above? The LLM has its own web-search tool.

The code is on the [`eval/remote-engine`](https://github.com/5queezer/dicio-android/tree/eval/remote-engine) branch of my fork. The benchmark harness is separate and I can share it too.
