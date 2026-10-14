"""Day 1: call an LLM once and log tokens, latency and cost.
 
Run:  uv run day01/hello_llm.py
Needs in .env: LLM_API_KEY, LLM_BASE_URL (blank for OpenAI), DEV_MODEL
Install: uv add openai python-dotenv
"""

import json
import logging
import os
import sys
import time
import uuid

from datetime import datetime, timezone 
from dotenv import load_dotenv
load_dotenv()  # reads .env into environment variables
from openai import(
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    BadRequestError,
    RateLimitError,
    APIStatusError,
)

# --- Config -----------------------------------------------------------------
# Fill these from the provider's Models and Pricing pages. Note the date you checked.
# On a free tier you pay $0, but use the PAID price here anyway: the log then shows what
# this call would cost in production, which is the number you'll report in your projects.
MODEL = os.getenv("DEV_MODEL")

# Gemini 2.5 Flash-Lite, paid tier, standard, text. Source: ai.google.dev/gemini-api/docs/pricing
PRICE_INPUT_PER_M = 0.30   # $ per 1M input tokens   (checked: 2026-10-14)
PRICE_OUTPUT_PER_M = 2.50  # $ per 1M output tokens  (checked: 2026-10-14)

# One JSON object per line: easy to search, easy to load into Pandas later.
logging.basicConfig(level=logging.WARNING, format="%(message)s")
log = logging.getLogger("hello_llm")
log.setLevel(logging.INFO)


def cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * PRICE_INPUT_PER_M + output_tokens * PRICE_OUTPUT_PER_M) / 1_000_000


def main() -> None:

    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")  # None = OpenAI; set it to use Gemini or another provider
    if not api_key:
        sys.exit("LLM_API_KEY is missing. Add it to .env (never commit .env).")
    if not MODEL:
        sys.exit("DEV_MODEL is missing. Add it to .env.")
    if PRICE_INPUT_PER_M is None or PRICE_OUTPUT_PER_M is None:
        sys.exit("Fill PRICE_INPUT_PER_M and PRICE_OUTPUT_PER_M from the pricing page first.")
 
    # timeout: never wait forever. max_retries: SDK retries transient errors with backoff.
    # Same OpenAI SDK for any OpenAI-compatible provider: only base_url and key change.
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0, max_retries=2)
 
    request_id = str(uuid.uuid4())  # correlation ID, like a trace ID in your Java services
    prompt = "In two sentences, what is retrieval-augmented generation? Explain it to a Java backend engineer, compare it to calling a database then a service, and give one real-world example."

    start = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,  # caps output tokens, which caps the cost of this call
        )
    except AuthenticationError:
        sys.exit("Auth failed: check the API key.")
    except BadRequestError as e:
        sys.exit(f"Bad request (check model name and parameters): {e}")
    except RateLimitError as e:
        # Also raised when prepaid credits run out (insufficient quota).
        sys.exit(f"Rate limited or out of credits: {e}")
    except (APITimeoutError, APIConnectionError) as e:
        sys.exit(f"Network or timeout error after retries: {e}")
    except (APITimeoutError, APIConnectionError) as e:
        sys.exit(f"Network or timeout error after retries: {e}")
    except APIStatusError as e:                      # new: catches 404, 500, and anything else
        sys.exit(f"API error {e.status_code}: {e.message}")
    latency_ms = round((time.perf_counter() - start) * 1000)

    # The provider counts tokens and returns them in `usage`. You don't count them yourself.
    usage = response.usage
    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens
 
    log.info(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "model": response.model,  # the exact model version that served the call
        "status": "success",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": usage.total_tokens,
        "latency_ms": latency_ms,
        "cost_usd": round(cost_usd(input_tokens, output_tokens), 6),
        "finish_reason": response.choices[0].finish_reason,  # "length" = hit max_tokens
    }))
 
    print("\nAnswer:\n" + response.choices[0].message.content)

if __name__ == "__main__":
    main()