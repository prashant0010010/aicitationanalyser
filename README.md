# AI Citation Analyser

A local-first Python application that analyses how clearly, specifically and attributably a brand, organisation, product or website is represented for a target query, in the way that matters for AI-generated search experiences. It scores the entity on a 16-metric framework, explains every score with evidence, and produces a structured PDF report.

It is a GEO (generative engine optimisation) analysis tool, not a traditional SEO audit. It looks at retrievability, extractability, information quality, entity clarity, source attribution, cross-platform representation and query relevance. It does not use rankings, backlinks or organic sessions, and it does **not** claim to know how any AI search engine ranks or retrieves content. It measures observable properties of the content and sources you give it.

**No API key is required.** Without one, everything except the optional AI suggestions runs locally.

---

## Contents

1. [Who it is for](#who-it-is-for)
2. [What it does and the core workflow](#what-it-does-and-the-core-workflow)
3. [Quick start](#quick-start)
4. [Installation](#installation)
5. [API keys and free configuration](#api-keys-and-free-configuration)
6. [Running the application](#running-the-application)
7. [How to run an analysis](#how-to-run-an-analysis)
8. [The 16-metric framework](#the-16-metric-framework)
9. [How the Citation Quality Score is calculated](#how-the-citation-quality-score-is-calculated)
10. [Recommendations and priority](#recommendations-and-priority)
11. [PDF report](#pdf-report)
12. [Architecture and project structure](#architecture-and-project-structure)
13. [Running tests](#running-tests)
14. [Deployment](#deployment)
15. [Security](#security)
16. [Troubleshooting](#troubleshooting)
17. [Environment variables](#environment-variables)
18. [Limitations](#limitations)
19. [Extending the application](#extending-the-application)
20. [Verification status](#verification-status)
21. [License](#license)

---

## Who it is for

Digital and SEO strategists, GEO practitioners, content strategists, marketing directors and researchers who need explainable evidence for questions such as: *Is our page structured so an answer can be lifted from it? Is the entity clearly defined? Do independent sources corroborate it? Where are we absent from the answers people see?*

## What it does and the core workflow

```
New Analysis -> Source Collection -> Analysis -> Results -> Citation Opportunities -> Report (PDF)
```

| Step | Page | What happens |
|---|---|---|
| 1 | New Analysis | Define the target query, entity, website, industry, market, optional competitors and optional extra queries. |
| 2 | Source Collection | Fetch a URL or paste content for the target. Add external source URLs or pasted content. Paste real AI answers with their citation lists. |
| 3 | Analysis | Clean and normalise content, run semantic, structural, information, entity, authority and citation analysis, compute the score, build recommendations. |
| 4 | Results | See the Citation Quality Score, four pillar scores and all 16 metrics with evidence, method and interpretation. |
| 5 | Citation Opportunities | Prioritised actions, opportunities by type, AI answer analysis, evidence gaps. |
| 6 | Report | Generate and download the PDF. |

Supporting pages: **Methodology** (how scoring works, rendered from the live configuration) and **Settings** (providers, models, session-only keys, pillar weights).

A tracker at the top of each page shows where you are and what comes next. Pages that need earlier steps tell you which page to visit.

---

## Quick start

macOS / Linux:

```bash
unzip AI_Citation_Analyser.zip && cd AI_Citation_Analyser
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Windows PowerShell:

```powershell
Expand-Archive AI_Citation_Analyser.zip -DestinationPath .
cd AI_Citation_Analyser
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Then open **New Analysis** and click **Load demo data** to walk through the whole workflow with a clearly labelled fictional example.

## Installation

Requirements: Python 3.10 or newer (3.12 recommended), about 300 MB of disk for the core install.

### Windows (PowerShell)

```powershell
cd path\to\AI_Citation_Analyser
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env      # optional: only needed if you want AI suggestions
streamlit run app.py
```

If PowerShell refuses to run the activation script, run this once for your user and retry:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Command Prompt users activate with `.venv\Scripts\activate.bat`.

### macOS / Linux

```bash
cd path/to/AI_Citation_Analyser
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env             # optional
streamlit run app.py
```

### Optional: sentence embeddings (stronger semantic similarity)

The default similarity engine is TF-IDF with cosine similarity, which needs no download but measures weighted term overlap. For paraphrase-aware similarity install the optional package (large: pulls in PyTorch, downloads about 90 MB on first use):

```powershell
pip install -r requirements-semantic.txt
```

The engine detects it automatically (`SEMANTIC_BACKEND=auto`). The backend actually used is always shown in the results and printed in the report. Change the model with `EMBEDDING_MODEL`.

### Installation check without the UI

```powershell
python scripts\run_cli_demo.py
```

This runs the demo analysis and writes a PDF to `reports/`.

---

## API keys and free configuration

**Every key is optional.** Do not put real keys in any file that you commit. `.env`, `.streamlit/secrets.toml` and `reports/` are already in `.gitignore`.

### What works with no keys

HTML fetching and extraction, content cleaning, heading, chunk and schema analysis, fact and entity extraction (rule-based), TF-IDF semantic similarity, query-adaptive coverage, third-party mention and source diversity analysis for sources you supply, AI answer analysis for answers you paste, scoring, recommendations and PDF generation.

### What the optional keys add

| Key | Purpose | Cost |
|---|---|---|
| `GEMINI_API_KEY` | AI-suggested subtopics for the coverage metric and an optional strategic commentary in the report | Google AI Studio offers a free tier. Check Google's current terms and rate limits. |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | Same as above, for users who already hold such a key | Paid. Not required. |
| `SEARCH_PROVIDER` plus `SEARCH_API_KEY` (and `SEARCH_ENGINE_ID` for `google_cse`) | Suggest candidate external sources from a web search | Provider-dependent. Check each provider's current free-tier availability. |

AI output **never changes a score**. It is validated against a schema before use, labelled as AI-generated in the report, and if a provider fails, is rate limited or returns malformed JSON, the analysis continues locally and says: *"AI enhancement unavailable. Local analysis has been used."* (or a message naming the failure).

### Where each key goes

Pick one of these:

1. **`.env` file (local, recommended).** Copy `.env.example` to `.env` in the project root and replace the placeholder for the provider you use:
   ```
   GEMINI_API_KEY=your-real-key
   ```
2. **Environment variable** in your shell, for example in PowerShell: `$env:GEMINI_API_KEY = "your-real-key"` before `streamlit run app.py`.
3. **Streamlit secrets.** Locally copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml`. On Streamlit Community Cloud paste the same content into *App settings, Secrets*.
4. **Session only.** *Settings, Use a key for this browser session only* holds a Gemini key in memory for the current session. It is not written to disk.

Keys are never displayed in the UI. The Settings page only shows whether a key is configured. Use *Settings, Test connection* to confirm a key works.

Get a free Gemini key in Google AI Studio (search for "Google AI Studio API key"), then set `AI_PROVIDER=auto` or `AI_PROVIDER=gemini`. Set `AI_PROVIDER=none` to force local-only mode.

---

## Running the application

```powershell
.venv\Scripts\Activate.ps1
streamlit run app.py
```

Streamlit opens `http://localhost:8501`. Stop it with `Ctrl+C`.

## How to run an analysis

1. **New Analysis.** Enter the query (for example `best accounting software for small businesses`), the entity name exactly as it should appear, the website, industry and market. Optionally add competitors, one per line (`Name, domain.com` lets competitor citations be recognised), and extra queries.
2. **Source Collection.**
   - *Target:* enter the page URL, or paste the content or HTML. Pasted content wins if both are present. Use pasting when a site blocks automated access or needs JavaScript.
   - *External sources:* URLs, one per line, or pasted content with an optional URL so the source type can be classified.
   - *AI answers:* paste a real answer for your query and its citation list (one URL or `Title - URL` per line). The application never fetches AI answers itself.
   - Click **Start collection** and review the table of what was read, failed or truncated.
3. **Analysis.** Click **Run analysis**. Progress is shown per stage. Toggle AI enhancement off if you want a strictly local run.
4. **Results.** Review the score, pillars and each metric's evidence, calculation and recommendation. Download the raw results as JSON if you like.
5. **Citation Opportunities.** Work from the priority matrix.
6. **Report.** Click **Generate Report**, then **Download PDF report**.

---

## The 16-metric framework

This is the application's own analytical framework. It is not an industry standard. Every metric reports a score from 0 to 100, its raw evidence, the calculation method, an interpretation and recommendations. Each is labelled **measured** (directly observed), **proxy** (indirect signal), **estimate** (modelled judgement) or **unavailable** (evidence not supplied; never invented).

| # | Metric | Pillar | Basis | Needs |
|---|---|---|---|---|
| 1 | Direct Answer / BLUF Strength | Structural Extractability | measured | Target content, query |
| 2 | Heading Hierarchy | Structural Extractability | measured | Target content |
| 3 | Content Chunkability | Structural Extractability | measured | Target content |
| 4 | Structured Data / Machine Readability | Structural Extractability | measured | Target HTML (plain text gives "unavailable") |
| 5 | Information Density | Fact and Information Density | measured | Target content, query |
| 6 | Fact Density | Fact and Information Density | measured | Target content |
| 7 | Evidence Attribution | Fact and Information Density | proxy | Target content ("unavailable" if no claims found) |
| 8 | Information Coverage | Fact and Information Density | proxy | Target content, query |
| 9 | Entity Presence | Entity Clarity and Relationship Mapping | measured | Target content, entity |
| 10 | Entity Clarity | Entity Clarity and Relationship Mapping | measured | Target content, entity |
| 11 | Entity Relationships | Entity Clarity and Relationship Mapping | measured | Target content, entity |
| 12 | Contextual Relevance | Entity Clarity and Relationship Mapping | measured | Target content, entity, query |
| 13 | Third-Party Mentions | Cross-Platform Authority | measured | External sources |
| 14 | Source Diversity | Cross-Platform Authority | measured | External sources |
| 15 | Citation Share | Cross-Platform Authority | measured (proxy if only mention share) | AI answers with citations |
| 16 | AI Referral Value / Citation Value | Cross-Platform Authority | **estimate** | Query and entity (optional answers, sources) |

The exact formula for each metric is in `config/scoring.py` and is shown on the **Methodology** page. Highlights:

- **Metric 1** combines the semantic relevance and length of the opening answer with the share of question-style headings followed by a concise (8 to 80 word) answer.
- **Metric 6** counts deterministic fact patterns (percentages, currency, dates, measurements, quantities, definitions, comparisons, named organisations) per 100 words.
- **Metric 8** builds a subtopic list from the query's intent, the query's own key phrases and optional AI suggestions, then checks each with keyword evidence plus semantic similarity.
- **Metric 15** uses only the answers you supplied: target-domain citations over all citations, and target mentions over target plus competitor mentions.
- **Metric 16** blends query intent value, entity relevance, supplied source relevance and best citation prominence. It uses no search volume or traffic data and is labelled an estimate.

## How the Citation Quality Score is calculated

```
metric score (0-100)  ->  pillar score  ->  Citation Quality Score (0-100)
```

1. A **pillar score** is the weighted mean of the pillar's available metrics. Weights come from `METRICS[n]["weight"]` in `config/scoring.py` and are **renormalised over the metrics that have evidence**, so a missing source never counts as a zero.
2. A pillar needs at least one **measured or proxy** metric to be scored. Metric 16 is an estimate and does not count, so Cross-Platform Authority is "not scored" when no external sources or AI answers exist.
3. The **Citation Quality Score** is the weighted mean of the scored pillars (default weights 0.25 each, in `PILLARS`). If any pillar could not be scored the score is flagged **provisional** in the UI and the PDF.
4. Bands: Strong 85 and above, Good 70, Developing 50, Weak 30, Very weak below 30.
5. Every run records a **calculation trace** (visible in Results and the PDF) such as `Structural Extractability = 90.4 (M1 100 x 0.30, M2 83 x 0.20, ...)`.

Change weights centrally in `config/scoring.py`, or per session with the sliders in **Settings**. Calibration targets (for example the fact density target of 3 per 100 words, or the 40 percent share that earns full Citation Share marks) are in `CALIBRATION` in the same file.

## Recommendations and priority

Each metric below 75 with actionable findings yields one recommendation containing: observed evidence, why it matters, recommended action (written from the evidence, for example naming the exact unattributed claim or missing subtopics), expected effect, priority and horizon.

Priority is calculated, not assigned: a weighted sum of six factors between 0 and 1.

| Factor | Weight | Meaning |
|---|---|---|
| weakness | 0.35 | Distance of the score from 100 |
| impact | 0.20 | The metric's weight in the overall score |
| query importance | 0.15 | Intent value of the query (commercial 1.0 down to navigational 0.45) |
| entity relevance | 0.10 | How relevant the entity already is, so effort is worth investing |
| effort | 0.10 | Lower effort scores higher |
| evidence strength | 0.10 | Measured 1.0, proxy 0.7, estimate 0.4 |

High is 0.72 or above, Medium 0.55 or above, otherwise Low. Horizon is Immediate for low-effort items of High or Medium priority, Strategic for sustained programmes, Near-term otherwise. All values are in `config/scoring.py`, and the full factor breakdown appears in the Citation Opportunities page and in the PDF's priority matrix.

Citation opportunities additionally come from real supplied data: answers where the entity is absent, cited sources that do not mention the entity, mentions with no visible source, and relevant external pages that discuss the topic without naming the entity.

---

## PDF report

Click **Generate Report** on the Report page. The PDF is built with ReportLab from structured data (it is not a screenshot) and is offered through a download button. A copy is also written to the `reports/` folder (configurable with `REPORT_DIR`) when the filesystem allows. Filename pattern:

```
AI_Citation_Analysis_<entity>_<date>.pdf
```

Structure:

1. Cover block: entity, query, market, website, date, analysis mode and semantic backend (and a prominent DEMO DATA notice when applicable)
2. Executive summary, Citation Quality Score and pillar table on the first page
3. Score calculation trace and the 16-metric overview
4. Important findings: strengths, weaknesses, evidence gaps
5. The 16 metrics in detail: score, evidence, calculation, components, interpretation, recommendation
6. Opportunities: citation, content, entity, authority, technical
7. Recommended actions: priority matrix with factor breakdown, per-recommendation detail (evidence, why it matters, action, expected effect, priority) and an action plan (Immediate, Near-term, Strategic)
8. AI answer analysis, external sources and query set, when supplied
9. AI-generated commentary (only if an AI provider produced one, clearly labelled)
10. Methodology and limitations
11. Data sources
12. Appendix: detected entities, relationships, subtopic checklist, configuration used

Page numbers and report metadata are in the footer. Em dashes and arrow symbols are stripped from report text.

---

## Architecture and project structure

The analysis engine is independent of Streamlit. Pages only collect input and render results.

```
AI_Citation_Analyser/
  app.py                     Streamlit entry point and navigation
  pages/                     One file per page (home, new_analysis, source_collection,
                             analysis, results, citation_opportunities, report,
                             methodology, settings)
  components/ui.py           Session access, headers, workflow tracker, stage guards
  config/
    settings.py              Env, .env and Streamlit secrets loading (never logs secrets)
    scoring.py               Pillar and metric weights, calibration, bands, priority formula
    lexicons.py              Word lists and pattern libraries (filler, relationships, facets...)
  models/schemas.py          Typed dataclasses: ProjectInput, Document, MetricResult,
                             Recommendation, AnalysisResults, AnalysisSession
  collectors/
    url_collector.py         Safe fetch (SSRF checks per redirect, size and time limits),
                             HTML extraction, pasted-content handling
    source_collector.py      Collects target and external sources, classifies source types
    search_collector.py      Optional search API (Brave, Google CSE) for candidate sources
  analyzers/
    semantic_analyzer.py     TF-IDF or sentence-embedding engine, cosine similarity, clustering
    structural_analyzer.py   Metrics 1 to 4
    information_analyzer.py  Metrics 5 to 8, fact patterns, query-adaptive facets
    entity_analyzer.py       Entity extraction, roles, relationships, metrics 9 to 12
    authority_analyzer.py    Metrics 13 to 16
    citation_analyzer.py     Parsing and analysis of supplied AI answers
    base.py                  AnalysisContext and shared helpers
  providers/                 AI abstraction: base.py, gemini.py, openai.py, anthropic.py
  core/
    pipeline.py              End-to-end analysis, per-metric fault isolation
    scoring.py               Pillar and overall score calculation with trace
    recommendations.py       Evidence-linked recommendations, priority, opportunities
    enhance.py               Optional validated AI subtopics and commentary
    demo.py                  Loads the bundled fictional demo
  reporting/                 pdf_report.py (ReportLab) and narrative.py
  utils/                     text, urls, query, security (URL validation), cache
  data/                      Demo inputs and sample_analysis.json (all fictional and labelled)
  scripts/                   run_cli_demo.py, regenerate_sample.py
  tests/                     pytest suite
  reports/                   Generated PDFs (git-ignored)
  .streamlit/                config.toml and secrets.example.toml
  requirements.txt, requirements-semantic.txt, .env.example, .gitignore,
  runtime.txt, pytest.ini, LICENSE
```

Design points worth knowing:

- **Each metric is a function** `fn(ctx) -> MetricResult` registered in its module's `METRICS` dict. The pipeline runs all 16 and converts any exception into an "unavailable" metric, so one failure never stops the run.
- **The semantic engine has one interface and two backends.** All thresholds are calibrated per backend in `CALIBRATION`.
- **Entity extraction is rule-based** (capitalisation, suffixes, gazetteers, relationship patterns). It is an approximation of NER and is described that way in the report.
- **Caching:** fetched pages (TTL cache, `CACHE_TTL_SECONDS`), embeddings (per text hash), the semantic engine instance, and AI calls are cached in process.
- **Session state:** one `AnalysisSession` object holds project input, collected documents, AI answers, results and timestamps, so navigating between pages never loses work. Content is capped by `MAX_CONTENT_CHARS`.

---

## Running tests

```powershell
.venv\Scripts\Activate.ps1
python -m pytest -q
```

The suite (about 50 tests, a few seconds, no network or API keys needed) covers URL extraction and cleaning, SSRF validation including redirects to private addresses, cosine similarity, entity and relationship extraction, fact patterns, all 16 metrics on the demo, unavailable-metric behaviour, score maths and renormalisation, recommendation priority, AI answer analysis, provider error handling (mocked), configuration loading, PDF generation and content, and a check that user-facing text contains no em dashes or arrows.

## Deployment

### Streamlit Community Cloud

1. Push the project to a GitHub repository. Confirm `.env`, `.streamlit/secrets.toml` and `reports/` are not committed.
2. In Streamlit Community Cloud choose *New app*, select the repository, and set the main file to `app.py`.
3. In *Advanced settings* choose Python 3.12 (matching `runtime.txt`) and paste any keys into *Secrets* using the format in `.streamlit/secrets.example.toml`.
4. Deploy. The default `requirements.txt` is deliberately light. **Do not** use `requirements-semantic.txt` on the free tier because PyTorch is too heavy. TF-IDF mode is used automatically.

Notes for hosted use: generated PDFs are delivered through the download button because the cloud filesystem is temporary. Some sites block data-centre IP addresses, so pasting content is the reliable fallback. Session data lives in memory per browser session. There is no database and no login.

### Other hosts

Any host that can run `streamlit run app.py --server.port $PORT --server.address 0.0.0.0` works (for example a small VM or container). Provide keys as environment variables. Put the app behind authentication if it is exposed publicly, because it fetches URLs on behalf of users.

## Security

- No keys are stored in the project. Keys come from the environment, `.env`, or Streamlit secrets, are never rendered in the UI, never logged, and are sent to providers in headers (not URLs).
- **URL fetching is restricted:** only http and https, no embedded credentials, only ports 80, 443, 8080 and 8443, hostnames are resolved and rejected if any address is private, loopback, link-local or reserved, redirects are followed manually with the same checks on every hop (maximum 5), downloads are capped in size and time, and only HTML and text content types are accepted. A DNS rebinding race between validation and connection is a known residual risk of this approach, so avoid exposing the app publicly without authentication.
- Pasted and fetched content is length-capped and stripped of control characters. HTML is parsed, never executed. No user-supplied code is run. Streamlit renders analysed text as plain text, not HTML.
- Set `ALLOW_PRIVATE_URLS=true` only on a private machine, and only if you need to analyse intranet pages.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `streamlit` is not recognised | The virtual environment is not active. Run `.venv\Scripts\Activate.ps1` (Windows) or `source .venv/bin/activate`. |
| PowerShell blocks `Activate.ps1` | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| "The site blocked automated access (HTTP 403)" | The site refuses automated requests. Open the page in your browser, copy the content or HTML, and paste it. |
| "Very little readable text was found" | The page probably renders with JavaScript. Paste the rendered content instead. |
| "URL rejected: ..." | The URL points to a private or unsupported destination. See Security. |
| "The request timed out" | Raise `REQUEST_TIMEOUT` or paste the content. |
| "AI enhancement unavailable. Local analysis has been used." | No provider key is configured. This is normal. Add a key only if you want AI subtopics and commentary. |
| "rate limit or free-tier quota reached" | Wait and retry, or switch off AI enhancement on the Analysis page. The score is unaffected. |
| "the API key was rejected" | Check the key and that it is for the provider named. Use *Settings, Test connection*. |
| "Request rejected (HTTP 400/404). Check the model name." | Model names change over time. Update `GEMINI_MODEL`, `OPENAI_MODEL` or `ANTHROPIC_MODEL`. |
| Sentence-transformers message, TF-IDF used | The optional package or model is unavailable. Install `requirements-semantic.txt` and make sure the machine can download the model once. |
| Authority metrics show "Requires external sources" | Add external URLs or pasted sources (13, 14) or AI answers with citations (15). They are intentionally never estimated. |
| Score marked provisional | At least one pillar could not be scored because its evidence is missing. |
| PDF generation failed | Check the message shown. Make sure `reportlab` is installed (`pip install -r requirements.txt`). |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` inside the active virtual environment. |
| Port already in use | `streamlit run app.py --server.port 8502` |

Set `DEBUG=true` to see detailed logs in the terminal. Tracebacks are never shown in the UI.

## Environment variables

All optional. Defaults in parentheses. See `.env.example`.

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | Optional AI providers (none) |
| `AI_PROVIDER` | `auto`, `gemini`, `openai`, `anthropic`, `none` (auto) |
| `GEMINI_MODEL`, `OPENAI_MODEL`, `ANTHROPIC_MODEL` | Model names (gemini-2.5-flash, gpt-4o-mini, claude-haiku-4-5) |
| `SEARCH_PROVIDER` | `none`, `brave`, `google_cse` (none) |
| `SEARCH_API_KEY`, `SEARCH_ENGINE_ID` | Search provider credentials (none) |
| `SEMANTIC_BACKEND` | `auto`, `sbert`, `tfidf` (auto) |
| `EMBEDDING_MODEL` | Sentence-transformers model (sentence-transformers/all-MiniLM-L6-v2) |
| `REQUEST_TIMEOUT` | Seconds per fetch (15) |
| `MAX_CONTENT_CHARS` | Content cap per page (200000) |
| `MAX_DOWNLOAD_BYTES` | Download cap per page (3000000) |
| `MAX_EXTERNAL_SOURCES` | Cap on external URLs (15) |
| `CACHE_TTL_SECONDS` | Fetch cache lifetime (3600) |
| `REPORT_DIR` | Where PDFs are saved (reports) |
| `ALLOW_PRIVATE_URLS` | Disable SSRF protection, private use only (false) |
| `DEBUG` | Verbose logging (false) |

## Limitations

- Fact and entity extraction is pattern-based. It can miss entities and misclassify some types, and it is tuned for English.
- Authority metrics (13 to 15) describe only the sources and answers you supply. They are not measures of the whole web or of all AI answers, and the application cannot see private or proprietary AI search results.
- Source types come from domain rules and will sometimes label unusual domains as "Other web source".
- Metric 16 is an estimate that uses no search volume, traffic or conversion data.
- TF-IDF similarity measures weighted term overlap. Install sentence embeddings for a stronger semantic signal.
- No domain authority, backlink counts or proprietary SEO metrics are used, because they cannot be measured reliably without paid data.
- Scores indicate the presence of characteristics associated with usefulness as a source. They do not predict that a specific AI system will cite an entity.
- Pages that block bots or require JavaScript may need pasted content. Extraction is a general-purpose heuristic and can mis-handle unusual layouts.

## Extending the application

Clean extension points exist for:

| Goal | Where |
|---|---|
| Add or reweight a metric | Add a function to a module's `METRICS` dict and an entry in `config/scoring.py` |
| Change thresholds and weights | `config/scoring.py` |
| Add an AI provider | Subclass `AIProvider` in `providers/`, register it in `providers/__init__.py` |
| Add a search or SERP source | Add a function to `collectors/search_collector.py` |
| Collect AI answers automatically | Implement a collector that returns `AIAnswer` objects and attach them to `session.answers` |
| Competitor benchmarking | Run the pipeline per competitor page and compare `MetricResult` lists |
| Historical tracking and multi-project | Persist `AnalysisSession.to_dict()` to a database keyed by project |
| Scheduled analysis | Call `collect_all` and `analyse` from `scripts/run_cli_demo.py` style scripts |
| New report sections | Add to `reporting/pdf_report.py` |

## Verification status

Honest notes on what was and was not exercised when this project was built:

- **Verified:** the full workflow end to end on the bundled demo (collection, analysis, results, opportunities, PDF generation and download) through Streamlit's AppTest harness, the whole test suite, and PDF content and rendering.
- **Not verified in the build environment:** fetching real public URLs (the build sandbox had no general internet access, so network paths were tested with mocks and SSRF checks only), live calls to Gemini, OpenAI, Anthropic, Brave or Google CSE (tested with mocked responses), and the optional sentence-transformers backend (not installable there, so the fallback path was tested). Please try a real URL and, if you use one, a real key as your first acceptance test, and report any provider response format changes.
- Provider model names and free-tier terms change. Verify them in each provider's current documentation.

 
