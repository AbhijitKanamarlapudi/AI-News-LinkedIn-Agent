# AI News LinkedIn Agent — Project Documentation

> Automatically fetch the latest Anthropic / Claude platform updates and publish a polished, audience-targeted LinkedIn post every day — hands-free.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [How It Works](#2-how-it-works)
3. [Project Structure](#3-project-structure)
4. [Tech Stack](#4-tech-stack)
5. [Step-by-Step Setup Guide](#5-step-by-step-setup-guide)
6. [Configuration Reference](#6-configuration-reference)
7. [How the Content Fetcher Works](#7-how-the-content-fetcher-works)
8. [How the LinkedIn Post Is Built](#8-how-the-linkedin-post-is-built)
9. [Daily Usage](#9-daily-usage)
10. [Troubleshooting](#10-troubleshooting)
11. [Customisation Guide](#11-customisation-guide)

---

## 1. Project Overview

### What it does

The **AI News LinkedIn Agent** is a Python automation tool that:

1. Scrapes the official **Anthropic News** and **Anthropic Research** pages for the latest articles about Claude, the Claude API, and the broader Anthropic platform.
2. Scores and ranks those articles using a **two-tier relevance system** — prioritising content most useful to data engineers and ML platform teams.
3. Generates a **structured, engagement-optimised LinkedIn post** for the top-ranked article.
4. Publishes that post directly to your LinkedIn profile (or company page) via the official LinkedIn REST API.
5. Tracks which articles have already been posted so the same article is never published twice.

### Who it is for

- **Data engineers and ML platform engineers** who want to maintain an active LinkedIn presence without spending time writing posts daily.
- **Technical content creators** covering AI / data infrastructure topics.
- **Developer advocates** at companies building on the Anthropic platform.

### What problem it solves

Staying visible on LinkedIn requires consistent posting, but finding good content and writing thoughtful posts takes 20–30 minutes per day. This agent compresses that effort to a single terminal command that runs in under 60 seconds.

---

## 2. How It Works

### End-to-end flow

```
┌──────────────────────────────────────────────────────────────────┐
│                        DAILY RUN  (run_once)                     │
│                                                                  │
│   ┌──────────────┐      ┌──────────────────┐                    │
│   │  Scheduler   │─────▶│   NewsFetcher    │                    │
│   │ (APScheduler)│      │                  │                    │
│   └──────────────┘      │  1. GET /news    │                    │
│                         │  2. GET /research│                    │
│                         │  3. Scrape links │                    │
│                         │  4. Fetch each   │                    │
│                         │     article page │                    │
│                         │  5. Score & rank │                    │
│                         └────────┬─────────┘                    │
│                                  │                              │
│                         List of ranked articles                  │
│                         (Tier 1 first, Tier 2 backfill)         │
│                                  │                              │
│                                  ▼                              │
│                         ┌──────────────────┐                    │
│                         │  LinkedInPoster  │                    │
│                         │                  │                    │
│                         │  1. Skip if      │                    │
│                         │     already      │                    │
│                         │     posted       │                    │
│                         │  2. Build post   │                    │
│                         │     content      │                    │
│                         │  3. Call LinkedIn│                    │
│                         │     REST API     │                    │
│                         │  4. Save to      │                    │
│                         │     posted_      │                    │
│                         │     articles.json│                    │
│                         └──────────────────┘                    │
│                                                                  │
│         posted_articles.json ◀── deduplication store            │
└──────────────────────────────────────────────────────────────────┘
```

### Two-tier content strategy

The fetcher uses a scoring system that places articles into one of two tiers before ranking:

| Tier | Name | Who it targets | Minimum score to qualify |
|------|------|----------------|--------------------------|
| **Tier 1** | Data Developer | Data engineers, ML platform teams | Data-dev score ≥ 2 |
| **Tier 2** | General Claude Update | Any AI-curious professional | Claude score ≥ 1 |

Tier 1 articles are always surfaced before Tier 2 articles. If fewer than `limit` (default: 5) Tier 1 articles are found, Tier 2 articles backfill the remainder. Only the single highest-ranked article from the combined list is published per run.

---

## 3. Project Structure

```
AI Agent LinkedIn/
│
├── src/                        # All application source code
│   ├── __init__.py             # Makes src a Python package
│   ├── ai_agent.py             # Orchestrator — wires fetcher + poster + scheduler
│   ├── news_fetcher.py         # Scrapes Anthropic sources, scores, and ranks articles
│   ├── linkedin_poster.py      # Builds post content and publishes to LinkedIn
│   └── config.py               # Loads .env into typed Config class attributes
│
├── tests/
│   ├── __init__.py
│   └── test_suite.py           # Full test suite covering fetcher and poster logic
│
├── .env                        # Your real secrets (never commit this)
├── .env.example                # Template showing all required variables
├── .gitignore                  # Excludes .env, .venv, posted_articles.json, etc.
├── pyproject.toml              # Project metadata and dependency declarations
├── requirements.txt            # Pinned dependency list (pip install -r)
├── posted_articles.json        # Auto-generated; tracks already-posted article URLs
├── logo.svg / logo.svg.png     # Project logo assets
└── README.md                   # Short project overview
```

### Key runtime files

| File | Created by | Purpose |
|------|-----------|---------|
| `posted_articles.json` | `LinkedInPoster` on first successful post | Deduplication store — prevents the same article being posted twice |
| `.env` | You, during setup | Holds all secrets and runtime config |

---

## 4. Tech Stack

| Library | Version | Why it is used |
|---------|---------|----------------|
| `requests` | ≥ 2.31.0 | HTTP client for scraping Anthropic pages and calling the LinkedIn REST API |
| `beautifulsoup4` | ≥ 4.12.2 | HTML parsing — extracts article links and Open Graph metadata from scraped pages |
| `lxml` | ≥ 4.9.3 | Fast, permissive HTML parser backend used by BeautifulSoup |
| `python-dotenv` | ≥ 1.0.0 | Loads `.env` file variables into `os.environ` at startup |
| `APScheduler` | ≥ 3.10.4 | Background job scheduler — runs the agent on a configurable interval (default: every 24 hours) |
| `linkedin-api` | ≥ 2.0.0 | Unofficial LinkedIn Voyager API client used as a credential-based fallback when no OAuth token is available |

### Dev dependencies (optional)

| Library | Purpose |
|---------|---------|
| `pytest` | Test runner |
| `black` | Code formatter |
| `flake8` | Linter |

---

## 5. Step-by-Step Setup Guide

### Prerequisites

- Python **3.9 or later** (`python3 --version`)
- `pip` or `pip3`
- A LinkedIn account
- A LinkedIn **OAuth 2.0 access token** (instructions below)

---

### Step 1 — Download the project

If you received the project as a zip file, unzip it. If you are cloning from a repository:

```bash
git clone <repository-url>
cd "AI Agent LinkedIn"
```

---

### Step 2 — Create a virtual environment

A virtual environment keeps the project's dependencies isolated from your system Python.

```bash
python3 -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (Command Prompt)
.venv\Scripts\activate.bat
```

You should see `(.venv)` at the start of your terminal prompt.

---

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

Or, if you prefer the `pyproject.toml` approach:

```bash
pip install .
```

To also install development tools (pytest, black, flake8):

```bash
pip install ".[dev]"
```

---

### Step 4 — Configure your `.env` file

Copy the example file:

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in the values. At minimum you need `LINKEDIN_ACCESS_TOKEN`. See the [Configuration Reference](#6-configuration-reference) for a full explanation of every variable.

A minimal working `.env` looks like this:

```env
LINKEDIN_ACCESS_TOKEN=AQV...your_token_here...
LINKEDIN_DRY_RUN=false
SCHEDULE_INTERVAL_HOURS=24
```

---

### Step 5 — Get your LinkedIn Access Token

LinkedIn uses OAuth 2.0. Follow these steps to get a token that lets the agent post on your behalf.

#### 5a — Create a LinkedIn Developer Application

1. Go to [https://www.linkedin.com/developers/apps/new](https://www.linkedin.com/developers/apps/new)
2. Fill in the required fields:
   - **App name**: e.g. `AI News Agent`
   - **LinkedIn Page**: select or create a company page (required by LinkedIn)
   - **App logo**: upload any image
3. Click **Create app**

#### 5b — Request the correct OAuth scopes

On your app's **Auth** tab, request the following OAuth 2.0 scopes:

| Scope | Purpose |
|-------|---------|
| `w_member_social` | Post to your personal LinkedIn profile |
| `r_liteprofile` | Read your profile ID (used to build the author URN) |
| `openid` | Required for the userinfo endpoint |
| `profile` | Access your profile information |

> **Note:** If you want to post as a LinkedIn **Company Page** instead of your personal profile, also request `w_organization_social` and set `LINKEDIN_PAGE_ID` in your `.env`.

#### 5c — Generate an access token

The quickest method uses LinkedIn's **OAuth 2.0 Token Generator** in the developer portal:

1. On your app page, go to the **Auth** tab.
2. Scroll to **OAuth 2.0 tools** and click **OAuth 2.0 Token Generator** (or use the direct link in the portal).
3. Select the scopes listed above.
4. Click **Request access token**.
5. Authorise the app when prompted.
6. Copy the **Access Token** that appears.

Paste it into your `.env`:

```env
LINKEDIN_ACCESS_TOKEN=AQV...copied_token...
```

> **Token expiry:** LinkedIn tokens expire after **60 days**. When your token expires you will get a 401 error. Return to the token generator and repeat step 5c.

#### 5d — (Optional) Find your author URN

If the agent cannot auto-resolve your identity via the `/userinfo` endpoint, set `LINKEDIN_AUTHOR_URN` manually.

Your personal URN looks like: `urn:li:person:abc123XYZ`

To find it:
1. Go to [https://www.linkedin.com/in/me/](https://www.linkedin.com/in/me/) — note your profile ID from the URL.
2. Or call the userinfo endpoint directly:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" https://api.linkedin.com/v2/userinfo
   ```
   The `sub` field in the JSON response is your profile ID. Your URN is `urn:li:person:<sub>`.

---

### Step 6 — Run a dry-run to verify setup

Before publishing a real post, run in dry-run mode (the default):

```bash
LINKEDIN_DRY_RUN=true python -m src.ai_agent
```

You should see output like:

```
2026-03-28 09:00:00 - __main__ - INFO - Starting AI News LinkedIn Agent...
2026-03-28 09:00:01 - __main__ - INFO - Fetching curated Data Platform + AI updates...
2026-03-28 09:00:05 - __main__ - INFO - Found 4 candidate articles
2026-03-28 09:00:05 - __main__ - INFO - Dry-running one article to LinkedIn...
Dry run only, not posted: Claude 3.5 Sonnet: Our Most Intellig...
Content preview:
As a data developer, the Claude API just became a tool you need to know about.

→ Claude 3.5 Sonnet: Our Most Intelligent Model

What this means for data teams:
Claude 3.5 Sonnet is now our most intelligent model...
```

---

### Step 7 — Run your first real post

Set `LINKEDIN_DRY_RUN=false` in your `.env` (or pass it inline):

```bash
python -m src.ai_agent
```

The agent will:
1. Fetch and rank articles
2. Build the post
3. Publish it to LinkedIn
4. Save the article URL to `posted_articles.json`
5. Print a summary

---

## 6. Configuration Reference

All configuration is loaded from your `.env` file by `src/config.py`.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LINKEDIN_ACCESS_TOKEN` | **Yes** (preferred) | _(empty)_ | OAuth 2.0 Bearer token from the LinkedIn Developer portal. Used for all official API calls. Expires after 60 days. |
| `LINKEDIN_EMAIL` | Conditional | _(empty)_ | Your LinkedIn login email. Only needed if you are using the unofficial credential-based fallback (no access token). |
| `LINKEDIN_PASSWORD` | Conditional | _(empty)_ | Your LinkedIn login password. Only needed alongside `LINKEDIN_EMAIL` for the credential-based fallback. |
| `LINKEDIN_API_VERSION` | No | `202603` | LinkedIn API version header sent with every REST request. Format: `YYYYMM`. Update if LinkedIn deprecates this version. |
| `LINKEDIN_AUTHOR_URN` | No | _(empty)_ | Fully-qualified LinkedIn URN to post as (e.g. `urn:li:person:abc123`). If omitted the agent resolves your URN via the `/userinfo` endpoint. Takes precedence over `LINKEDIN_PAGE_URN` and `LINKEDIN_PAGE_ID`. |
| `LINKEDIN_PAGE_URN` | No | _(empty)_ | Fully-qualified organization URN (e.g. `urn:li:organization:12345`). Use to post as a company page. Takes precedence over `LINKEDIN_PAGE_ID`. |
| `LINKEDIN_PAGE_ID` | No | _(empty)_ | Numeric LinkedIn company page ID. The agent converts this to `urn:li:organization:<id>` automatically. Use when you only have the page ID, not the full URN. |
| `LINKEDIN_DRY_RUN` | No | `true` | When set to `true`, `yes`, `1`, or `on`, the agent generates and logs the post content but does **not** publish to LinkedIn. Set to `false` for production use. |
| `NEWSAPI_KEY` | No | _(empty)_ | Legacy NewsAPI.org key. Not used by the current scraper-based fetcher. Safe to leave empty. |
| `NEWS_KEYWORDS` | No | `artificial intelligence,machine learning` | Comma-separated keyword list. Currently informational; the fetcher uses its built-in term sets rather than this variable for scoring. |
| `SCHEDULE_TIME` | No | `09:00` | Intended daily run time in 24-hour format. Currently informational — the scheduler uses `SCHEDULE_INTERVAL_HOURS` for timing. |
| `SCHEDULE_INTERVAL_HOURS` | No | `24` | How many hours between scheduled runs. Set to `24` for once-daily posting, `12` for twice-daily, etc. |

### Authentication priority

```
LINKEDIN_ACCESS_TOKEN set?
        │
        ├── YES → Use official LinkedIn REST API  (recommended)
        │
        └── NO  → Fall back to LINKEDIN_EMAIL + LINKEDIN_PASSWORD
                  (unofficial Voyager API — may break without warning)
```

### Author URN resolution priority

```
LINKEDIN_AUTHOR_URN set?
        │
        ├── YES → Use it directly
        │
        └── NO  → LINKEDIN_PAGE_URN set?
                        │
                        ├── YES → Use it directly
                        │
                        └── NO  → LINKEDIN_PAGE_ID set?
                                        │
                                        ├── YES → Build urn:li:organization:<id>
                                        │
                                        └── NO  → Resolve via /userinfo endpoint
```

---

## 7. How the Content Fetcher Works

**File:** `src/news_fetcher.py` — `NewsFetcher` class

### Sources

The fetcher scrapes two official Anthropic pages:

| Source name | URL | Allowed paths |
|-------------|-----|---------------|
| Anthropic News | `https://www.anthropic.com/news` | `/news/*` |
| Anthropic Research | `https://www.anthropic.com/research` | `/research/*` (excludes `/research/team/`) |

For each source, up to **10 article links** are extracted per run (`INDEX_ARTICLES_PER_SOURCE = 10`). Each link is then fetched individually to extract its title, description (from Open Graph tags), publication date, and image.

### Scoring pipeline

```
All candidate articles
        │
        ▼
  Deduplicate by URL
        │
        ▼
  Noise filter (skip any article containing NOISE_TERMS)
        │
        ▼
  Score each article
  ┌─────────────────────────────────────────────┐
  │  data_score = count of DATA_DEV_TERMS found │
  │  claude_score = count of CLAUDE_TERMS found │
  └─────────────────────────────────────────────┘
        │
        ├── data_score >= 2  →  Tier 1
        │   final_score = data_score * 3 + claude_score
        │
        └── claude_score >= 1  →  Tier 2
            final_score = claude_score
        │
        ▼
  Sort each tier by (score DESC, published_at DESC)
        │
        ▼
  Return: Tier 1 articles first, backfilled by Tier 2 up to limit=5
```

The "haystack" used for scoring is a single lowercased string combining the article's **title**, **description**, **URL**, and **source name**. This means terms that appear in the URL slug (e.g. `/news/claude-api-tool-use`) also contribute to the score.

### DATA_DEV_TERMS (Tier 1 keywords)

These 38 terms represent topics directly relevant to data engineers and ML platform teams:

```
api, tool use, function calling, rag, retrieval, embedding, embeddings,
vector, mcp, model context protocol, data pipeline, pipeline, sql,
database, data engineering, data platform, streaming, batch, fine-tuning,
fine tuning, context window, long context, structured output, json mode,
vision, multimodal, agent, agents, agentic, workflow, orchestration,
computer use, files api, prompt caching, latency, throughput, sdk,
tokens, cost
```

### CLAUDE_TERMS (Tier 2 keywords)

These 18 terms represent general Anthropic / Claude platform topics:

```
claude, anthropic, sonnet, opus, haiku, model, llm, language model,
capability, capabilities, intelligence, reasoning, benchmark, release,
launch, update, feature, safety, alignment
```

### NOISE_TERMS (always filtered out)

```
sports, football, celebrity, entertainment, children's book,
retirement, digital marketing, movie
```

---

## 8. How the LinkedIn Post Is Built

**File:** `src/linkedin_poster.py` — `LinkedInPoster.create_post_content()`

### Post structure

Every post follows this exact template:

```
{hook}

→ {article title}

{why_it_matters_prefix}
{article description (truncated to 200 chars)}

{takeaway}

Source: {source name}

Reference link: {article URL}

{hashtags (up to 6)}
```

### Section breakdown

#### Hook

An opening line chosen by matching the article's haystack against keyword patterns. The hook is **tier-aware** — Tier 1 articles get direct, technical hooks aimed at data engineers; Tier 2 articles get broader AI-curiosity hooks.

**Tier 1 hook examples:**

| Keyword match | Hook text |
|---------------|-----------|
| `rag` / `retrieval` | "If you're building RAG pipelines, Claude just got more powerful for your stack." |
| `embedding` / `vector` | "Vector search + Claude: this is the combination your data platform has been waiting for." |
| `agent` / `agentic` / `computer use` | "Autonomous agents that can reason over your data — Claude's latest move changes the game." |
| `mcp` / `model context protocol` | "MCP is quietly becoming the backbone of AI-data integrations. Here's why that matters." |
| `context window` / `long context` | "200K tokens of context. Your entire data schema, docs, and history — all in one prompt." |
| `api` / `sdk` | "As a data developer, the Claude API just became a tool you need to know about." |
| `fine-tun` | "Fine-tuning Claude for your domain data — this is what production AI actually looks like." |
| `structured output` / `json` | "Structured outputs from Claude mean cleaner data pipelines and fewer parsing headaches." |
| `vision` / `multimodal` | "Claude can now see your charts, dashboards, and data visualisations. Let that sink in." |
| _(default)_ | "Data engineers — Claude just shipped something that belongs in your toolkit." |

**Tier 2 hook examples:**

| Keyword match | Hook text |
|---------------|-----------|
| `sonnet` / `opus` / `haiku` | "A new Claude model just dropped — and the benchmark numbers are worth your attention." |
| `safety` / `alignment` | "Anthropic continues to set the bar for what responsible AI development looks like." |
| `reasoning` | "Claude's reasoning capabilities just leveled up. Here's what that means in practice." |
| _(default)_ | "Anthropic just published something worth reading if you're serious about AI." |

#### Why it matters

- **Prefix** for Tier 1: `"What this means for data teams:"`
- **Prefix** for Tier 2: `"Why this matters:"`
- **Body**: The article's Open Graph description, truncated to 200 characters with a trailing `...` if longer. If no description is available, a keyword-matched fallback sentence is used.

#### Takeaway

A first-person opinion line to drive engagement. Examples:

| Keyword match | Takeaway |
|---------------|---------|
| `rag` / `retrieval` | "My take: RAG + Claude is becoming the default pattern for enterprise AI. Get ahead of it." |
| `mcp` | "My take: MCP will be to AI what REST was to web APIs. Learn it now." |
| `agent` | "My take: the gap between 'AI assistant' and 'AI coworker' is closing faster than most teams realise." |
| `safety` / `alignment` | "My take: safety and capability are not a trade-off — Anthropic keeps proving that." |

#### Hashtags

Always starts with `#Claude #GenerativeAI #DataEngineering`, then adds up to 3 keyword-specific tags:

| Keyword | Hashtag added |
|---------|--------------|
| `rag` / `retrieval` | `#RAG` |
| `embedding` | `#Embeddings` |
| `vector` | `#VectorSearch` |
| `agent` / `agentic` | `#AIAgents` |
| `mcp` / `model context protocol` | `#MCP` |
| `api` / `sdk` | `#ClaudeAPI` |
| `fine-tun` | `#FineTuning` |
| `context window` | `#LongContext` |
| `structured output` | `#StructuredAI` |
| `multimodal` / `vision` | `#MultimodalAI` |
| `computer use` | `#ComputerUse` |
| `safety` / `alignment` | `#ResponsibleAI` |
| `pipeline` | `#DataPipeline` |
| `data platform` | `#DataPlatform` |
| `anthropic` | `#Anthropic` |

Maximum 6 hashtags are included per post.

### Real example post

```
As a data developer, the Claude API just became a tool you need to know about.

→ Introducing the Claude Files API and token-efficient tool use

What this means for data teams:
The new Files API lets you upload documents once and reference them across
multiple API calls — dramatically reducing token costs for document-heavy...

My take: if you're building data products, Claude's platform is worth a
serious look right now.

Source: Anthropic News

Reference link: https://www.anthropic.com/news/files-api

#Claude #GenerativeAI #DataEngineering #ClaudeAPI #DataPlatform
```

### Post validation

Before publishing, `_validate_post_content()` enforces:
- Post is not empty
- Post has at least 3 non-empty lines
- Post contains a `Source: ` line
- Post contains at least one hashtag starting with `#`

---

## 9. Daily Usage

### Single command to run every day

```bash
python -m src.ai_agent
```

That's it. The agent will:
1. Start immediately and post one article
2. Then continue running in the background, posting again every `SCHEDULE_INTERVAL_HOURS` hours
3. Stop with `Ctrl+C`

### Run once and exit (no scheduler loop)

If you prefer to trigger the agent from an external cron job (macOS `launchd`, Linux `cron`, GitHub Actions, etc.) and do not want the built-in scheduler, call `run_once()` directly:

```bash
python -c "from src.ai_agent import AINewsLinkedInAgent; AINewsLinkedInAgent().run_once()"
```

### Schedule via macOS cron (example)

Add this to your crontab (`crontab -e`) to post every day at 9 AM:

```cron
0 9 * * * cd "/Users/yourname/Documents/AI Agent LinkedIn" && /Users/yourname/Documents/AI Agent LinkedIn/.venv/bin/python -m src.ai_agent
```

### Check what has already been posted

```bash
cat posted_articles.json
```

The file is a JSON object with an `articles` array. Each entry has `title`, `url`, and `timestamp`.

---

## 10. Troubleshooting

### "Organization permissions must be used" error

**Symptom:**
```
Official LinkedIn returned 403: {"message":"Organization permissions must be used..."}
```

**Cause:** You are trying to post as a company page, but either the scope `w_organization_social` is missing from your token, or you have not set the page URN correctly.

**Fix:**
1. In the LinkedIn Developer portal, add the `w_organization_social` scope to your app.
2. Re-generate your access token (repeat Step 5c in the setup guide).
3. Set one of these in your `.env`:
   ```env
   LINKEDIN_PAGE_ID=123456789
   # OR
   LINKEDIN_PAGE_URN=urn:li:organization:123456789
   ```
4. Make sure your LinkedIn account is an **Admin** of the company page.

---

### Token expired / 401 Unauthorised error

**Symptom:**
```
Official LinkedIn returned 401: {"message":"Unauthorized","status":401}
```

**Cause:** LinkedIn access tokens expire after **60 days**.

**Fix:**
1. Return to the LinkedIn Developer portal.
2. Open your app → Auth tab → OAuth 2.0 Token Generator.
3. Generate a new token with the same scopes.
4. Update `LINKEDIN_ACCESS_TOKEN` in your `.env`.
5. Re-run the agent.

---

### No articles found

**Symptom:**
```
WARNING - No articles found
```

**Cause:** The Anthropic website structure may have changed, the request timed out, or all articles were filtered out by the noise or scoring thresholds.

**Fix:**
1. Check your internet connection.
2. Visit `https://www.anthropic.com/news` in a browser to confirm the site is reachable.
3. If the site is up, the page structure may have changed. Check `NewsFetcher._extract_article_urls()` — specifically the `allowed_path_prefixes` and the anchor link parsing logic.
4. Temporarily lower scoring thresholds for debugging — see [Customisation Guide](#11-customisation-guide).

---

### Already posted / 0 posts published

**Symptom:**
```
Article already posted: Claude 3.5 Sonnet: Our Most Intellig...
Completed posting for 0 article(s) in this run
```

**Cause:** The top-ranked article(s) are already in `posted_articles.json`.

**Fix (normal):** Wait for Anthropic to publish a new article. This is expected behaviour — it means the deduplication is working correctly.

**Fix (reset):** If you want to re-post an article (e.g. for testing), edit `posted_articles.json` and remove the relevant entry, or delete the file entirely:

```bash
rm posted_articles.json
```

---

### Dry-run mode is on / posts not appearing on LinkedIn

**Symptom:** The agent runs without errors but nothing appears on LinkedIn.

**Cause:** `LINKEDIN_DRY_RUN` is set to `true` (the default).

**Fix:** Set `LINKEDIN_DRY_RUN=false` in your `.env`.

---

### ModuleNotFoundError

**Symptom:**
```
ModuleNotFoundError: No module named 'requests'
```

**Cause:** Dependencies are not installed, or you are running Python from outside the virtual environment.

**Fix:**
```bash
source .venv/bin/activate   # or the Windows equivalent
pip install -r requirements.txt
python -m src.ai_agent
```

---

## 11. Customisation Guide

### Change how often posts are published

Edit `SCHEDULE_INTERVAL_HOURS` in `.env`:

```env
SCHEDULE_INTERVAL_HOURS=12   # post twice a day
SCHEDULE_INTERVAL_HOURS=48   # post every two days
SCHEDULE_INTERVAL_HOURS=168  # post once a week
```

### Change the maximum posts per run

By default, exactly **one post** is published per run. To change this, edit the `max_posts` argument in `src/ai_agent.py`:

```python
# Line 56 in ai_agent.py
success_count = self.linkedin_poster.post_multiple(articles, max_posts=1)
#                                                             ^^^^^^^^^^^
# Change 1 to 2, 3, etc. to publish more articles per run
```

### Add more news sources

In `src/news_fetcher.py`, add entries to the `SOURCE_PAGES` list:

```python
SOURCE_PAGES = [
    # existing entries...
    {
        "name": "Anthropic Blog",
        "url": "https://www.anthropic.com/blog",
        "base": "https://www.anthropic.com",
        "allowed_path_prefixes": ["/blog/"],
    },
]
```

Each source entry supports:

| Key | Required | Description |
|-----|----------|-------------|
| `name` | Yes | Display name used in post content and logging |
| `url` | Yes | The index page URL to scrape for article links |
| `base` | Yes | Base URL for resolving relative href links |
| `allowed_path_prefixes` | Yes | Only links whose URL path starts with one of these strings are followed |
| `blocked_path_segments` | No | Links whose URL path contains any of these strings are skipped |

### Tweak the scoring thresholds

In `src/news_fetcher.py`, adjust the class-level constants:

```python
# Require at least 3 data-dev term matches to qualify as Tier 1 (default: 2)
DATA_DEV_MIN_SCORE = 3

# Require at least 2 Claude term matches to qualify as Tier 2 (default: 1)
CLAUDE_MIN_SCORE = 2
```

Raising `DATA_DEV_MIN_SCORE` makes Tier 1 qualification stricter (fewer, more targeted articles). Lowering `CLAUDE_MIN_SCORE` lets more general articles through to Tier 2.

### Add Tier 1 keywords

To make the fetcher recognise additional data engineering terms as high-priority signals, add them to `DATA_DEV_TERMS` in `src/news_fetcher.py`:

```python
DATA_DEV_TERMS = {
    # ... existing terms ...
    "kafka",
    "spark",
    "dbt",
    "lakehouse",
    "feature store",
}
```

### Add new hook / takeaway patterns

In `src/linkedin_poster.py`, extend the `if/elif` chains in `_build_hook()`, `_build_why_it_matters()`, and `_build_takeaway()`:

```python
# In _build_hook(), inside the tier == 1 block:
if "kafka" in haystack or "streaming" in haystack:
    return "Real-time data pipelines + Claude: the combination your platform team needs to see."
```

### Disable the built-in scheduler and use an external one

Instead of calling `agent.start_scheduler()`, call `agent.run_once()` from a script and schedule that script externally (cron, launchd, GitHub Actions):

```python
# run_once.py
from src.ai_agent import AINewsLinkedInAgent
AINewsLinkedInAgent().run_once()
```

```bash
# GitHub Actions example (daily at 9am UTC)
# .github/workflows/post.yml
on:
  schedule:
    - cron: '0 9 * * *'
jobs:
  post:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python run_once.py
        env:
          LINKEDIN_ACCESS_TOKEN: ${{ secrets.LINKEDIN_ACCESS_TOKEN }}
          LINKEDIN_DRY_RUN: "false"
```

---

*Generated 2026-03-28*
