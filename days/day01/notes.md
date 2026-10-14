# Day 1: Setup, LLM API call, system map
Date: 2026-10-14

## Goal
Set up the dev environment and repos, make a first LLM API call that logs tokens, latency and cost, and understand where an LLM sits in a real system.

## What I built
- Five GitHub repos: `ai-engineering-lab` plus one per project (ShelfSense, ShiftWise, ComplaintOps, LedgerGuard).
- `ai-engineering-lab` set up as a uv project on Python 3.12.
- `days/day01/hello_llm.py`: calls Gemini 3.5 Flash-Lite (free tier) through the OpenAI SDK and logs one JSON line per call.

---

## Concepts learned

### 1. Where the LLM sits in a system
- The LLM is an external API that my app service calls over HTTPS, the same as any third-party service (like SAP).
- Compared with a database call, it is about 100–1,000x slower (seconds, not milliseconds), costs money on every call, and can give a different or wrong answer each time.
- We add it anyway because it can do what a database can't: understand a plain-language question and write one readable answer from a lot of raw data.


### 2. The RAG request flow
```
User → App → Database (search for relevant reviews) → App
     → LLM (instructions + question + those reviews) → App → User
```
- The app coordinates every step. The database never talks to the LLM directly.
- Only the top few relevant results go to the LLM, never everything (too slow, too costly, input size limit).
- "Answer using only these reviews" keeps the model grounded in my data.


### 3. Tokens and cost
- A token is roughly 3/4 of a word. Providers bill per million tokens, with separate input and output prices.
- `cost = (input_tokens × input_price + output_tokens × output_price) / 1,000,000`
- Output tokens cost more per token (8x more for Gemini 3.5 Flash-Lite).
- Input = instructions + question + retrieved data. The biggest input saving comes from sending fewer, shorter results.


### 4. `max_tokens`
- Caps **output** tokens only. Input is billed in full no matter what.
- Example: 10,000-token prompt with `max_tokens=150` → I pay for 10,000 input + 150 output.
- If the cap is hit, the answer is cut off and `finish_reason` is `"length"`.


### 5. Where the token count comes from
- The provider counts tokens and returns them in `response.usage` (`prompt_tokens`, `completion_tokens`, `total_tokens`). My code reads them; it never counts them.
- These are the numbers the provider bills from.


### 6. Protecting every external call
- `timeout=30.0` so a call never hangs forever; `max_retries=2` for brief failures.
- Specific `except` blocks first (auth, bad request, rate limit, network), then `APIStatusError` as a catch-all last. Python uses the first match.
- Credits running out or the free-tier limit → HTTP 429 → `RateLimitError`. No tokens generated, no charge.


### 7. Logging
- One JSON object per line (structured logging): searchable in log tools, loadable with `pd.read_json(..., lines=True)`.
- Fields: `ts` (UTC), `request_id`, `model`, `status`, tokens, `latency_ms`, `cost_usd`, `finish_reason`.
- Log metadata on every call. Full prompt and answer text can contain PII: log it in dev, redact or sample it in production.
- Root logger at WARNING, my logger at INFO, so library loggers stay quiet (same as Logback root=WARN, my package=INFO).


### 8. Config and secrets
- `.env` holds the real key and is never committed. `.env.example` lists the variable names with blank secrets and is committed.
- `load_dotenv()` must run before any `os.getenv()` call.
- Secrets never get a default; fail fast if missing. Settings that affect cost or behavior (model name) should also be required.
- If a key is ever pushed: revoke it first, create a new one, check usage. Deleting the commit is not enough, because Git history keeps it.
- `git check-ignore -v .env` proves Git actually ignores the file.


### 9. uv
| Node | Java | Python (uv) |
|---|---|---|
| package.json | pom.xml | pyproject.toml |
| package-lock.json | pinned versions | uv.lock |
| node_modules/ | .m2 | .venv/ |
| npm install | mvn install | uv sync |
- `uv add` picks the latest compatible version once and freezes it in `uv.lock`. Versions only change with `uv lock --upgrade`.
- Commit `pyproject.toml` and `uv.lock`; never commit `.venv`.


### 10. Logging paid-tier cost on a free model
- Actual cost is $0, but I log what the call would cost on the paid tier. Project numbers like "$ per 1k queries" need real prices to mean anything.


---

## Experiments (Gemini 3.5 Flash-Lite, prices $0.30 / $2.50 per 1M tokens)

| Run | Input | Output | Latency | Cost (paid equiv.) | finish_reason |
|---|---|---|---|---|---|
| Short prompt | 12 | 63 | 6,452 ms | $0.000161 | stop |
| Prompt ~3x longer | 38 | 102 | 1,173 ms | $0.000266 | stop |
| `max_tokens=10` | 38 | 6 | 713 ms | $0.000026 | length |

**What I noticed**
- Output was 84% of the tokens in run 1 but 98% of the cost. Output length is the bigger cost lever.
- A longer prompt raised input tokens in proportion, and asking for more also raised output.
- Latency varied from 6.5 s to 0.7 s across calls. One call tells you nothing; measure many and report p95.
- With `max_tokens=10`, the answer was cut off ("Retrieval-Augmented Generation") and only 6 output tokens were reported.

---

## Bugs I hit and how I fixed them
1. **`model is not specified` (400).** `MODEL = os.getenv(...)` ran at file load, before `load_dotenv()` inside `main()`. Fix: call `load_dotenv()` right after the imports. The old default value had been hiding this bug.
2. **Model no longer available (404).** `gemini-2.5-flash-lite` is closed to new users. Fix: switched to `gemini-3.5-flash-lite` and updated the prices. Also added `APIStatusError` as a catch-all so unknown API errors don't crash with a stack trace.
3. **`HTTP Request: POST ...` line in the output.** A library logger was logging at INFO. Fix: root logger at WARNING, my logger at INFO.

---

## Open questions
- With `max_tokens=10`, only 6 output tokens were reported. Are hidden thinking tokens using the budget but not showing in `completion_tokens`? If so, my cost log undercounts. Check by printing the full `response.usage`.
- A cut-off answer is logged as `"status": "success"`. In production, `finish_reason == "length"` should be flagged.

---

## Interview answers
**Q: Your LLM call takes 6 seconds. How do you make it feel faster without changing the model?**
A: Stream the response so the first words show in under a second, and track time to first token as the latency users actually feel. Show progress steps like “searching” for the parts before the model starts. Cache repeated questions so they skip the LLM call entirely.

**Q: How do you know what an LLM call costs?**
A: The provider returns input and output token counts in the response. I multiply each by its price per million tokens and log the result with every call, along with latency, model and a request ID.

**Q: What does `max_tokens` protect, and what doesn't it protect?**
A: It caps output tokens, so it limits output cost and stops runaway answers. It does nothing for input: the full prompt is billed regardless.