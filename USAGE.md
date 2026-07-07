# USAGE.md — Cost, Tokens & Scaling Guide

## Your Actual Baseline (Measured)

From your first video generation run (C++ Lesson 1):

| Metric | Value |
|---|---|
| Total API calls | ~300 |
| Cost (Gemini 2.5 Flash, thinking ON) | ₹30–40 |
| Cost after fix (thinking OFF) | ~₹0.5–1.5 |
| Video duration | ~13–14 minutes |
| Script words | ~1800–2100 |

> **Why so expensive first time?** `gemini-2.5-flash` has thinking mode ON by default.  
> Thinking tokens are billed at **$3.50/1M** vs **$0.30/1M** for regular output — ~12× more expensive.  
> This is now fixed. Thinking is permanently disabled (`thinking_budget=0`).

---

## API Call Breakdown Per Video

### One-time (course setup only)

| Step | Calls | Type |
|---|---|---|
| PDF ingest (300-page book → ~800 chunks) | ~550 | Embedding |
| Curriculum generation (100 lessons) | ~1 LLM + ~15 | LLM + Embedding |
| **One-time total** | **~566** | — |

### Per video (100 lessons × this)

| Agent | LLM Calls | Embedding Calls | Notes |
|---|---|---|---|
| LessonPlannerAgent | 1 | 6 | RAG + plan |
| ScriptAgent | 1 | 12 | RAG + script |
| CodeAgent | 1–3 | 0 | 1 per code example |
| SlideAgent | 1 | 0 | All slides in one call |
| VoiceAgent | 0 | 0 | Edge-TTS, free |
| QAAgent | 1 | 0 | |
| SEOAgent | 1 | 0 | |
| **Per video total** | **~7–9 LLM** | **~18–20 Embed** | |

---

## Token Estimates Per Video

### LLM Token Usage (Gemini 2.5 Flash, no thinking)

| Agent | Input tokens | Output tokens |
|---|---|---|
| LessonPlannerAgent | ~1,800 | ~700 |
| ScriptAgent | ~4,500 | ~3,500 |
| CodeAgent (×2 examples) | ~3,000 | ~1,600 |
| SlideAgent | ~3,500 | ~2,200 |
| QAAgent | ~1,200 | ~400 |
| SEOAgent | ~1,500 | ~900 |
| **Total per video** | **~15,500 in** | **~9,300 out** |

### Embedding Token Usage (Gemini Embedding-001)

~200 tokens × 18 calls = ~3,600 tokens per video  
(well within free tier: 1,500 requests/day)

---

## Cost Calculation — 100 Lesson C++ Course

### Gemini 2.5 Flash Pricing (no thinking)

| | Rate | Per Video | 100 Videos |
|---|---|---|---|
| Input tokens | $0.075 / 1M | $0.00116 | $0.116 |
| Output tokens | $0.30 / 1M | $0.00279 | $0.279 |
| **Total LLM** | | **~$0.004** | **~$0.40** |
| Embeddings | Free tier | $0 | $0 |
| Edge-TTS | Free | $0 | $0 |
| Playwright/FFmpeg | Free (local) | $0 | $0 |
| **TOTAL** | | **~$0.004** | **~$0.40** |

**₹ equivalent: ~₹0.33 per video → ~₹33 for 100 videos**  
*(exchange rate: 1 USD = 84 INR)*

### Upper Bound (worst case: retries, long scripts, 3 code examples)

| | Per Video | 100 Videos |
|---|---|---|
| LLM (2× estimate for retries) | ~$0.008 | ~$0.80 |
| **Upper bound total** | **~₹0.7/video** | **~₹67 total** |

---

## Free Tier Limits

| Service | Free Limit | Sustained Rate | Notes |
|---|---|---|---|
| Gemini 2.5 Flash | 500 req/day | ~250K TPM | More than enough for 1–2 videos/day |
| Gemini Embedding | 1,500 req/day | — | Enough for ~75 videos/day |
| Edge-TTS | Unlimited | — | Microsoft's free neural TTS |

**At 1 video/day:** Entirely within free tier. Cost = ₹0.  
**At 5 videos/day:** Still within free tier. Cost = ₹0.  
**At 50 videos/day:** Hits paid tier. Cost = ~₹17/day.

---

## Time Estimates

| Phase | Time per Video |
|---|---|
| LLM pipeline (lesson plan + script + slides) | 3–5 min |
| Audio synthesis (24 segments, Edge-TTS) | 2–3 min |
| Slide rendering (12 slides, Playwright) | 1–2 min |
| Video encoding (FFmpeg) | 1–2 min |
| **Total wall-clock time** | **~8–12 min** |

For 100 videos running sequentially: **~14–20 hours**  
(Run overnight in batches of 10–15 per session)

---

## Scaling to Multiple Courses

| Courses | Books ingested | Total videos | Estimated cost |
|---|---|---|---|
| 1 (C++) | 1 | 100 | ~₹33–67 |
| 5 (C, C++, Python, Java, DSA) | 5 | 500 | ~₹165–335 |
| 20 (full curriculum) | 20 | 2,000 | ~₹660–1,340 |

Each new book ingest is a one-time cost of ~550 embedding calls = effectively free.

---

## How to Reduce Cost Further

1. **Reduce script length**: Set `TARGET_DURATION_MINUTES=8` → saves ~30% script tokens
2. **Fewer code examples**: Limit `CodeAgent` to 1 example per lesson → saves ~1,500 tokens
3. **Skip QA on first run**: Remove `qa_check` from pipeline → saves 1 LLM call per video
4. **Cache lesson plans**: Save `lesson_plan.json` and reuse → saves 1 LLM call if regenerating

---

## Quick Reference

```
1 video   ≈  ₹0.33 – ₹0.70    (₹0.50 typical)
10 videos ≈  ₹3.3  – ₹7       (₹5 typical)
100 videos ≈ ₹33   – ₹67      (₹40 typical)
500 videos ≈ ₹165  – ₹335     (₹200 typical)
```

> All prices assume **thinking mode disabled** (already configured) and **Gemini 2.5 Flash**.  
> If you upgrade to ElevenLabs for voice: add ~$0.30/video ($30 per 100 videos).
