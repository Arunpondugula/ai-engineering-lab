# Interview Sheet

How to use: answer each question out loud **before** opening the answer. The answers are written the way you'd say them in an interview: a direct answer first, then the reasoning, then an example. Don't memorize them word for word. Read one, close it, and say it back in your own words.

Levels: 🟢 basic · 🟡 common · 🔴 deeper follow-up

---
<details>
 <summary><b> Day 1 · Setup, LLM calls, cost guards</b> </summary>

<br>

### 1. 🟢 Where does an LLM sit in a production system?

<details><summary>Answer</summary>

The LLM is one dependency in the request path. My service calls it the same way it would call any external API, like a payment provider. It isn't the system itself.

Around that call, my code does all the work that makes it safe and useful. Before the call, it authenticates the user, checks their quota, builds the prompt, and retrieves relevant data to give the model context. After the call, it validates the output, runs guardrails, logs tokens and cost, and returns the result.

The key point is that the model never talks to the database or the user directly. It only produces text, or asks my code to run a tool, and my code decides what actually happens. That boundary is where I put security, validation and cost control.

</details>

### 2. 🟢 What is a token? Why do providers bill by tokens instead of requests?

<details><summary>Answer</summary>

A token is the unit of text a model reads and writes. It's roughly three quarters of an English word, so a short sentence might be 10 to 15 tokens.

Providers bill by tokens because that's what actually costs them compute. The model does work for every token it reads and every token it generates. Request count doesn't capture that: one request might be a 20-token question, and another might carry 50,000 tokens of chat history and retrieved documents. Billing per request would make the small requests subsidize the big ones.

That has a practical consequence for me as the engineer. I think about cost, rate limits and quotas in tokens, not requests.

</details>

### 3. 🟡 Why are output tokens priced higher than input tokens?

<details><summary>Answer</summary>

Because they're much more expensive to produce. The model reads the whole input in one parallel pass, but it generates output one token at a time, and each new token needs a full step through the model that depends on everything before it. That sequential work can't be parallelized, so output costs more compute per token.

I saw this in my own measurements. On a model priced at $0.30 per million input tokens and $2.50 per million output tokens, output was 84% of the tokens in a call but about 98% of the cost. So when I want to cut cost, the first lever is shorter outputs: a `max_tokens` cap and prompts that ask for concise answers.

</details>

### 4. 🟡 What does `max_tokens` do, and what happens when it's hit?

<details><summary>Answer</summary>

`max_tokens` is a hard cap on how many output tokens the model can generate. It's the only reliable length control I have. Asking for "300 words" in the prompt is just a suggestion; when I tested it, "300 words" gave 365 tokens and "800 words" gave over 1,100.

When the cap is hit, the model stops mid-answer. The response still comes back successfully, but `finish_reason` is set to `length` instead of `stop`. With a cap of 10, I got back a cut-off answer of 6 tokens.

So in code I always check `finish_reason`. A truncated answer is incomplete, and if I asked for JSON, it's probably invalid JSON too. Depending on the use case, I either retry with a higher cap or treat it as an error. I set `max_tokens` on every call anyway, because it protects both latency and cost.

</details>

### 5. 🟡 What is `finish_reason` and why should you log it?

<details><summary>Answer</summary>

`finish_reason` tells me why the model stopped generating. `stop` means it finished naturally. `length` means it hit `max_tokens`. Depending on the provider there are others, such as a safety filter or the model deciding to call a tool.

I log it on every call because it catches problems that don't throw errors. If 10% of my calls end with `length`, then 10% of users are getting cut-off answers, and nothing in my error dashboard would show it. It's also useful when debugging parsing failures: a lot of "the model returned bad JSON" issues turn out to be truncation.

</details>

### 6. 🟡 How do you stop an LLM feature from creating a surprise bill?

<details><summary>Answer</summary>

I put limits at several layers, because any single one can fail.

At the account level, I set a spending cap with the model provider and billing alerts on the cloud account, so I hear about a problem before it gets big. At the call level, every request has a `max_tokens` cap and every agent has a step limit, so one runaway call or loop can't run forever. At the user level, I enforce quotas in tokens or dollars per user, so one user, or one attacker, can't burn the budget.

Then I make cost visible: I log tokens and cost for every call, so I can see cost per request and per user. And I avoid paying for waste: retries are capped, a cheap model is used during development, and responses are cached where possible.

</details>

### 7. 🔴 Follow-up: you shipped the feature and cost per day doubled overnight. How do you investigate?

<details><summary>Answer</summary>

First I'd split the problem: did the number of calls go up, or did the cost per call go up? Since I log tokens and cost per call, that's one query.

If the number of calls went up, I'd look at who's making them. It could be real traffic growth, but it could also be a retry loop, a Kafka consumer stuck reprocessing the same messages, or a single user abusing the endpoint. Grouping by user, endpoint and request ID usually shows it quickly.

If cost per call went up, I'd look at tokens per call. Common causes are a prompt change that made the prompt longer, retrieval pulling in more context, chat history growing without being trimmed, or someone switching to a more expensive model. Grouping by prompt version and model name usually pinpoints the change.

Then I'd fix the cause and add a guard so it can't happen again, such as an alert on cost per request or a quota.

</details>

---
</details>

---

<details>
<summary> <b>Day 2 · System design for AI apps </b> </summary>

### Request path

### 8. 🟢 Walk me through what happens when a user hits your LLM endpoint.

<details><summary>Answer</summary>

The request comes through the load balancer, and the first steps are normal backend work: authenticate the user from their JWT, then check their quota, measured in tokens or dollars rather than request count.

Next I build the prompt: the instructions plus the user's question. If the feature answers from our own data, I retrieve the relevant documents, for example with a vector search in Postgres, and include them in the prompt. That's RAG.

Then I call the model. That call is slow, so it's async, with a timeout, retries with backoff and a `max_tokens` cap.

When the response comes back, I don't trust it yet. I validate its format against a schema, check citations if there are any, and run guardrails for things like leaked personal data. I log tokens, cost and latency for the call. Finally, I stream the answer back to the user as it's generated, over server-sent events, so they see progress instead of a spinner.

</details>

### 9. 🟡 How is an LLM request path different from a normal CRUD request path?

<details><summary>Answer</summary>

A CRUD request is fast, cheap and predictable: around tens of milliseconds, essentially free per request, and the same input always gives the same output.

An LLM call breaks all of that, in four ways. It's slow, taking seconds rather than milliseconds. It costs money on every call. It's unpredictable, because the same input can give a different answer, and sometimes a wrong one. And it can be fooled, because users can put instructions in their text that try to override mine.

Every design difference follows from those four. Because it's slow, I stream and use async. Because it costs money, I cache, cap tokens and limit retries. Because it's unpredictable, I validate output and test with evals instead of exact matches. Because it can be fooled, I enforce permissions in code, never in the prompt.

</details>

### Latency

### 10. 🟢 What is latency vs throughput?

<details><summary>Answer</summary>

Latency is how long one request takes, from sending it to getting the response. Throughput is how many requests, or tokens, the system can handle per second.

They're related but independent. A batch pipeline that processes millions of Kafka messages a day has high throughput, but each individual message might wait minutes, so its latency is high. A chat feature needs low latency for each user, even if total traffic is small.

For LLM systems I usually care about both: latency for the user who's waiting, and throughput because the provider's rate limits cap how many tokens per minute I can push through.

</details>

### 11. 🟡 What is TTFT, and how does total latency break down?

<details><summary>Answer</summary>

TTFT is time to first token: how long I wait after sending the request before the first piece of the answer arrives. During that time the model is processing my prompt, and on shared infrastructure the request might also be waiting in a queue.

After the first token, the model generates the rest one at a time. So total latency is roughly TTFT plus the number of output tokens times the time per token.

That breakdown tells me where to optimize. Long answers mean the generation part dominates, so I cut output length or use a faster model. If TTFT dominates, it's a large prompt or queueing. It also explains why streaming feels so much better: the user starts reading after TTFT instead of waiting for the whole answer.

</details>

### 12. 🟡 Why report p95/p99 instead of average latency?

<details><summary>Answer</summary>

Because the average hides the slow requests, and those are the ones users complain about.

Say nine requests take a few hundred milliseconds and one takes five seconds. The average comes out under a second, which describes nobody. p50, the median, tells me what a typical user sees. p95 and p99 tell me how bad it gets for the slowest 5% or 1%.

At scale the tail matters a lot. With a million requests a day, a bad p99 means ten thousand slow experiences every day. LLM latency is especially noisy, since my own test runs varied from under one second to over ten for similar calls, so percentiles over many calls are the only honest way to report it.

</details>

### 13. 🔴 Your LLM endpoint has p50 = 1 s and p95 = 9 s. What's going on, and what do you do?

<details><summary>Answer</summary>

The typical request is fine, but about one in twenty takes nine seconds or more. A gap that big usually means a specific kind of request is slow, not the whole system.

I'd look at per-call logs for the slow requests and compare them with the fast ones. The usual suspects are long answers with many output tokens, cache misses where the fast requests are cache hits, retries after rate-limit errors where the user waits through the backoff, and requests that pull in a lot of retrieved context and make the prompt huge.

Once I know which it is, the fix follows. Long answers get a tighter `max_tokens` or a more concise prompt. Simple questions get routed to a smaller, faster model. Retries mean I'm hitting rate limits, so I smooth traffic or raise limits. Big context means trimming retrieval. And whatever the cause, I stream so the slow requests at least show progress.

</details>

### 14. 🔴 Streaming makes it feel faster. What actually reduces total latency?

<details><summary>Answer</summary>

Streaming only changes when the user sees the first words. The total time is the same. To actually reduce it, I have three main levers.

First, generate fewer output tokens. Output is produced one token at a time, so it's usually the biggest part of latency. I cap `max_tokens` and ask for concise answers.

Second, use a smaller, faster model for tasks that don't need a big one. Classification or simple questions often work fine on a small model, and small models generate tokens much faster.

Third, skip the call entirely. A cache hit returns instantly, and some questions can be answered without the model at all. Shortening the input helps a little too, since it reduces TTFT, but output length matters more.

</details>

### 15. 🔴 Follow-up: you measured a 1,186-token answer that returned faster than a 365-token answer. Explain.

<details><summary>Answer</summary>

That happened in my own tests. The 365-token answer took about 10 seconds, and the 1,186-token answer took about 7.

Total latency is TTFT plus generation time, and TTFT includes time spent waiting in the provider's queue. I was on a free tier, where that queue time can swing by several seconds from one call to the next. The model I used generates tokens fast, so the difference in generation time between the two answers was smaller than the difference in queue time.

The lesson is that a single latency measurement tells you almost nothing. I'd measure TTFT separately using streaming, run many calls, and report percentiles. Interestingly, cost behaved perfectly in the same test: three times the output tokens gave three times the cost. Cost I can calculate from tokens; latency I have to measure.

</details>

### Components

### 16. 🟡 Why use async for LLM calls?

<details><summary>Answer</summary>

Because an LLM call is almost entirely waiting. My service sends the request and then does nothing for several seconds while the model generates.

With a thread-per-request model, like a standard Spring MVC setup, that thread is blocked the whole time. If each request holds a thread for ten seconds and I have a pool of 200 threads, 200 concurrent users exhaust the pool and everyone else queues.

With async code, a thread starts the call and is freed to handle other work while it waits. When the response arrives, processing picks up where it left off. One thread can wait on many calls at once. In Java that's WebFlux or virtual threads; in Python it's `async def` with `await`.

</details>

### 17. 🟡 Streaming vs a queue: when do you use each?

<details><summary>Answer</summary>

They solve different problems.

Streaming is for when the user is waiting for the answer, like a chat or a Q&A feature. Instead of making them wait for the full response, I send tokens as they're generated over server-sent events, so they start reading within a second or two.

A queue is for when the user doesn't need to wait at all. Classifying a batch of complaints overnight or processing an uploaded document are examples. I put the job on Kafka, return a 202 Accepted right away, and process it in the background. That also absorbs bursts: if ten thousand jobs arrive at once, they wait in the topic instead of overwhelming the model provider.

So the question I ask is whether a person is waiting for this answer right now. If yes, stream it. If no, queue it.

</details>

### 18. 🟡 How do you rate limit an LLM feature? Why isn't requests/min enough?

<details><summary>Answer</summary>

Requests per minute isn't enough because requests vary wildly in size. One request might be a 20-token question, and another might carry a long chat history and pages of retrieved documents, a hundred times bigger. A limit of 100 requests per minute could mean almost no cost, or a lot.

It also doesn't match how providers limit me. Providers enforce tokens per minute, so I can stay well under my request limit and still get 429 errors.

So I limit per user by tokens or dollars, for example a daily token budget per user, on top of a basic request limit to stop abuse. Since I already log tokens per call, the quota check is a lookup against that.

</details>

### 19. 🟡 How do you cache LLM responses? What goes in the key?

<details><summary>Answer</summary>

Caching matters more for LLMs than for normal APIs, because every cache hit saves money as well as time. If a thousand users ask the same product question, one model call can serve all of them.

The important part is the cache key. It has to include everything that affects the answer: the model name, the prompt version and the user's input, hashed together. If I leave out the prompt version and then improve the prompt, the cache keeps serving answers generated by the old prompt, and users never see the change.

With the version in the key, a new prompt simply produces new keys, and the old entries stop matching and expire. There's nothing to clean up by hand. I'd also set a sensible TTL for answers that depend on data that changes.

</details>

### 20. 🔴 Follow-up: what's a semantic cache and what's the risk?

<details><summary>Answer</summary>

A normal cache only hits on an exact match. A semantic cache hits on a similar question: it converts the question into an embedding and returns a cached answer if a previous question is close enough. So "Is this blender loud?" and "Is this blender noisy?" can share an answer, which raises the hit rate a lot.

The risk is returning the right answer to the wrong question. "Is it loud?" and "Is it loud on the lowest setting?" are very similar as embeddings but need different answers. And this failure is silent, since the user just gets a confident wrong answer.

So I'd use a strict similarity threshold, keep it off for questions where small wording changes matter, and measure it: sample cache hits and check how often the cached answer was actually right for the new question.

</details>

### 21. 🟡 You process 10k complaints through Kafka with LLM calls. What's different from a normal consumer?

<details><summary>Answer</summary>

Two things change.

First, my throughput is decided by the model provider, not my servers. The provider limits tokens per minute, so adding more consumers doesn't help once I'm at that limit; it just produces more 429 errors. Consumers need to slow down when they hit rate limits, which is backpressure, and I size the consumer group around the provider's limit.

Second, retries cost money. In a normal consumer, a message that fails fifty times wastes some CPU. Here, every retry is a paid model call, and a complaint that always breaks the model can burn real money. So I cap retries at around three with backoff, and after that send the message to a dead-letter queue for a person to look at.

</details>

### Failure modes

### 22. 🟡 What can go wrong when calling an LLM API, and how do you handle each?

<details><summary>Answer</summary>

There are four main failures, and three of them are loud.

A 429 means I'm over my rate limit. I wait and retry with exponential backoff, and if the response includes a Retry-After header, I wait exactly that long.

A 5xx means the provider has a problem. I retry two or three times with backoff, and if it keeps failing, a circuit breaker stops sending requests and I fall back, either to another model or by requeuing the work for later.

The third is malformed or cut-off output: the model returns invalid JSON, misses a field, or hits `max_tokens` mid-answer. I validate every response against a schema, re-ask once or twice with the validation error, and then fail clearly.

The fourth is the dangerous one: a 200 OK with valid output that's simply wrong. No error is raised, so none of the above catches it. That needs evals and verification, which is a separate answer.

</details>

### 23. 🔴 The model returns valid JSON with a confident wrong answer. How do you find out?

<details><summary>Answer</summary>

You can only detect a wrong answer by comparing it to something you trust. Try/catch won't help, because nothing failed.

Before release, I use evals. I keep a golden set of inputs with known correct answers and run the system on it in CI, scoring the results. For complaint classification, the public complaint data already comes with real product labels, so I can measure accuracy against those. If a prompt or model change drops the score below a threshold, the build fails.

At runtime, I verify what I can. If the answer cites sources, I check that the cited documents exist and actually support the claim. If there's an independent way to check the output, like a rule checker that re-validates a generated schedule against labor rules, I run it on every result.

Guardrails don't solve this. They block unsafe content like personal data or prompt injection. They can't tell whether an answer is true.

</details>

### 24. 🔴 Follow-up: your fallback model gives worse answers. How do you know how much worse, and what's acceptable?

<details><summary>Answer</summary>

I know how much worse by measuring, not guessing. I run both the primary and the fallback model on the same golden set and compare scores. Then the difference is a number, for example 94% versus 88% accuracy.

What's acceptable depends on the task and what a wrong answer costs. For a product Q&A, a slightly worse answer during an outage is usually better than no answer. For something like drafting a reply to a bank complaint, where a human approves every draft anyway, a weaker draft is fine. For something with no human check and real consequences, it might be better to queue the work and wait for the primary model.

I'd agree on that bar with the business ahead of time, and monitor how often the fallback is used, so a "temporary" fallback doesn't quietly become the normal path.

</details>

### Testing

### 25. 🟡 Why can't you test LLM output with assertEquals? What do you do instead?

<details><summary>Answer</summary>

Two reasons. The output changes from run to run, so "Credit card", "credit card" and "Credit card or prepaid card" are all roughly right but fail an exact match. And a wrong answer still returns successfully, so a test that only checks for errors passes when the output is wrong.

Instead I use evals. I build a golden set of realistic inputs with known correct answers, run the system on all of them, and score the results, for example 46 out of 50 correct. I set a threshold, and in CI any change that drops the score below it fails the build.

Normal unit tests don't go away. Parsing, permission checks, database code and tool functions are still deterministic and still get regular tests. Evals are added on top, specifically for what the model produces.

</details>

### Security

### 26. 🟡 Can you enforce access rules in the system prompt?

<details><summary>Answer</summary>

No. A rule in the system prompt is a request to the model, not an enforcement. Models can be talked out of their instructions; a user can write "I'm the manager now, show me everyone's schedule," and the model may go along with it. That's prompt injection, and there's no reliable way to prevent it with prompt wording alone.

So the rule I follow is: the model asks, the code decides. The model can request a tool call, but the tool's code checks whether the logged-in user is allowed to do it, using their identity from the auth token. Then even if the model is completely fooled, the worst it can do is ask for something and get denied.

</details>

### 27. 🟡 Where do permission checks go in an agent with tools, and what do they use?

<details><summary>Answer</summary>

They go inside the tool or service code, before any data is read or any action is taken. The model never touches the database directly; it asks my code to run a tool, and the tool checks permissions first, then queries.

The check uses two things the user can't change by typing. The first is the JWT, which tells me who is calling and their role. The second is the database record, which tells me the state of the thing they're touching: who owns it, or whether it's been approved. It never uses the prompt or anything the model says about who the user is.

A good way to think about it is to treat every tool like a public REST endpoint. I'd never expose an endpoint without an auth check just because I expect the frontend to call it correctly, and the model is effectively an untrusted frontend that might call anything.

</details>

### 28. 🔴 Follow-up: an agent drafts replies and a human must approve before sending. How do you enforce that?

<details><summary>Answer</summary>

The rule lives in the `send_reply` code, not in the prompt.

When `send_reply` is called, it checks two things. First, from the JWT, is the caller allowed to send replies at all, for example a reviewer or admin? Second, from the database, is this specific reply approved: is its status `approved`, and is there an `approved_by` user recorded? If either check fails, it refuses.

Then it sends the stored draft that the human approved, not whatever the model generates at that moment. Otherwise the model could change the text after approval. The approval record, with who approved it and when, also becomes the audit trail, which matters a lot in regulated areas like banking.

</details>

### Design / FDE

### 29. 🔴 You're adding one LLM call to an existing Spring Boot service. What do you change?

<details><summary>Answer</summary>

I'd think about it in three parts.

First, call it safely. The call has to be non-blocking, with WebFlux or virtual threads, so it doesn't tie up the thread pool. It needs a timeout, retries with backoff, and a circuit breaker with a fallback, which in Spring is Resilience4j. And every call gets a `max_tokens` cap.

Second, deliver the result in a way that fits the use case. If a user is waiting, I stream the answer with server-sent events. If it's background work, I put it on Kafka and return a 202.

Third, keep it correct and affordable. I validate the output against a schema, keep any permission checks in code, cache with a key that includes the model and prompt version, and log tokens, cost and latency for every call. And I add evals to CI, so a change that makes the answers worse fails the build.

</details>

### 30. 🔴 A customer asks: "Can we just put ChatGPT in front of our database?" How do you respond?

<details><summary>Answer</summary>

I'd take the goal seriously but push back on the shape of it. Letting a model query the database directly means any user who can talk to it can potentially get to any data, because the model can be talked into things. And they'd have no control over cost, no audit trail, and no way to know when it's wrong.

So I'd start with questions. Who are the users? What do they actually need to ask? What data is sensitive? What does a correct answer look like, and what does a wrong one cost the business?

Then I'd propose a narrower first version. Instead of raw database access, the model gets a small set of tools, like "look up this customer's open complaints," and each tool checks the caller's permissions. Sensitive data is redacted before it reaches the model, every call is logged, and we build a golden set from their real questions so we can measure accuracy before launch. Once that works and the numbers are good, we expand it.

</details>

---
</details>

---

<details>
<summary><b>Day 3 · Python essentials</b> (type hints, dataclasses, generators, exceptions, context managers, modules, pytest)</summary>

<br>

## 1. Type hints

### 🟡 Q1. Does Python enforce type hints? If not, why write them?

<details>
<summary>Answer</summary>

**TL;DR:** No, Python ignores them at runtime. Static checkers enforce them in CI, and Pydantic/FastAPI enforce them on data at runtime.

A function annotated `x: int` will accept a string and run. Hints are enforced in two other places:

- **Static checkers** (mypy, pyright/Pylance) in the editor and CI. They fail the build on type mismatches, which gives a Python team much of the safety a compiler gives Java.
- **Runtime libraries** (Pydantic, FastAPI) read the hints and validate data passing through their models. That's how FastAPI returns a 422 for a bad request.

In production I annotate every function signature and class field, and skip obvious locals.

</details>

### 🟡 Q2. What's the difference between `Iterable` and `Iterator`? Which do you use where?

<details>
<summary>Answer</summary>

**TL;DR:** `Iterable` = anything you can loop over. `Iterator` = the thing that hands out items with `next()` and gets used up. Accept `Iterable`, return `Iterator`.

```
Iterable   → list, set, dict, file, generator
 └ Iterator  → file objects, generators (single use)
    └ Generator → made with yield
```

A function that loops over shifts takes `Iterable[Shift]`, so it works with a list *or* a generator. A generator function returns `Iterator[Shift]`. Rule: accept the loosest type you can handle, return the most specific one you produce. Same split as Java's `Iterable<T>` / `Iterator<T>`.

</details>

### 🔴 Q3. You wrote `def f(shifts: list[shifts])` by mistake and the code runs fine. Why, and how would it get caught?

<details>
<summary>Answer</summary>

**TL;DR:** Hints aren't checked at runtime, so Python doesn't care. Pylance or mypy in CI would flag it.

`shifts` is a variable, not a type. Since the runtime ignores hints, nothing breaks. This is exactly why the static checker belongs in CI: it catches the mistakes the runtime never will.

</details>

---

## 2. Dataclasses

### 🟡 Q4. What is a dataclass, and when would you use Pydantic instead?

<details>
<summary>Answer</summary>

**TL;DR:** A dataclass removes boilerplate but does no validation. Pydantic at the edges, dataclasses inside.

`@dataclass` generates `__init__`, `__repr__` and `__eq__` from the annotated fields (like Lombok `@Data`). It doesn't validate or convert types: `Employee(emp_id=123, max_hours="forty")` is accepted.

- **Dataclass:** internal data my own code creates (shifts going into a solver).
- **Pydantic:** anything crossing a trust boundary — API requests, files, third-party APIs, **LLM output**. It validates, converts, and fails loudly.

</details>

### 🟡 Q5. What do `frozen=True` and `slots=True` do? When would you use them?

<details>
<summary>Answer</summary>

**TL;DR:** `frozen` = immutable and hashable (like a Java record). `slots` = less memory per object.

- `frozen=True`: assigning a field raises `FrozenInstanceError`. Instances can be dict keys or set members. Stops one component from mutating data another depends on.
- `slots=True`: fields go in fixed slots instead of a per-object `__dict__`. Matters with hundreds of thousands of objects, like review chunks in a RAG pipeline.

</details>

### 🟢 Q6. How do you validate fields in a dataclass?

<details>
<summary>Answer</summary>

**TL;DR:** `__post_init__`, which runs right after the generated `__init__`.

Check invariants there and raise a custom exception, so an invalid object can never exist:

```python
def __post_init__(self) -> None:
    if self.end_hour <= self.start_hour:
        raise InvalidShiftError(f"end ({self.end_hour}) must be after start ({self.start_hour})")
```

Java equivalent: a record's compact constructor. Note it doesn't convert types — `"40"` stays a string — which is another reason outside data goes through Pydantic.

</details>

### 🟡 Q7. What's wrong with `def add_role(role, roles=[])`?

<details>
<summary>Answer</summary>

**TL;DR:** The default list is created once, at definition, and shared by every call.

```python
add_role("cashier")
add_role("stocker")   # ['cashier', 'stocker']  ← bug
```

Fix: default to `None` and create the list inside. Python gives no error here. In a dataclass, the same mistake (`roles: list[str] = []`) **is** caught with a `ValueError`, and the fix is `field(default_factory=list)`.

</details>

### 🟢 Q8. `e1 == e2` and `e1 is e2` for two dataclass instances with the same fields?

<details>
<summary>Answer</summary>

**TL;DR:** `==` is `True` (compares values), `is` is `False` (different objects).

`==` uses the generated `__eq__`, like Java's `.equals()`. `is` checks identity, like Java's `==`.

</details>

---

## 3. Comprehensions and generators

### 🟢 Q9. List comprehension vs generator expression?

<details>
<summary>Answer</summary>

**TL;DR:** `[ ]` builds everything now. `( )` builds nothing until asked, holds one item at a time, and can be used only once.

For a million numbers: list ≈ 8 MB, generator ≈ 200 bytes. Loop over a generator twice and the second pass is empty — `sum` returns 0 with no error.

</details>

### 🟡 Q10. You need to count "Mortgage" complaints in a 500,000-line file. List or generator?

<details>
<summary>Answer</summary>

**TL;DR:** Generator. It's a single pass, so memory stays flat no matter how big the file is.

```python
count = sum(1 for c in read_complaints(path) if c["product"] == "Mortgage")
```

A list loads all 500k into memory just to produce one number. Use a list only when you need the data again, need `len()`, or need indexing.

</details>

### 🟢 Q11. What does this print, and in what order?

```python
def nums():
    print("start")
    yield 1
    print("middle")
    yield 2

g = nums()
print("created")
print(next(g))
print(next(g))
```

<details>
<summary>Answer</summary>

**TL;DR:** `created`, `start`, `1`, `middle`, `2`.

Calling a generator function runs **none** of its body. It starts at the first `next()`, runs to the first `yield`, and pauses. Each `next()` resumes from where it paused.

</details>

### 🔴 Q12. Total hours per employee from 50,000 shifts — how do you write it, and why not a comprehension per employee?

<details>
<summary>Answer</summary>

**TL;DR:** One pass with a running total: `totals[emp] = totals.get(emp, 0) + hours`.

```python
totals: dict[str, int] = {}
for shift in shifts:
    totals[shift.emp_id] = totals.get(shift.emp_id, 0) + shift.hours
```

- `.get(key, 0)` only reads: current value, or 0. Nothing is written. (Java: `getOrDefault` / `merge(..., Integer::sum)`.)
- A comprehension per employee is O(employees × shifts), and **breaks on a generator input**, because the generator is used up after the first employee.
- The single pass is O(shifts) and works with streamed data like `read_shifts`.

</details>

### 🟢 Q13. Why does `print(gen)` show `<generator object ...>`?

<details>
<summary>Answer</summary>

**TL;DR:** It's lazy and hasn't produced anything yet.

To see items: loop with `for`, call `next(gen)`, or `list(gen)` for small data.

</details>

---

## 4. Exceptions

### 🟡 Q14. How do you handle errors well in Python?

<details>
<summary>Answer</summary>

**TL;DR:** Catch the specific error you can handle, keep `try` small, chain with `from e`, never swallow.

- Catch the most specific exception type.
- Keep `try` blocks small, so you know which step failed.
- `raise DomainError(...) from e` keeps the original traceback.
- Custom exceptions let callers catch *your* problem specifically.
- Never `except: pass`. A bare `except` once hid a typo in my own code and reported every line as a data error.

</details>

### 🟡 Q15. An LLM API returns a 429 once and a 400 once. Which do you retry?

<details>
<summary>Answer</summary>

**TL;DR:** Retry the 429 with exponential backoff. Never retry the 400.

- **429** = rate limited. The request is fine, you're too fast. Temporary. Back off (0.5s, 1s, 2s…) and respect `Retry-After`.
- **400** = the request is invalid. It fails the same way every time. Retrying wastes money and rate limit.

</details>

### 🔴 Q16. What's wrong with this?

```python
try:
    response = call_llm(prompt)
    data = parse(response)
    save(data)
except Exception:
    pass
```

<details>
<summary>Answer</summary>

**TL;DR:** It silently hides every failure, and the big `try` hides which step failed.

A timeout, garbage output, or a database outage all disappear. Nothing is saved, nothing is logged, nobody knows until a customer complains. Fix: narrow the `try` to the LLM call, catch only retryable errors, log, and re-raise so the caller or retry layer decides.

</details>

### 🟢 Q17. Predict the output of `run("5")` and `run("abc")`.

```python
def run(text: str) -> None:
    try:
        n = int(text)
    except ValueError:
        print("bad")
    else:
        print("good", n)
    finally:
        print("done")
```

<details>
<summary>Answer</summary>

**TL;DR:** `"5"` → `good 5`, `done`. `"abc"` → `bad`, `done`.

`else` runs only when no error happened. `finally` always runs. Java has no `else` equivalent.

</details>

---

## 5. Context managers

### 🟡 Q18. What is a context manager and why use one?

<details>
<summary>Answer</summary>

**TL;DR:** It guarantees setup at the start of a `with` block and cleanup at the end, even if the block raises.

Files, DB connections, HTTP clients and locks must be released. A missed `close()` in a long-running service eventually exhausts file handles or connections. Libraries ship their own (`open()`, `httpx.Client`). I write one only when I have a setup/cleanup pair nothing else handles — like timing a block for latency logs — using `@contextmanager` with `try/finally` around a single `yield`. Java: try-with-resources.

</details>

### 🔴 Q19. Why does this crash?

```python
def read_lines(path: str):
    with open(path, encoding="utf-8") as f:
        return (line.strip() for line in f)

for line in read_lines("data.csv"):
    print(line)
```

<details>
<summary>Answer</summary>

**TL;DR:** The file closes before the first line is read.

1. `read_lines` is called **once**. The generator is created, but reads nothing.
2. `return` leaves the `with` → file closes.
3. The loop asks for the first line → `ValueError: I/O operation on closed file`. Zero lines read.

Fix: `yield` inside the `with` (lazy, file stays open until the last line), or return a `[ ]` list (eager, reads everything while open).

</details>

### 🔴 Q20. In a `@contextmanager`, why do you need `try/finally` around `yield`?

<details>
<summary>Answer</summary>

**TL;DR:** If the `with` block raises, the error is thrown back in at the `yield`. Without `finally`, cleanup never runs.

```
start → block runs → block raises → finally (cleanup) → error continues to the caller
```

</details>

### 🟢 Q21. Why always pass `encoding="utf-8"` to `open()`?

<details>
<summary>Answer</summary>

**TL;DR:** Windows defaults to a legacy encoding (cp1252), not UTF-8.

Real text with emoji or accents then crashes with `UnicodeDecodeError` or comes out garbled. Passing the encoding makes the code behave the same everywhere.

</details>

---

## 6. Modules and packages

### 🟡 Q22. How does Python find a module on import?

<details>
<summary>Answer</summary>

**TL;DR:** It searches `sys.path` in order: script's folder → PYTHONPATH → stdlib → installed packages. First match wins.

That's why a file named `dataclasses.py` breaks `from dataclasses import dataclass` — your file is found first. It does **not** search parent folders. Real projects use a package layout installed with `uv`, so imports work from anywhere. `sys.path` is Python's classpath.

</details>

### 🟢 Q23. What does `if __name__ == "__main__":` do?

<details>
<summary>Answer</summary>

**TL;DR:** Runs a block only when the file is executed directly, not when it's imported.

Importing a module runs all its top-level code. Without the guard, importing a file to reuse one function also runs its demo or test code. Java equivalent: `public static void main`.

</details>

### 🔴 Q24. A module connects to Postgres on its first line. Your test imports one helper from it. What goes wrong?

<details>
<summary>Answer</summary>

**TL;DR:** The import runs the connection, so the test fails or hits a real DB before it even starts.

No DB in CI → the test errors on import. A real DB → every test run connects to it. Fix: move the connection into a function or a dependency, so importing has no side effects. Java analogy: a `static {}` block that opens a connection at class load.

</details>

### 🟢 Q25. Why `Path(__file__).parent / "data.csv"` instead of `"days/day03/data.csv"`?

<details>
<summary>Answer</summary>

**TL;DR:** Relative paths depend on where you run the command from. `__file__` is where the script lives.

Run from another folder and the relative path breaks with `FileNotFoundError`. Building from `__file__` works anywhere — important for CI and evals.

</details>

---

## 7. pytest

### 🟡 Q26. How do you test that code raises, and why not try/except?

<details>
<summary>Answer</summary>

**TL;DR:** `with pytest.raises(MyError, match="key phrase"):`. A try/except test passes even when nothing is raised.

`pytest.raises` **fails** the test if the exception doesn't happen. Match a key phrase, not the whole message, and remember `match` is a regex (watch `(` `)` `.`).

</details>

### 🟡 Q27. What are parametrize and fixtures?

<details>
<summary>Answer</summary>

**TL;DR:** Parametrize = run one test per set of inputs. Fixture = setup a test requests by naming it as a parameter.

- `@pytest.mark.parametrize(("hours", "expected"), [(39, []), (40, []), (41, ["E1"])])` — pytest calls the test once per tuple, reported separately. Ideal for boundaries, where off-by-one bugs hide. JUnit: `@ParameterizedTest`.
- `tmp_path` is a built-in fixture: a fresh temp folder per test, for testing file code without touching real files. JUnit: `@TempDir`.

</details>

### 🟡 Q28. Why shouldn't unit tests call a real LLM API?

<details>
<summary>Answer</summary>

**TL;DR:** Cost, speed, network failures, and non-deterministic output.

The same prompt can return different text, so exact-output tests are flaky. Mock the call in unit tests. Measure LLM quality with evals on a golden set instead.

</details>

### 🔴 Q29. All your tests are green. Is the code correct?

<details>
<summary>Answer</summary>

**TL;DR:** No — only the cases I wrote passed. I check the test count against what I meant to cover.

On this project, one boundary case was missing, so a whole validation rule (hours above 24) was untested while everything looked green. Green is only as good as the cases behind it.

</details>

---

## Quick-fire (answer in one line each)

1. Two kinds of tools that check type hints?
2. Fix for a mutable default in a dataclass?
3. `sum(gen)` twice — second result?
4. `.get("E1", 0)` when E1 = 9 — what's returned, and is anything written?
5. Which HTTP error do you retry, 429 or 400?
6. What keeps the original traceback when re-raising?
7. When does `finally` run?
8. `return` vs `yield` inside a `with` — which keeps the file open?
9. Why did `dataclasses.py` break imports?
10. `pytest.raises` keyword for checking the message?

<details>
<summary>Answers</summary>

1. Static checkers (mypy/pyright) and runtime validators (Pydantic/FastAPI)
2. `field(default_factory=list)`
3. `0`, no error
4. `9`; nothing is written
5. 429
6. `raise ... from e`
7. Always — success, error, or return
8. `yield`
9. Script's folder is searched before the stdlib
10. `match=` (not `matches=`)

</details>

---

</details>
