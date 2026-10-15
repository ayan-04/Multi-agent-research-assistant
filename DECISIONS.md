# Decisions

Each entry is a choice made while building. The live Gemini, DuckDuckGo, and page-fetch paths were not called.

## Plain Python roles instead of an agent framework

Options considered: a graph of role nodes with shared state; a single ReAct loop in one prompt; plain functions for planner, researcher, writer, and critic called by a hand-written loop.

Choice: plain functions plus a step-limited loop.

Reason: the stack for this build is plain Python, and a visible loop makes the step cap and the two-iteration critic cap obvious.

## Gemini 2.5 Flash

Options considered: Gemini 2.5 Flash; a larger Gemini Pro model; an OpenAI mini model.

Choice: `gemini-2.5-flash`, overridable with `GEMINI_MODEL`.

Reason: it is the cheap Flash model on the free tier. The model name lives in config, not in the agent code.

## Official google-genai SDK behind a wrapper

Options considered: `google-genai`; the older `google-generativeai` package; raw HTTP to the Gemini REST API.

Choice: `google-genai`, called only from `GeminiBackend` and `GeminiEmbedder`.

Reason: it is the current official SDK. Tests inject a fake backend, so the SDK is imported and not called.

## DuckDuckGo through an interface

Options considered: DuckDuckGo via the `ddgs` package; Tavily; SerpAPI.

Choice: DuckDuckGo behind `SearchProvider` in `src/tools/search.py`.

Reason: it does not need an API key, which fits a $0 budget. Failures become an empty hit list and are not cached.

## Chroma with explicit embeddings

Options considered: Chroma; SQLite full-text only; an in-memory dict.

Choice: Chroma. Each chunk's metadata includes `source_url` and `title`. Embeddings are computed by our embedder and passed in, so Chroma's default ONNX model is not downloaded.

Reason: Chroma was the requested store, and explicit embeddings keep tests offline.

## Hashing embedder unless an API key is set

Options considered: Gemini embeddings for every run; Chroma's bundled neural embedder; a local hashing embedder.

Choice: `GeminiEmbedder` when `GEMINI_API_KEY` is set, otherwise `HashingEmbedder`.

Reason: tests and keyless runs must not call the network. Hashing is deterministic and ranks shared words closer together. It is not a semantic model. Live retrieval quality is unverified.

## JSON schema in the prompt plus Pydantic repair

Options considered: Gemini response schemas / tool calling; asking for JSON and validating with Pydantic; free-form text parsed with regex.

Choice: the prompt includes the Pydantic JSON Schema, the reply is parsed, and one repair call is allowed after a validation failure.

Reason: the same path works for the fake backend and for Gemini JSON mode. Repair is capped so a bad reply cannot loop.

## On-disk cache and exponential backoff

Options considered: no cache; an in-memory cache; a disk cache. For retries: fail immediately; fixed delay; exponential backoff.

Choice: SHA-256 files under `data/cache` for successful LLM, search, and completed fetch responses. Transient LLM errors sleep `0.5s`, then `1s`, then `2s`, up to 3 attempts. `time.sleep` is injectable so tests do not wait.

Reason: reruns should not spend the free-tier quota, and short rate-limit bursts should not fail the run. Search exceptions are not cached. Fetch timeouts are not cached.

## Budgets

Options considered: unlimited calls; a dollar cap that needs price tables; integer caps per run.

Choice: default caps of 12 LLM calls, 6 searches, 6 fetches, 40 embed calls, and 40 loop steps. Cache hits do not charge. Each retry does.

Reason: integer caps need no price list and stop a runaway loop on the free tier. Two search results and three sub-questions fit inside the fetch cap.

## Character chunks of 800 with overlap 120

Options considered: token chunks at 400 and 800; character windows of 500/50 and 800/120; one chunk per page.

Choice: 800 characters with 120 characters of overlap.

Reason: character windows need no tokenizer. The overlap keeps a sentence that sits on a boundary inside a chunk. Both values are config fields. No live chunk-size bakeoff was run.

## Outline approval off by default

Options considered: always stop for a human; never ask; ask only with a flag.

Choice: auto-approve the outline unless `--approve-outline` is set.

Reason: the default path is scriptable. The flag is the human gate.

## Critic revision cap of 2

Options considered: a single critique with no rewrite; unlimited rewrite until approval; a cap of 2 iterations.

Choice: at most two critic passes. A failed first pass allows one rewrite, then one more critique. The loop stops even if the second critique fails.

Reason: that matches the requested cap and bounds LLM calls.

## html.parser and truncated page text

Options considered: lxml; html.parser; trafilatura.

Choice: BeautifulSoup with the stdlib `html.parser`. Script, style, and noscript tags are dropped. Text is truncated to 6000 characters.

Reason: html.parser avoids a native parser build on Windows. Truncation keeps prompts inside the call budget. Non-HTML bodies and HTTP errors are failed fetches, not exceptions.

## Untrusted web text

Options considered: paste page text into the prompt; fence it and tell the model it is data; a separate sanitizer model.

Choice: every prompt states that fetched web text is untrusted data, never as instructions. Page text sits inside `<untrusted_web_content>` tags, and a closing tag in the page is escaped.

Reason: pages are data. A fence is a prompt-level defence, not a guarantee. Findings are kept only when the quote is a substring of the fetched page and the URL was actually fetched.

## Evaluation harness without a live run

Options considered: run the 10 topics now; write the harness and leave results empty; use an LLM judge.

Choice: 10 topics, a runner, and a deterministic check (HTTP success status and quote contained in the fetched text). The runner was not executed.

Reason: there is no API key, and live calls were out of scope. No scores were invented.

## Python 3.13 for the local environment

Options considered: the MSYS2 CPython 3.12 on `PATH`; the Windows `py` launcher, which has CPython 3.13.

Choice: create `.venv` with `py -3` (CPython 3.13).

Reason: 3.13 meets the 3.11+ requirement and installs the Chroma wheel. The MSYS build is a poor fit for those wheels.

## Dependency pins and secrets

Options considered: unpinned requirements; a lock written by the installer; committing `.env`.

Choice: pin the installed wheels in `requirements.txt`. Commit `.env.example` only. `.gitignore` covers `.env`, `.venv`, `__pycache__`, and `data/`.

Reason: a fresh environment should match the one the tests ran in, and the Gemini key must stay local.

## Interfaces, not a tool-calling loop

Options considered: let the model choose the next tool; hard-code the order in Python.

Choice: `LLMBackend`, `SearchProvider`, `PageFetcher`, `Embedder`, and `VectorStore` are interfaces. `run_research` always plans, then searches and fetches, then writes, then critiques. The model fills Pydantic objects. It does not pick tools.

Reason: the call order and the budgets stay visible in `src/agent/loop.py`.

## Staged checklist removed

The stage checklist, the empty progress log, and the empty `docs/decisions/` folder were removed after the code was audited. The choices above are the ones the code still follows. Later checklist items that are not in `src/` (a graph runtime, a browser UI, a trace viewer, a second-model judge, recall of past topics, a tool registry) are recorded as not implemented in `docs/SYSTEM_DESIGN.md`.
