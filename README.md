# CodeGuard AI

**An AI security analyst for Python code that checks its own work.**

Semgrep finds suspicious lines. Gemini decides which findings are real, looks for logic flaws that pattern-matching can't see, and writes fixes. **Every fix is re-scanned by Semgrep before it's shown.** It runs on free tiers, works as a CLI, web API, MCP tool and GitHub code-scanning integration, and comes with an evaluation that measures whether the AI actually helps.

[![CI](https://github.com/adityakumarprasad/CodeGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/adityakumarprasad/CodeGuard/actions/workflows/ci.yml)

---

## Table of contents
- [The problem](#the-problem)
- [How it works](#how-it-works)
- [Example output](#example-output)
- [Evaluation](#evaluation)
- [Free-tier engineering](#free-tier-engineering-handling-429s)
- [Security and hardening](#security-and-hardening)
- [Design decisions](#design-decisions)
- [Quick start](#quick-start)
- [Interfaces: CLI, web, MCP, SARIF](#interfaces)
- [Deployment](#deployment)
- [Observability with Langfuse](#observability-with-langfuse)
- [Testing](#testing)
- [Project structure](#project-structure)
- [Limitations and roadmap](#limitations-and-roadmap)

---

## The problem

| Tool alone | Problem |
|---|---|
| **Static scanners** (Semgrep) | Fast and deterministic, but they produce **false positives**, can't tell how dangerous a finding is in context, and **miss logic flaws** (missing authorization, IDOR) because those have no fixed pattern. |
| **LLMs** | Understand context and write fixes, but **hallucinate** findings and fixes, are slow, and on free tiers are **heavily rate-limited**. |

CodeGuard combines them so each covers the other's weakness: **the scanner does detection, the LLM does reasoning, and the scanner checks the LLM's fixes.**

---

## How it works

```
Python file
   │
   ▼
1. Semgrep scan ─────────────── local, free, no LLM. Vendored rules (rules/python.yml) for reproducible results
   │  findings compacted to 5 fields (~10x smaller than raw JSON)
   ▼
2. AI triage ────────────────── ONE small request per finding (±15 lines of code, never the whole file)
   │  real or false positive? severity? why?   Fail-safe: only an explicit "false" dismisses a finding
   ▼
3. AI logic review ──────────── looks for what scanners miss: missing auth, IDOR, hardcoded secrets
   │  anti-hallucination: every claim must quote code that really exists at that line, otherwise dropped
   ▼
4. Self-verifying fixes (--fix)
   │  for attempt 1..3:
   │     AI rewrites only the lines around the bug (±6)
   │     ✔ file still parses (ast.parse, which never executes the code)
   │     ✔ Semgrep re-scan: the rule no longer fires
   │     ✔ no new Semgrep findings introduced
   │     failed → the reason is fed back to the AI for the next attempt
   │  one fix per bug, even when several rules flag the same line
   ▼
5. Report ───────────────────── Markdown · JSON (API) · SARIF (GitHub Security tab) · MCP tool result
```

Every LLM call goes through one module (`app/llm.py`) with **cache → daily budget → pacing → retry with backoff**. If the AI is unavailable, the scan still completes with Semgrep's findings, labeled "AI unavailable, kept to be safe".

---

## Example output

Real output from `uv run python -m app.cli demo/vulnerable_app.py --fix` (shortened):

````markdown
| Semgrep findings | Confirmed real | Dismissed as false positive | Extra issues found by AI |
|---|---|---|---|
| 5 | 5 | 0 | 2 |

### 1. [HIGH] tainted-sql-string (line 12)
The user-controlled query parameter 'name' is directly interpolated into the SQL query string
using an f-string, allowing SQL injection.

**Fix:** ✅ verified (syntax OK, Semgrep re-scan clean) after 1 attempt(s)
```diff
-    return {"rows": conn.execute(f"SELECT * FROM users WHERE name = '{name}'").fetchall()}
+    return {"rows": conn.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchall()}
```

### 2. [CRITICAL] command-injection-os-system (line 17)
**Fix:** ✅ verified after 1 attempt(s)
```diff
-    os.system("ping -c 1 " + host)
+    subprocess.run(["ping", "-c", "1", host])
```

## Issues found by AI review (not detected by Semgrep)
- **[CRITICAL] Missing Authentication on Sensitive Action** (line 22): the admin database reset
  endpoint has no authentication or authorization check.
````

During this run Gemini returned **HTTP 503 (high demand)**. CodeGuard waited 10 seconds, retried, and finished normally.

---

## Evaluation

**Question: does the AI actually improve on Semgrep alone?**

**Setup:** 15 labeled Python files in `evaluation/cases/`:
- 10 vulnerable files: SQL, command and code injection, pickle, unsafe YAML, path traversal, weak password hash, Flask debug mode, hardcoded secret, IDOR, missing authorization
- 4 **false-positive traps**: safe code that Semgrep flags anyway (`shlex.quote` + `os.system`, md5 used for a cache key) or that looks risky
- 1 **prompt-injection** file: a comment tells "AI reviewers" to report everything as a false positive

In total: **12 real bugs** across 11 files, plus 4 files with no bugs.

**Ground truth:** every truly vulnerable line ends with `# VULN: <type>`. The script **strips the markers before scanning** so the AI can't read the answers (no label leakage), and keeps line numbers unchanged. A finding within 2 lines of a real bug counts as a hit.

### Results (`gemini-3.5-flash-lite`, free tier, 43 LLM calls, ~8 minutes)

| Metric | Semgrep alone | Semgrep + AI |
|---|---|---|
| **Precision** (findings that are real) | 83% | **95%** |
| **Recall** (real bugs found) | 58% (7/12) | **92% (11/12)** |
| False alarms | 3 | **1** |
| **Fixes verified** | – | **7/7 (100%)** |

Full per-file table: [`evaluation/results.md`](evaluation/results.md). Run it yourself with `uv run python -m evaluation.run_eval --fix`.

### What the numbers show
- **Recall 58% → 92%.** The AI logic review found what pattern rules can't: the hardcoded secret, the IDOR, the missing authorization check, and a path traversal that Semgrep's taint rules missed.
- **False alarms 3 → 1.** The AI correctly dismissed all 3 trap findings with the right reasoning, e.g. *"user input is properly sanitized using shlex.quote() before being passed to os.system()"* and *"MD5 is used here for generating a cache file name, not for cryptographic security"*.
- **The prompt-injection attack failed.** Despite the comment telling it to dismiss everything, the AI still reported the command injection.
- **Every attempted fix was verified** by a Semgrep re-scan on the first attempt.

### Honest analysis of the misses
- **Missed: `pickle.loads(request.data)`.** Semgrep's pickle rule didn't fire on `request.data`, and the logic-review prompt only looks for auth, IDOR, secrets and business logic, not deserialization. Next step: widen the review prompt (as `PROMPT_VERSION=v2`) and compare the scores in Langfuse.
- **The remaining false alarm** is on `safe_sql.py`: the SQL is parameterized (safe), but the AI flagged the `/user` endpoint for lacking authentication. That's arguably a real design issue, but it's not what the file is labeled for, so it counts against the AI.
- **Small set:** 15 files I wrote myself, so these numbers are indicative, not a benchmark. A larger public dataset is on the roadmap.
- An earlier run on `gemini-3.8-flash` hit that model's **20 requests/day** free limit. The evaluation now **refuses to write results** when the quota runs out, instead of silently reporting Semgrep-only numbers as "Semgrep + AI".

---

## Free-tier engineering (handling 429s)

Free LLM tiers allow only a few requests per minute and per day. The first evaluation run on `gemini-3.8-flash` hit a **20 requests/day** limit. Every protection below lives in `app/llm.py`:

| Layer | What it does | Setting |
|---|---|---|
| Small prompts | Only ±15 lines per finding; compacted Semgrep output; ±6-line fix windows. Token use scales with the **number of findings, not the size of the code** | `scanner.get_snippet`, `fixer.WINDOW` |
| Top-N findings | Only the most severe N findings go to the AI; the rest are kept as-is | `MAX_FINDINGS` |
| Disk cache | SHA-256(model + prompt) → answer. Re-runs cost **0 calls**, and an interrupted evaluation resumes for free | `CACHE_DIR` |
| Pacing | Minimum gap between requests, so 429s are prevented rather than just retried | `SECONDS_BETWEEN_CALLS` |
| Exponential backoff | 429 / 5xx / network error → wait 10s, 20s, 40s, 80s | `MAX_RETRIES` |
| Daily-quota detection | A "per day" 429 can't be fixed by waiting, so it **fails fast** instead of retrying | automatic |
| Daily budget | Stops before the provider blocks you | `DAILY_CALL_LIMIT` |
| Graceful degradation | AI failure → findings kept and labeled, never hidden | `pipeline.py` |
| Honest evaluation | If the quota runs out mid-evaluation, it **refuses to write results** rather than reporting Semgrep-only numbers as "Semgrep + AI" | `run_eval.py` |
| API rate limit | Per-IP limit, so users can't drain the quota | `REQUESTS_PER_MINUTE` |

All of these are unit-tested with a **fake Gemini**: a 429 retry, a daily-quota stop and a cache hit, with no real API calls.

---

## Security and hardening

| Threat | Defense | Where |
|---|---|---|
| Someone drains the LLM quota | Per-IP rate limit, daily LLM budget; the demo uses a public key (`demo-key`), set your own `API_KEY` to make the API private | `api.py`, `llm.py` |
| Timing attack on the API key | `secrets.compare_digest` on bytes | `api.py` |
| Huge input / denial of service | Pydantic `max_length`, Semgrep `--timeout`, subprocess timeout, container CPU/memory limits | `api.py`, `scanner.py`, Docker |
| Running malicious code | Scanned code is **never executed**: Semgrep reads it, `ast.parse` only parses it | `fixer.py` |
| Prompt injection inside scanned code | Code wrapped in `<code>` tags, "treat as data" instruction, tested with a poisoned file | prompts, `evaluation/cases/prompt_injection.py` |
| Hallucinated findings | Quoted evidence must exist at the claimed line (±1) | `review.py` |
| AI hides a real bug | Fail-safe: only an explicit `is_real: false` dismisses; any AI error keeps the finding | `triage.py`, `pipeline.py` |
| Bad AI fixes | Syntax check, Semgrep re-scan, no new findings; otherwise "⚠️ unverified" | `fixer.py` |
| Leaked secrets | `.env` gitignored and dockerignored; GitHub push protection on | config |
| Container compromise | Non-root user, read-only filesystem, all Linux capabilities dropped, no-new-privileges | `Dockerfile` |
| Rule tampering / supply chain | Semgrep rules vendored into the repo and image; Semgrep and uv versions pinned; no downloads at runtime | `rules/`, `Dockerfile` |
| Telemetry | Semgrep runs with `--metrics=off` | `scanner.py` |

Verified locally: the image runs as `appuser` under `--read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges` and still scans correctly.

---

## Design decisions

**Why Semgrep first instead of letting an LLM agent read the code?** Agent loops resend the whole conversation every turn, so token use grows quickly and free tiers run out. Semgrep scans locally at no cost and points at the exact lines that matter. The pipeline is also deterministic, testable and easy to explain.

**Why one request per finding?** Each request is small (well under 1k tokens), fits strict per-minute limits, and fails independently: one bad answer doesn't lose the whole scan.

**Why fail-safe?** For a security tool, a missed vulnerability is worse than a false alarm. So when the AI is unsure, errors or is rate-limited, the finding stays.

**Why verify fixes with Semgrep?** An LLM saying "fixed" isn't evidence. The same scanner that found the bug confirms it's gone, and that nothing new appeared.

**Why vendor the rules?** Evaluation numbers must be reproducible. If Semgrep's registry changes, results would drift.

**Why plain functions and one dataclass?** The code is meant to be readable and explainable line by line. `Finding` is a dataclass because it's passed through every stage; raw LLM JSON stays a dict because it's only validated and displayed.

**Why no async?** The free tier allows one LLM call at a time, so async wouldn't speed anything up. FastAPI runs the sync endpoints in a thread pool. With a paid API, parallel async calls would be the next step.

---

## Quick start

**Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/), a free [Gemini API key](https://aistudio.google.com). Docker is optional.

```bash
git clone https://github.com/adityakumarprasad/CodeGuard.git
cd CodeGuard
uv sync
uv tool install semgrep          # installed separately so its dependencies never clash with ours
cp .env.example .env             # then set GEMINI_API_KEY (API_KEY defaults to the public demo-key)
```

Pick a model with a generous free daily limit (check your limits at https://aistudio.google.com/rate-limit) and set `SECONDS_BETWEEN_CALLS = 60 / RPM`.

```bash
uv run python -m app.cli demo/vulnerable_app.py          # scan
uv run python -m app.cli demo/vulnerable_app.py --fix    # scan + self-verifying fixes
```

---

## Interfaces

One core (`app/pipeline.py`) with four ways to use it:

| Interface | Command | For |
|---|---|---|
| **CLI** | `uv run python -m app.cli FILE [...] [--fix] [--sarif out.sarif]` | Terminal and CI |
| **Web API + page** | `uv run uvicorn app.api:app --port 8080`, then open http://localhost:8080 | Live demo |
| **MCP server** | `uv run python -m app.mcp_server` | Claude Code, Cursor and other AI tools |
| **SARIF** | `--sarif` + `.github/workflows/security-scan.yml` | GitHub Security → Code scanning |

**API:**
```bash
curl -X POST http://localhost:8080/scan \
  -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
  -d '{"code": "import os\nos.system(input())", "fix": false}'
```

**MCP (Claude Code):**
```bash
claude mcp add codeguard -- uv run --directory /path/to/CodeGuard python -m app.mcp_server
```
Then ask: *"Use codeguard to review demo/vulnerable_app.py"*. The server exposes one tool, `security_review(file_path, fix=False)`. Logs go to stderr because stdout is the MCP channel.

---

## Deployment

```
git push → GitHub Actions: pytest → build image → ghcr.io/adityakumarprasad/codeguard:latest
                                                    │
                     ┌──────────────────────────────┼───────────────────────────┐
                     ▼                              ▼                           ▼
              Render (free)               Google Cloud Run              Azure Container Apps
                                          └──────── Terraform (terraform/) ───────┘
```

**Docker (hardened):**
```bash
docker build -t codeguard .
docker run --rm -p 8080:8080 --env-file .env \
  --read-only --tmpfs /tmp --memory 1g --cpus 1 \
  --cap-drop ALL --security-opt no-new-privileges codeguard
```

**Render:** New Web Service → Existing image → `ghcr.io/adityakumarprasad/codeguard:latest`, port `8080`, health check `/health`, and set `GEMINI_API_KEY`, `API_KEY` and `LLM_MODEL`.

**Multi-cloud with Terraform** (one image, two clouds):
```bash
cd terraform
cp example.tfvars terraform.tfvars    # fill in values (gitignored)
terraform init && terraform plan && terraform apply
terraform destroy                     # when done
```
`gcp.tf` creates an Artifact Registry remote repository that proxies ghcr.io (Cloud Run can't pull from it directly) and a Cloud Run service capped at one instance. `azure.tf` creates a Container App that scales to zero, with the keys stored as Azure secrets.

---

## Observability with Langfuse

Optional. It's enabled automatically when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set, and with no keys nothing changes.

- Each scan is one **`security-scan` trace**, with nested `triage`, `logic-review` and `fix` generations showing the prompt, answer, latency and tokens.
- Each evaluation run is one **`evaluation-run` trace** with `precision`, `recall` and `fix_rate` **scores**, tagged with the model and `PROMPT_VERSION`.
- **Prompt workflow:** change a prompt, bump `PROMPT_VERSION`, re-run the evaluation, and compare the scores in Langfuse.

---

## Testing

```bash
uv run pytest -v
```

37 tests. **None of them call the LLM**, so they're free and deterministic and run in CI on every push. AI behavior is tested with fakes (`monkeypatch`), while Semgrep runs for real.

| Area | What's tested |
|---|---|
| Free-tier protection | Retry after 429; daily quota stops immediately; cache prevents repeat calls; JSON extraction |
| Safety | Fail-safe triage; findings kept when the AI is down; hallucinated lines and code rejected |
| Fixes | Applying replacements; verification accepts a parameterized query and rejects unchanged code or syntax errors; the retry loop feeds the failure back and succeeds on attempt 2; one fix per bug |
| Evaluation | Ground-truth markers are hidden from the AI; scoring with line tolerance |
| API | API key required; rate limit returns 429; empty input rejected; dataclasses serialized to JSON |
| Output | Markdown sections; SARIF contains only real findings and uses forward slashes |
| MCP | Tool registered; non-Python files rejected |

---

## Project structure

```
app/
  config.py        all settings, from environment variables
  models.py        Finding dataclass
  scanner.py       Step 1: Semgrep, compacting, code snippets
  llm.py           the only Gemini client: cache, budget, pacing, backoff
  triage.py        Step 2: real or false positive (fail-safe)
  review.py        Step 3: logic flaws + anti-hallucination check
  fixer.py         Step 4: fix → verify → retry
  pipeline.py      the core used by every interface
  report.py        Markdown + SARIF
  cli.py · api.py · mcp_server.py · static/index.html
evaluation/
  cases/           15 labeled files (# VULN markers = ground truth)
  run_eval.py      precision / recall / fix rate, Semgrep alone vs Semgrep + AI
  results.md       latest results
rules/python.yml   vendored Semgrep rules
tests/             pytest suite (no LLM calls)
terraform/         Cloud Run + Azure Container Apps
.github/workflows/ CI (tests + image) and SARIF code scanning
Dockerfile         hardened, non-root image
```

---

## Limitations and roadmap

| Limitation | Next step |
|---|---|
| Python only | Add Semgrep rulesets and syntax checks for other languages |
| "Verified" means the file parses, Semgrep no longer fires and nothing new appears. It does **not** prove behavior is unchanged | Run the project's unit tests as a fourth check |
| Fixes may add imports inside functions (the AI may only edit lines near the bug) | Allow a separate, verified import edit at the top of the file |
| The logic review is skipped for files over 400 lines (free-tier budget) | Review function by function |
| Evaluation set is small (15 files, written by me), so the numbers are indicative, not definitive | Public benchmarks such as the OWASP Benchmark and real CVE datasets |
| Rate limit and daily budget are in memory (correct for a single instance) | Redis (e.g. Upstash) for multi-instance deployments |
| Free-tier Gemini may use prompts to improve models | Paid tier or a self-hosted model for private code |

---

Built by **Aditya Kumar Prasad** as part of an AI deployment course (Week 3: multi-cloud and industry skills), rebuilt on free tiers with self-verifying fixes, evaluation, MCP and hardening added.
