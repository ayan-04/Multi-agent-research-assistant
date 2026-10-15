# Interview questions

Answers describe this repository as it is. If a feature is absent, the answer says it is not built. Personal stories are marked `[FILL IN]`. No latency, accuracy, or cost figure is given, because those were not measured. The eval runner has not been executed.

## 30-second pitch

This is a command-line research assistant. You pass a topic. Plain Python plans a few sub-questions, searches DuckDuckGo, fetches pages with httpx, and keeps a finding only when the quote is actually on the page. Chunks go into Chroma with the source URL. A writer drafts a report from retrieved chunks, and a critic can send it back once, with a hard cap of two critiques. Defaults target the Gemini free tier: Flash, a disk cache, and integer caps on LLM calls, searches, fetches, and embed batches. Unit tests mock the model and the network. I have not run the live eval harness, so I will not quote a quality score.

## 2-minute walkthrough script

"The entry point is `python -m src.cli`. `main` in `src/cli.py` loads `Settings` from the environment, then `build_runtime` wires one budget, a disk cache, a Gemini backend behind `LLMClient`, DuckDuckGo, an httpx fetcher, and a new Chroma collection named `run_` plus a random id.

`run_research` is a hand-written loop, not a model that picks tools. It calls `create_plan`, which asks the model for a `ResearchPlan` and then overwrites the topic with the user's string. For each sub-question, `research` searches, fetches, chunks at 800 characters with 120 overlap, and stores vectors we computed ourselves. Extraction returns a `FindingBatch`. `_supported` drops any quote that is not a substring of the fetched page.

`write_report` calls `retrieve_for_report`, one query built from the topic and the questions, top 4 chunks, and asks for a `Report`. `critique_report` does the same against a `Critique`. If the critic rejects the draft, `revise_report` runs once and the critic runs a second time. After that we stop even if the critic is still unhappy. The CLI prints markdown. `--out` writes that same string. `--approve-outline` is the only human gate, and it is off by default.

Reliability is `Budget`, exponential backoff on transient Gemini errors, one JSON repair, and a step guard. Pages are wrapped as untrusted data. What I have not done is a live scored eval: `evals/run_evals.py` would write `data/eval_results.json`, and that file does not exist."

## Project overview and motivation

### 1. What does this project do?

- Difficulty: basic
- Answer: Given a topic, it plans sub-questions, searches and fetches pages, stores chunks, and prints a cited markdown report. The critic can force one rewrite. Entry points are `src/cli.py` and `src/__main__.py`. The output shape is the `Report` model in `src/llm/schemas.py`, rendered by `report_to_markdown`.
- Follow-up: What does the CLI print when the critic still rejects the revised report?

### 2. What problem is it solving?

- Difficulty: basic
- Answer: A single model call will invent citations. This design puts search and fetch in Python, requires a quote to appear on the fetched page before a `Finding` is kept (`researcher._supported`), and shows the writer retrieved chunks instead of asking it to remember the web.
- Follow-up: Where is that quote rule not applied?

### 3. Who is the user?

- Difficulty: basic
- Answer: A person at a terminal who wants a short cited brief and can set `GEMINI_API_KEY`. There is no account system and no browser UI. The optional human step is `--approve-outline`.
- Follow-up: What happens if they press `n` at the outline prompt?

### 4. Why is it a portfolio project rather than a product?

- Difficulty: basic
- Answer: It is one synchronous process with local Chroma and a disk cache, built so the control flow in `run_research` can be explained line by line. There is no API, no queue, and no measured quality score. Those gaps are listed in `docs/SYSTEM_DESIGN.md`.
- Follow-up: What would you add first if this had to serve more than one person?

### 5. What did you decide not to build?

- Difficulty: intermediate
- Answer: No graph runtime, no browser UI, no tracer, no dollar ledger, no recall of past topics, and no second model that scores reports. The model does not choose tools. `DECISIONS.md` records the choices the code follows. Later checklist items that never landed are called out as not implemented in the system design doc.
- Follow-up: Which of those would change the interview story the most if you built it?

### 6. How do I run it?

- Difficulty: basic
- Answer: Install from `requirements.txt`, copy `.env.example` to `.env`, set the key, then `python -m src.cli "topic"`. Add `--approve-outline` or `--out path`. Tests are `python -m pytest`. The live eval command is `python -m evals.run_evals`, and it has not been run in this environment.
- Follow-up: What works with an empty `GEMINI_API_KEY`?

## LLM and agent fundamentals

### 7. What is an LLM in the context of this code?

- Difficulty: basic
- Answer: A text-in, text-out function. `GeminiBackend.generate` sends one prompt and returns `response.text`. The rest of the program interprets that string as JSON. The model does not search or fetch.
- Follow-up: Why is a new `genai.Client` constructed on every call?

### 8. What is a prompt here?

- Difficulty: basic
- Answer: A Python f-string from `src/llm/prompts.py`, plus the JSON Schema appended in `LLMClient.complete_model`. The schema is `schema.model_json_schema()` rendered by `schema_instruction`.
- Follow-up: Why is `UNTRUSTED_DATA_RULE` on the planner prompt too, where there is no page yet?

### 9. What is a context window, and do you measure it?

- Difficulty: intermediate
- Answer: It is the maximum text one call can see. This repo does not count tokens. It truncates extracted page text to `fetch_max_chars` (default 6000) in `truncate_text`, and it only puts `top_k` chunks (default 4) into the writer prompt via `retrieve_for_report`.
- Follow-up: What is lost when a page is truncated before extraction?

### 10. What is temperature set to, and why does that matter?

- Difficulty: intermediate
- Answer: `Settings.temperature` defaults to 0.2 and is passed as `GenerateContentConfig.temperature`. The env var is `GEMINI_TEMPERATURE`. Lower values make JSON shapes more stable. It does not make citations true. There is no measured comparison against another temperature.
- Follow-up: Where would a higher temperature show up as a bug in this design?

### 11. What is the difference between a model call and a step?

- Difficulty: intermediate
- Answer: A step is `StepGuard.tick` (`plan`, `search`, `fetch`, `extract`, `write`, `critique`, `revise`). An LLM call is `Budget.charge("llm")`, which also counts retries and the repair call. One extract step is one logical `complete_model`, which may be several charged attempts. Caps are `max_steps` (40) and `max_llm_calls` (12).
- Follow-up: Can you hit the LLM cap while steps remain?

### 12. Why a cheap Flash model by default?

- Difficulty: basic
- Answer: `gemini_model` defaults to `gemini-2.5-flash` so development stays on the free tier. `GEMINI_MODEL` overrides it without code changes. I have not measured quality differences against a larger model.
- Follow-up: What else in the client is provider-specific?

### 13. Is this multi-agent?

- Difficulty: intermediate
- Answer: It is four roles as plain functions: `create_plan`, `research`, `write_report` / `revise_report`, and `critique_report`. They do not talk to each other. `run_research` passes Pydantic objects between them. There is no separate model per role. They share one `LLMClient` and one `Settings.gemini_model`.
- Follow-up: What state is shared, and what is recomputed?

### 14. What would a ReAct loop have looked like, and why isn't this one?

- Difficulty: advanced
- Answer: ReAct would ask the model for the next action, run that tool, append the observation, and repeat until the model says it is done. Here the order is fixed in `run_research`. That makes the step cap and the fetch cap obvious, and it prevents the model from searching forever. The cost is that a bad first query is not followed by a reformulation. See `DECISIONS.md`.
- Follow-up: Where would you insert a single "search again" decision without giving the model an open tool loop?

## The agent loop

### 15. Walk through `run_research`.

- Difficulty: intermediate
- Answer: Tick plan, `create_plan`, slice to `max_subquestions`. Optional approver. `research` appends into a list the caller owns. `write_report`. Then a for-loop of length `critic_max_iterations` (clamped to 2): critique, break if approved, break if this was the last pass, else `revise_report`. Catch only `StepLimitError` and `BudgetExceededError`. Return a `ResearchRun`.
- Follow-up: Why is the findings list created in the loop and passed into `research`?

### 16. What does `StepGuard` actually prevent?

- Difficulty: basic
- Answer: It raises `StepLimitError` when `steps >= max_steps` before the next action. Default `max_steps` is 40, and `trimmed()` forces it to at least 1. It does not count LLM retries inside a step.
- Follow-up: With `max_steps=1`, which action runs and which does not? (See `tests/test_loop.py`.)

### 17. What are the `stopped_reason` values?

- Difficulty: basic
- Answer: `completed`, `outline_rejected`, `step_limit`, `budget`. They are set in `run_research` and stored on `ResearchRun`. Validation errors never set a reason. They raise.
- Follow-up: Which of these still have `report is None`?

### 18. Why is the outline auto-approved?

- Difficulty: basic
- Answer: `approve_outline` defaults to false so the CLI is scriptable. `--approve-outline` prints `render_outline` and `ask_user_to_approve` accepts empty, `y`, or `yes`. Rejection returns before `research`. Decision note in `DECISIONS.md`.
- Follow-up: What LLM calls have already happened when the user rejects the outline?

### 19. How many critic passes can run?

- Difficulty: intermediate
- Answer: `Settings.trimmed` sets `critic_max_iterations` to `max(1, min(value, 2))`. The loop revises only when `index < critic_max_iterations - 1`. So the maximum is two critiques and one revision. `tests/test_loop.py::test_critic_revision_is_capped_at_two_iterations` expects six backend calls for a full reject path with one sub-question: plan, extract, draft, critique, revise, critique.
- Follow-up: What does the CLI return code mean in that case?

### 20. What is incomplete when the budget trips mid-research?

- Difficulty: intermediate
- Answer: `stopped_reason` is `budget`. `plan` may be set. `findings` may hold earlier questions because they were appended in place. `report` is `None` if `write_report` did not finish. `cli.main` prints only `Stopped: budget` and returns 1. The findings are not rendered.
- Follow-up: Is an embed-budget failure distinguishable from an LLM-budget failure in the CLI output?

### 21. Why pass `budget` both on the client and into `run_research`?

- Difficulty: advanced
- Answer: `LLMClient` charges LLM calls on `self.budget`. Search, fetch, and embed charge their own objects. `build_runtime` uses one `Budget` instance for all of them. `run_research` reads counters from the argument, or from `llm.budget` if the argument is omitted. Tests sometimes share one budget so `llm_calls` on the `ResearchRun` matches the client.
- Follow-up: What bug would two separate `Budget` objects cause?

### 22. Is the loop safe to run twice in one process?

- Difficulty: advanced
- Answer: `build_runtime` creates a new collection name each call, so retrieval does not see the previous topic. The `Budget` and `DiskCache` are also new per `build_runtime`. Calling `run_research` twice on the same `Runtime` would share the cap and the collection. That is what `evals/run_evals.py` does across ten topics. It is a limitation, not a feature.
- Follow-up: What would you reset between eval topics?

## Tool calling and structured output

### 23. Do you use function calling?

- Difficulty: intermediate
- Answer: No. `LLMBackend.generate` returns a string. Gemini is configured with `response_mime_type="application/json"` only when `json_mode` is true. The tool order is Python. `SearchProvider.search` and `PageFetcher.fetch` are interfaces for fakes, not a schema sent to the model.
- Follow-up: What would you put in a tool schema if you added one tool?

### 24. Why JSON schema in the prompt plus Pydantic?

- Difficulty: intermediate
- Answer: `complete_model` works for `ScriptedBackend` and for Gemini without depending on provider-specific schema objects. Pydantic is the real validator (`model_validate`). The prompt schema can drift from the model if someone edits one and not the other, because the prompt uses `model_json_schema()` generated from the same class. That coupling is the point. Decision in `DECISIONS.md`.
- Follow-up: What does `parse_json_object` accept besides raw JSON?

### 25. What happens on the repair attempt?

- Difficulty: intermediate
- Answer: `validation_repairs` defaults to 1, so the loop in `complete_model` parses twice. The second prompt is `build_repair_prompt` with the original prompt, the bad text, and the exception string. Each generation charges the LLM budget and uses backoff. Success caches `json.dumps(obj.model_dump())`, not the raw model string. Failure raises `OutputValidationError` and does not cache.
- Follow-up: Why re-validate a cache hit with `model_validate`?

### 26. Which schema constraints are easy to violate?

- Difficulty: intermediate
- Answer: `ResearchPlan.sub_questions` must have length 1..4. `SubQuestion.question` min length 3. `Report.sections` min length 1. `Finding.quote` and `claim` min length 1. The planner prompt asks for exactly 3 questions, but the code also slices to `max_subquestions` after validation. A model that returns 4 valid questions is accepted and then sliced to 3 by default.
- Follow-up: Why does `create_plan` overwrite `topic`?

### 27. What is `complete_text` for?

- Difficulty: basic
- Answer: It caches and returns plain text with backoff. The research loop never calls it. Only `complete_model` is on the plan, extract, write, revise, and critique path.
- Follow-up: What bug would you cause by caching a failed validation?

### 28. How are search results turned into objects?

- Difficulty: basic
- Answer: `parse_hits` reads `href` or `url` or `link`, and `body` or `snippet`, and drops rows with no URL. `SearchHit` requires `url` min length 1. The cache stores `model_dump()` lists.
- Follow-up: Why are empty successful searches cached, but exceptions not?

### 29. What does a failed fetch look like to the researcher?

- Difficulty: basic
- Answer: A `FetchResult` with `ok` false. HTTP 4xx/5xx includes `status_code` and is cached. `httpx.HTTPError` has `status_code=None` and is not cached. Non-HTML and empty text are also not ok. `research` skips them. It does not raise.
- Follow-up: Why is a 404 cached?

### 30. Why can `OutputValidationError` kill the process?

- Difficulty: advanced
- Answer: `run_research` only catches `StepLimitError` and `BudgetExceededError`. A bad JSON reply after the repair escapes `main`. That is a gap. A finished design would map it to a `stopped_reason` and exit 1 without a traceback. It is not built that way today.
- Follow-up: Should a repair call be allowed to exceed `max_llm_calls`? What does the code do?

## RAG

### 31. Where does RAG happen, and where does it not?

- Difficulty: intermediate
- Answer: Indexing happens in `research` via `chunk_text` and `ChromaStore.add`. Retrieval happens in `writer._chunks` and `critique_report` through `retrieve_for_report`. The planner does not retrieve. The researcher does not retrieve. There is no branch that skips the web and reads an older collection.
- Follow-up: Why is retrieval one query string instead of one query per sub-question?

### 32. Why character chunks of 800 and overlap 120?

- Difficulty: intermediate
- Answer: `chunk_text` needs no tokenizer. Overlap keeps a sentence on the boundary inside a window. Both values are `CHUNK_SIZE` and `CHUNK_OVERLAP`. If overlap is greater than or equal to size, `chunk_text` reduces overlap to `size // 4` so the start index moves. No second setting was scored on real documents. `DECISIONS.md` says that explicitly.
- Follow-up: What does a short page become?

### 33. Why pass embeddings in instead of letting Chroma embed?

- Difficulty: intermediate
- Answer: `ChromaStore.add` calls `self._embedder.embed` and passes `embeddings=` to `upsert`. Tests use `HashingEmbedder` and never download a model. The Gemini path stays behind `Embedder`. Telemetry is turned off with `ANONYMIZED_TELEMETRY` and Chroma settings.
- Follow-up: What metadata is stored on every chunk, and what is not?

### 34. What is the hashing embedder good for?

- Difficulty: intermediate
- Answer: Deterministic offline vectors. Shared `[a-z0-9]+` tokens land in the same buckets, so related toy strings rank nearer in `tests/test_embeddings.py`. It is not a semantic model. `build_embedder` uses it only when `gemini_api_key` is empty. Live retrieval quality with Gemini embeddings has not been measured.
- Follow-up: Does the hashing embedder charge `max_embed_calls`?

### 35. How does a Gemini embed call interact with the budget?

- Difficulty: advanced
- Answer: `GeminiEmbedder.embed` charges one `embed` unit per batch call, then retries transient errors with the same backoff as the LLM client, charging again per attempt. `ChromaStore.add` embeds all chunks of one page as one batch. `query` embeds a single string as one batch. Default `max_embed_calls` is 40.
- Follow-up: What happens if the API returns a different number of vectors than texts?

### 36. Why a new Chroma collection every process?

- Difficulty: intermediate
- Answer: `build_runtime` uses `run_{uuid4 hex[:12]}` so this topic cannot retrieve another topic's pages. The directory is still `chroma_dir` (default `data/chroma`). Old collections are not deleted. Tests pass `persist_dir=None` and a unique collection because the ephemeral client is process-wide.
- Follow-up: What bug appears if two topics share a collection?

### 37. What does `distance` mean on `RetrievedChunk`?

- Difficulty: advanced
- Answer: It is the distance Chroma returns for the query embedding we supplied. The writer prompt does not include the distance. Nothing thresholds it. A far chunk can still enter the prompt if it is inside `top_k`.
- Follow-up: Would you filter on distance before calling the writer? What evidence would you need?

### 38. Is there reranking?

- Difficulty: basic
- Answer: No. `ChromaStore.query` returns the neighbours Chroma orders, sliced by `k`. There is no second model and no lexical reranker.
- Follow-up: What is `top_k` default, and where is it applied?

## Planner, researcher, writer, critic

### 39. What is the planner allowed to do?

- Difficulty: basic
- Answer: `build_plan_prompt` tells it to emit exactly three sub-questions a public page could answer, and not to answer the topic. The code then forces `topic` back to the user string and slices the list. It does not search.
- Follow-up: What if the model returns one question? Is that valid?

### 40. What is the researcher's contract?

- Difficulty: intermediate
- Answer: For each question, search `search_results_per_query` hits (default 2), fetch them, store chunks from successful pages, then extract a `FindingBatch`. Keep an item only if the URL was fetched for this question and `quote_in_text` matches. Set `sub_question` to the planner's question, not whatever the model wrote.
- Follow-up: Can one question produce zero findings while the run still completes?

### 41. Why check the quote in Python instead of trusting the critic?

- Difficulty: intermediate
- Answer: The critic is another LLM call and can be wrong. `_supported` is deterministic and cheap. It runs before the finding is stored on the `ResearchRun`. The critic still sees findings and chunks, but it is not the only gate. The report's own citation strings are not passed through this function.
- Follow-up: What false positive can a short quote create?

### 42. What does the writer see?

- Difficulty: intermediate
- Answer: `build_report_prompt` includes the topic, the sub-questions, JSON lines of findings, and fenced retrieved chunks. It tells the model to cite only URLs from that evidence and to admit thin evidence. The code does not delete a citation that violates that sentence.
- Follow-up: How does `revise_report` differ?

### 43. What does the critic see, and what can it change?

- Difficulty: intermediate
- Answer: `build_critique_prompt` includes the report JSON, findings, and chunks. The model returns `approved`, `issues`, and `unsupported_claims`. It does not edit the report. Only `revise_report` produces a new `Report`, and only when a revision is still allowed.
- Follow-up: If the second critique fails, which report is printed?

### 44. Why not one prompt for all four roles?

- Difficulty: intermediate
- Answer: Separate calls keep each JSON schema small and keep a failure in extraction from being the same call as the final prose. The trade-off is more LLM calls against a cap of 12. `DECISIONS.md` records the plain-function choice.
- Follow-up: Which calls are mandatory even when search returns nothing?

### 45. How does a finding's title get filled?

- Difficulty: basic
- Answer: The page title prefers `FetchResult.title`, then the search hit title, before extraction (`research`). `_supported` then uses `item.title or page.title`. The fetch parser reads the `<title>` tag after BeautifulSoup.
- Follow-up: What does `html_to_text` remove before the model sees the page?

### 46. What is deliberately not a role?

- Difficulty: advanced
- Answer: There is no router that chooses search versus retrieve, no citation-checker role in code, and no separate embed role the model can invoke. Indexing and retrieval are function calls inside the researcher, writer, and critic.
- Follow-up: If you added a citation checker, would it be another model call or a Python function? Why?

## Reliability and cost

### 47. How do you stay on a free tier without a price table?

- Difficulty: intermediate
- Answer: Integer caps in `Budget`, a disk cache that skips charges, a small default result count (2 hits, 3 questions, so 6 fetches), and a Flash model name. There is no token or dollar field anywhere. I cannot quote a cost per run.
- Follow-up: Which retries are charged, and which failures are free of a charge?

### 48. Explain the backoff numbers.

- Difficulty: basic
- Answer: `retry_base_seconds` is 0.5. The delay doubles after each transient failure. `max_retries` is 3, so the sleeps between attempts are 0.5s and 1s if the third try is the last. Tests inject a sleeper and do not wait. Search and fetch do not use this helper.
- Follow-up: Why is an empty Gemini body treated as transient?

### 49. What is considered transient?

- Difficulty: intermediate
- Answer: `is_transient_message` looks for substrings: `429`, `500`, `502`, `503`, `504`, `unavailable`, `resource_exhausted`, `rate limit`, `timeout`, `timed out`. A 400 or a schema error from the provider that does not match those strings is not retried.
- Follow-up: Why is matching on the exception string fragile?

### 50. What does the cache refuse to remember?

- Difficulty: intermediate
- Answer: LLM replies that fail validation. Search calls that raise. Fetches that never got a status code (timeouts and connection errors). It does remember HTTP error statuses and empty search lists. There is no TTL. The fetch key is the URL only, so it ignores a later `FETCH_MAX_CHARS` change.
- Follow-up: Why must cache hits skip `Budget.charge`?

### 51. How can the default caps still stop a healthy run?

- Difficulty: advanced
- Answer: Each retry and the repair call count as LLM calls. Three questions plus write plus two critiques plus one revise is already most of the 12. A couple of repairs can raise `BudgetExceededError` before the report exists. Embed retries count against 40, which is looser. I have not observed this on a live run. It follows from the counters.
- Follow-up: What does `trimmed()` do if someone sets `CRITIC_MAX_ITERATIONS=9`?

### 52. How are dead links and empty searches "graceful"?

- Difficulty: basic
- Answer: They are values, not exceptions. The researcher continues. The writer still runs, including with zero findings, and the prompt tells it to say the evidence is thin. Tests cover both. A search exception is logged and becomes `[]` so one bad query does not kill the process.
- Follow-up: What is the difference in caching between those two empty cases?

### 53. What is not retried?

- Difficulty: intermediate
- Answer: Non-transient LLM exceptions. `OutputValidationError` after the one repair. Fetch transport errors (the next loop iteration does not automatically refetch the same URL). Search exceptions (the function returns and does not try a second provider). There is only one search implementation.
- Follow-up: Why not retry a 404?

### 54. Does the eval runner respect the same budget?

- Difficulty: advanced
- Answer: It calls `build_runtime` once and passes that same `budget` into every `run_research`. Ten topics share 12 LLM calls by default. Later topics can stop with `budget` immediately. That behaviour is visible in `evals/run_evals.py`. It has not been executed, so I am describing the code, not a log.
- Follow-up: How would you keep evals cheap without sharing one cap across topics?

## Security

### 55. How do you treat web pages?

- Difficulty: intermediate
- Answer: As data. `fence_untrusted` wraps text and replaces the exact closing tag `</untrusted_web_content>`. Every prompt includes `UNTRUSTED_DATA_RULE`. Scripts are stripped in `html_to_text` so they do not become visible text. Findings must quote the page. This is not a proof against injection.
- Follow-up: What injection string would the fence miss?

### 56. What stops a hallucinated citation at extraction time?

- Difficulty: intermediate
- Answer: `_supported` requires the URL to be one of the pages just fetched for that question, and `quote_in_text` requires the quote, after case-fold and whitespace collapse, to be a substring. Otherwise the finding is logged and dropped. No new model call replaces it.
- Follow-up: Why doesn't the same function run on `Report.sections[].citations`?

### 57. Where is the API key, and where must it not go?

- Difficulty: basic
- Answer: `GEMINI_API_KEY` is read in `load_settings`. `.env` is gitignored. `.env.example` has an empty value. The key is passed to `genai.Client`. It is not part of the cache material. Prompts and page text are written under `data/cache` and `data/chroma`, which are gitignored and plaintext.
- Follow-up: What does `load_dotenv(..., override=False)` mean if the variable is already in the process?

### 58. What SSRF and download issues are unhandled?

- Difficulty: advanced
- Answer: `HttpxFetcher` requests the hit URL with `follow_redirects=True` and no host or scheme allowlist. A result can target a private address, or a public URL can redirect to one. The full body is read before `truncate_text`. There is no `Content-Length` limit. I would call those limitations, not mitigations. They are unhandled.
- Follow-up: Where would you put an allowlist without breaking normal web pages?

### 59. What is the user agent, and what policy is missing?

- Difficulty: basic
- Answer: `research-agent/0.1 (educational; local research assistant)` is set on the GET. There is no robots.txt check and no per-host rate limit. Search and fetch caps are per run, not per site.
- Follow-up: Why drop `script`, `style`, and `noscript`?

### 60. Can the critic be prompt-injected too?

- Difficulty: advanced
- Answer: Yes. Retrieved chunk text is fenced in `_evidence_block`, but the critic is still a model reading attacker-controlled text. Approval is whatever boolean the model emits. The deterministic quote check does not re-run on the report. A malicious page that is also a true substring can influence the critique.
- Follow-up: What test in `tests/test_researcher.py` locks the fence behaviour?

## Testing and evals

### 61. What do the unit tests prove?

- Difficulty: intermediate
- Answer: They prove the Python control flow against fakes: quote filtering, critic cap, budgets, cache rules, JSON repair, chunk edges, CLI flags, and that `topics.jsonl` has ten rows. `tests/conftest.py` says none of the fakes call Gemini, DuckDuckGo, or the network. Sleep is disabled.
- Follow-up: Which test shows a cache hit does not charge search twice?

### 62. What do they not prove?

- Difficulty: intermediate
- Answer: They do not prove that Gemini obeys the prompts, that DuckDuckGo's live JSON matches `parse_hits`, that real pages contain useful quotes after truncation, or that Gemini embeddings retrieve the right chunk. They do not produce an accuracy number.
- Follow-up: How is the Chroma client kept offline in tests?

### 63. What is in the eval set?

- Difficulty: basic
- Answer: Ten JSONL rows, `t01` through `t10`, in `evals/topics.jsonl`. Topics are short public-knowledge questions (vaccines, 2008 crisis, batteries, and so on). `tests/test_evals.py` asserts the file has between eight and ten rows. There is no expected answer key in the file, only `id`, `topic`, and `notes`.
- Follow-up: Why is there no gold citation in the topic file?

### 64. What does a result row mean?

- Difficulty: intermediate
- Answer: `FindingCheck` has `topic_id`, `url`, `url_resolves`, `quote_in_source`, `claim`, and `note`. `url_resolves` means `ok` and status in `[200, 400)`. `quote_in_source` is that plus `quote_in_text`. A topic with no findings becomes one row with `note="no findings"`. `main` adds `stopped_reason`. No aggregate metric is computed.
- Follow-up: Why does the checker fetch the URL again instead of reusing the run's page text?

### 65. Have you run the eval? What was the score?

- Difficulty: basic
- Answer: No. `python -m evals.run_evals` was not executed. `data/eval_results.json` is not in the tree. There is no accuracy, latency, failure rate, or cost figure. I will not invent one.
- Follow-up: What would you record so a later change can be compared, given the runner only writes one file?

### 66. Why not an LLM judge?

- Difficulty: intermediate
- Answer: It is not built. The harness is a deterministic URL and quote check only. A second model would spend more of the free tier and could share the report's biases. I would add it only after the deterministic file exists so I can see disagreements. That comparison has not been done.
- Follow-up: What bias would a judge model add that the substring check cannot?

## System design and scaling

### 67. Why is the design synchronous?

- Difficulty: intermediate
- Answer: One thread makes the budget and the step counter obvious, and tests do not need an event loop. The cost is latency equal to the sum of searches, fetches, and model calls. Parallel fetch is not implemented. `docs/SYSTEM_DESIGN.md` labels async workers as not implemented.
- Follow-up: Which stages are safe to parallelise, and which are not?

### 68. How would you add a queue? It is not built.

- Difficulty: advanced
- Answer: It is not built. I would enqueue a topic, have a worker call the existing `run_research`, and store the `ResearchRun` plus `stopped_reason`. The worker would own the `Budget`. The HTTP handler would not call Gemini inline. None of those types exist in `src/`.
- Follow-up: How would you dead-letter a `budget` stop versus a validation crash?

### 69. How would you scale the vector store? It is not built.

- Difficulty: advanced
- Answer: Today's store is a local Chroma directory and a throwaway collection. It is not a server. I would use a durable collection with metadata filters on the topic id, an explicit delete, and I would refuse the hashing embedder on that server. I have not operated Chroma beyond this process.
- Follow-up: Why is passing our own embeddings useful when you change stores?

### 70. How would rate limiting work across processes? It is not built.

- Difficulty: advanced
- Answer: `Budget` is in-memory and dies with the process. A second terminal gets a fresh cap and can double-spend the free tier. A shared limiter would sit in front of `GeminiBackend.generate` and `GeminiEmbedder.embed`, after the cache lookup. Not built.
- Follow-up: Why should the cache be checked before taking a rate-limit slot?

### 71. What would you trace? Tracing is not built.

- Difficulty: intermediate
- Answer: Nothing is written per call today except logs on skips and warnings. I would emit one JSON line per LLM, search, fetch, and embed attempt with cache hit, attempt index, and latency. I would not add a viewer until those lines exist. Token and dollar fields would wait until the SDK usage object is actually read. It is not read now.
- Follow-up: Why is `ResearchRun` missing `embed_calls`?

### 72. How does the CLI map to HTTP status codes? There is no API.

- Difficulty: intermediate
- Answer: There is no API. Today, report present means exit 0, even if the critic is unhappy. Report missing means exit 1. An uncaught `OutputValidationError` is a traceback. An API could map `completed` to 200, `outline_rejected` to 409, `budget` and `step_limit` to 429, and validation failure to 502. That mapping is a proposal, not code.
- Follow-up: Why is a rejected critique still exit 0?

## Python and code-level questions

### 73. Why Pydantic `BaseModel` for settings and for tool results?

- Difficulty: basic
- Answer: `Settings`, `SearchHit`, `FetchResult`, and the LLM schemas share one validation style. `FetchResult.model_validate_json` reloads the fetch cache. `trimmed()` uses `model_copy`. The code does not use dataclasses for those payloads. `Runtime` is a dataclass because it holds live objects, not JSON.
- Follow-up: What does `Field(min_length=1)` do that a plain `str` does not?

### 74. Why protocols instead of ABCs for the cache and the embedder?

- Difficulty: intermediate
- Answer: `Cache`, `Embedder`, `VectorStore`, and `LLMBackend` are `typing.Protocol`s. `SearchProvider` and `PageFetcher` are ordinary classes with methods that raise `NotImplementedError`. Fakes in tests do not inherit from them. They only need the same method. That is enough for the type checker style this repo uses. There is no runtime registry.
- Follow-up: What breaks if a fake's `search` signature drifts?

### 75. How is the disk cache path built?

- Difficulty: intermediate
- Answer: SHA-256 of the material UTF-8 bytes. Directory is `root / safe_namespace / digest[:2] / digest[2:]`. Namespace characters outside `[A-Za-z0-9_-]` become `_`. No extension. `tests/test_cache.py` checks the round trip.
- Follow-up: Why shard with the first two hex characters?

### 76. What does `quote_in_text` do to the string?

- Difficulty: basic
- Answer: `normalize_ws` splits on whitespace, joins with a single space, and case-folds. Empty quote or empty page returns false. It is a substring test, not a token overlap score. Used by the researcher and by `evals/checks.py`.
- Follow-up: Why can two different dash characters fail the check?

### 77. How does chunking guarantee progress?

- Difficulty: intermediate
- Answer: `step = size - overlap`. If `overlap >= size`, overlap is replaced with `size // 4` before that subtraction. The loop breaks when `start + size` covers the end. `tests/test_chunking.py` covers overlap larger than size.
- Follow-up: Why `strip()` each window?

### 78. How is JSON pulled out of a fenced reply?

- Difficulty: intermediate
- Answer: `parse_json_object` strips one leading ` ``` ` or ` ```json ` fence, cuts from the first `{` to the last `}`, and `json.loads`. The root must be an object. Prose with no brace raises `ValueError`. A leading array would fail the dict check.
- Follow-up: What is the risk of "first brace to last brace" if the page quote itself contains JSON? Does the quote sit inside the model reply or inside the prompt?

### 79. Why lazy-import `google.genai` and `chromadb`?

- Difficulty: intermediate
- Answer: `GeminiBackend.generate` and `GeminiEmbedder._embed_once` import the SDK inside the method so constructing the object does not need a key or a call. `ChromaStore.__init__` imports chromadb when a store is built. `HttpxFetcher._fetch_live` imports httpx at fetch time. Tests that never construct those paths still import the modules' pure functions.
- Follow-up: What error do you get if `google-genai` is missing at call time?

### 80. What is pinned, and what Python version?

- Difficulty: basic
- Answer: `requirements.txt` pins `google-genai`, `ddgs`, `httpx`, `beautifulsoup4`, `pydantic`, `python-dotenv`, `chromadb`, and `pytest` to the versions installed for this tree. `DECISIONS.md` records the local venv as CPython 3.13 via `py -3`, which satisfies the 3.11+ bar. There is no `pyproject.toml` and no lock beyond that file.
- Follow-up: Why pin `chromadb` exactly?

## Behavioural and honesty

### 81. This was built with an AI coding agent. How should I talk about that?

- Difficulty: basic
- Answer: "I directed Cursor, then reviewed, tested, and can explain every module." I chose the caps, the quote check, the critic limit, and the decision to keep a visible loop. I can open `src/agent/loop.py`, `src/llm/client.py`, and `src/tools/fetch.py` and walk them. I do not claim I typed every line from memory, and I do not claim a live quality score the harness never produced. `[FILL IN: what you personally changed after review, and one decision you rejected.]`
- Follow-up: Which module did you have to re-read before you trusted it?

### 82. What was the hardest bug?

- Difficulty: intermediate
- Answer skeleton: `[FILL IN: the symptom, the file, the wrong hypothesis, the actual cause, and the test you added.]` A true example that is already in the code, if it matches your memory: cache hits must not charge the budget, search exceptions must not be cached, and the critic must not request a third report. Point at `tests/test_search.py`, `tests/test_llm.py`, and `tests/test_loop.py` only for the case you actually hit.
- Follow-up: How did you prove the fix without calling Gemini?

### 83. What would you do differently?

- Difficulty: intermediate
- Answer skeleton: `[FILL IN: one design you would change and why.]` Honest candidates grounded in the code, pick the one you believe: catch `OutputValidationError` as a stop reason; give the eval runner a fresh budget per topic; check report citation URLs in Python the same way `_supported` checks quotes; add a download cap and a host check on `HttpxFetcher`. Do not claim you already did these.
- Follow-up: Which of those is a safety fix rather than a quality fix?

### 84. What is the weakest part of the project?

- Difficulty: advanced
- Answer: The live path is unmeasured, and the final report's citations are not mechanically checked. The critic is a prompt. Fetch will request whatever URL search returns, including after redirects, and will read the whole body. I would rather say that than invent an eval score.
- Follow-up: What would you measure first, and what would you refuse to measure until the deterministic file exists?

### 85. Tell me about a trade-off you accepted.

- Difficulty: intermediate
- Answer: Plan-then-execute instead of an open tool loop. I gave up follow-up searches so the fetch cap of 6 stays understandable. Character chunks instead of tokens. I gave up a tokenizer so the tests stay small, and I did not run a bakeoff. `[FILL IN: which trade-off you would defend first in the room.]`
- Follow-up: What did that choice make easier to test?

### 86. How do you handle "what was your accuracy?"

- Difficulty: basic
- Answer: I say the harness exists, the ten topics exist, the check is "status is successful and the quote is on the page," and the runner was not executed. No number. If I run it later, I will quote the file it writes, including failures.
- Follow-up: What would a high quote-on-page rate still fail to prove?

## What is not built, and how would you build it

### 87. A search-versus-retrieve decision is not built. How would you add it?

- Difficulty: advanced
- Answer: It is not built. The researcher always searches. I would add a Python check: if `store.count()` is already positive for this topic's collection and the query is a follow-up, call `query` before spending a search charge. I would not ask the model to choose until I had a test that shows it can waste the fetch budget. The collection today is empty at the start of every process on purpose.
- Follow-up: How would you stop that branch from reading another user's documents?

### 88. An HTTP API is not built. How would you add it?

- Difficulty: advanced
- Answer: It is not built. I would keep `run_research` as the core, put a worker in front of it, and return `ResearchRun` JSON. I would not call `GeminiBackend` on the request thread. Auth and per-key limits would wrap `build_runtime`. None of that is in the repo.
- Follow-up: What do you do with `--approve-outline` in an API?

### 89. Tracing is not built. How would you add it?

- Difficulty: intermediate
- Answer: It is not built. I would wrap `LLMClient._generate_with_backoff`, `DuckDuckGoSearch.search`, `HttpxFetcher.fetch`, and `GeminiEmbedder.embed` with a function that appends one JSON object: kind, cache hit, attempt, duration, and error type. I would not build a viewer in the same change. I would not write the API key or full page text into the line.
- Follow-up: Why log the error type and not the whole page?

### 90. Cross-run recall of sources is not built. How would you add it?

- Difficulty: advanced
- Answer: It is not built. Today each process gets a new collection and never reads an older one. I would add an explicit corpus id, store chunks under that id, and retrieve with a metadata filter. I would keep the quote check. I would not silently mix topics. Deletion of a corpus is also not implemented.
- Follow-up: What privacy issue does a shared corpus create that a per-run collection avoids?

### 91. A second-model judge is not built. How would you add it?

- Difficulty: intermediate
- Answer: It is not built. I would run it only after `data/eval_results.json` exists, on the same findings, and I would store both the deterministic booleans and the judge's label so I can see disagreements. I would charge it against a separate cap so it cannot eat the research budget. I have not done this, so I have no agreement rate to report.
- Follow-up: Why is the judge a worse source of truth than the substring check for "is the quote on the page"?

### 92. A download limit and SSRF guard are not built. How would you add them?

- Difficulty: advanced
- Answer: They are not built. Before `get`, I would allow only `http` and `https`, resolve the host, and reject private, loopback, and link-local addresses, and I would re-check redirects. I would stream the body and stop past a byte cap, instead of using `response.text` unbounded and then truncating. I would test this with a fake client, still without live calls.
- Follow-up: Why must the redirect target be checked again?

## Rapid-fire

### 93. Default model?

- Difficulty: basic
- Answer: `gemini-2.5-flash`, env `GEMINI_MODEL`.
- Follow-up: Default embed model?

### 94. Default embed model?

- Difficulty: basic
- Answer: `gemini-embedding-001`, and only if `GEMINI_API_KEY` is set. Otherwise `HashingEmbedder`.
- Follow-up: Embedding width of the hashing model?

### 95. Default LLM cap?

- Difficulty: basic
- Answer: 12. Cache hits do not count. Retries do.
- Follow-up: Default search and fetch caps?

### 96. Critic cap?

- Difficulty: basic
- Answer: 2, and `trimmed()` will not let configuration raise it.
- Follow-up: How many revisions is that?

### 97. Chunk settings?

- Difficulty: basic
- Answer: 800 characters, overlap 120, `top_k` 4.
- Follow-up: Where is overlap clamped?

### 98. Exit code when the outline is rejected?

- Difficulty: basic
- Answer: 1. The outline is printed. No search runs.
- Follow-up: Exit code when the critic is unhappy but a report exists?

### 99. Where is the report file written?

- Difficulty: basic
- Answer: Only if `--out` is passed. The directory is created. Encoding is UTF-8. The same bytes were printed to stdout.
- Follow-up: Does the loop write `ResearchRun` JSON anywhere? No.

### 100. What exception is not caught by the loop?

- Difficulty: intermediate
- Answer: `OutputValidationError`, and also a `TransientLLMError` that survives the last retry, and any non-transient provider error.
- Follow-up: What two exceptions are caught?

### 101. Name the cache namespaces.

- Difficulty: basic
- Answer: `llm`, `search`, and `fetch`.
- Follow-up: Which fetch results are absent from the cache?

### 102. Has the eval been run?

- Difficulty: basic
- Answer: No. No results file. No score.
- Follow-up: What command would run it, and why is it outside pytest?

## Personal blanks to fill before the interview

- `[FILL IN]` in question 81: what you changed after reviewing the agent's code, and one suggestion you rejected.
- `[FILL IN]` in question 82: the hardest bug you actually hit.
- `[FILL IN]` in question 83: the one change you would make first.
- `[FILL IN]` in question 85: which trade-off you want to defend out loud.
