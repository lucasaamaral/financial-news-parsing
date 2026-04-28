# Brazilian Financial News Parser

A parallel-processing pipeline to collect and enrich financial news from three major Brazilian news sources:

- **InfoMoney**
- **Valor Econômico**
- **Exame**

## 📊 Dataset

The pre-built dataset is available on Hugging Face:

**[lucasalmda/pt-br-financial-news-sentiment](https://huggingface.co/datasets/lucasalmda/pt-br-financial-news-sentiment)**

- **38,493 articles** spanning 2016-2025
- Ready for sentiment analysis, NLP tasks, and financial ML models

## Architecture

The pipeline executes **3 sequential phases** with a single command:

### Phase 1: Metadata Collection (Sitemaps) — **Parallelized**
Downloads historical sitemaps from all sources. Child-sitemap fetching runs in parallel (10 workers default) for optimal performance, but every request is still checked against each host's `robots.txt` before execution.

### Phase 2: In-Memory Pre-filter
Discards weak candidates using title, URL slug, and section — without opening any pages.

### Phase 3: Enrichment — **Parallelized**
Downloads article page metadata, performs fine-grained filtering, and persists each approved record immediately to output JSONL. Default: 8 worker threads, with `robots.txt` enforcement and per-origin pacing in the shared HTTP client.

### Robots Compliance
- The shared HTTP client identifies itself as `FinancialNewsResearchBot/1.0` instead of mimicking a browser.
- Every sitemap, redirect target, and article URL is validated against the source's `robots.txt` before cache lookup or network I/O.
- Requests are paced per origin with a minimum delay that honors the stricter value between the local default and any `Crawl-delay` or `Request-rate` rule advertised by the source.
- When a source does not advertise an explicit crawl rate, the client allows limited overlap of in-flight requests per origin instead of fully serializing the host.
- If a URL is disallowed, the fetch is aborted before any content is downloaded.

### HTTP Cache
- Persistent HTTP response caching on disk is optional.
- By default, the client keeps only in-memory `robots.txt` policy state during the current execution.
- Pass `--cache-dir .cache/` if you want to reuse downloaded sitemap or article responses across runs.

## Installation

```pwsh
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Usage

### Collect Full Dataset (2016-2025)
```pwsh
python main.py --start-date 2016-01-01 --end-date 2025-12-31
```

### Enable Persistent HTTP Cache
```pwsh
python main.py --start-date 2016-01-01 --end-date 2025-12-31 --cache-dir .cache/
```

### Collect Specific Period
```pwsh
python main.py --start-date 2025-01-01 --end-date 2025-12-31
```

### Resume Previous Run
```pwsh
python main.py --start-date 2016-01-01 --end-date 2025-12-31 --resume
```

### Adjust Parallelization
```pwsh
python main.py --start-date 2025-01-01 --end-date 2025-12-31 --workers 4
```

## Project Structure

```
financial-news-parsing/
├── main.py                  # Entry point
├── README.md               # Documentation
├── LICENSE                 # MIT License
├── requirements.txt        # Python dependencies
├── data/
│   ├── financial_news_br.jsonl  # Brazilian financial news dataset
│   └── financial.jsonl          # Enriched financial news data
├── domain/
│   ├── __init__.py         # Package initialization
│   ├── config.py           # Global settings, keyword lists, filtering thresholds
│   └── models.py           # Data models (CandidateArticle, ArticleRecord, FilterContext)
├── fetcher/
│   ├── __init__.py         # Package initialization
│   ├── client.py           # HTTP client with disk cache, robots enforcement, and per-origin pacing
│   ├── adapters.py         # Adapters per source (InfoMoney, Valor, Exame)
│   └── sitemaps.py         # XML sitemap parser
├── pipeline/
│   ├── __init__.py         # Package initialization
│   ├── collection.py       # Phases 1 & 2 (collection + pre-filter)
│   └── enrichment.py       # Phase 3 (parallel enrichment + fine-grained filtering)
└── processing/
    ├── __init__.py         # Package initialization
    ├── extractor.py        # HTML metadata extraction (title, description, tags)
    ├── analyzer.py         # Financial signal counting helpers
    ├── filters.py          # Multi-stage relevance filtering logic
    └── text.py             # Text normalization and URL utilities
```

## Output Format (JSONL)

Each line is a JSON object with the following fields:

```json
{
  "source": "Valor Econômico",
  "url": "https://valor.globo.com/financas/...",
  "published_at": "2025-04-21T10:30:00+00:00",
  "week_key": "2025-W17",
  "week_start": "2025-04-21",
  "week_end": "2025-04-27",
  "tags": ["Ibovespa", "Selic", "Banco Central"],
  "title": "Article Headline",
  "description": "Subtitle or summary line",
  "sentiment_text": "Titulo: Article Headline\nResumo: Subtitle or summary line"
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | News outlet: `"InfoMoney"`, `"Valor Econômico"`, or `"Exame"` |
| `url` | string | Article URL (may redirect) |
| `published_at` | ISO 8601 | Publication timestamp (UTC) |
| `week_key` | string | ISO week format (e.g., `"2025-W17"`) |
| `week_start` | date | Week start date (YYYY-MM-DD) |
| `week_end` | date | Week end date (YYYY-MM-DD) |
| `tags` | array[string] | Editorial tags/keywords |
| `title` | string | Article headline |
| `description` | string \| null | Subtitle or summary |
| `sentiment_text` | string | Derived text for sentiment tasks: title plus description when available |

## Relevance Filtering

The pipeline uses multi-stage filtering to ensure high-quality financial news:

### Pre-Filter (Title & URL only)
- ✅ Requires focused financial topic signals (keywords such as ibovespa, selic, cambio, juros, tesouro, etc.)
- ✅ Rewards direct Brazil market context and clear financial-strength signals
- ✅ Allows technical-analysis pieces when they are anchored in Brazilian market instruments
- ❌ Rejects: individual corporate announcements/results, exterior-only stories, editorial pieces, roundups, live coverage

### Fine-Grained Filter (Page Metadata)
- Analyzes extracted page metadata: title, description, tags, and section from HTML/JSON-LD
- Validates financial relevance with multi-pass keyword analysis over metadata only
- Filters editorial recommendations, roundups, and exterior-only coverage
- Re-checks direct Brazil market context from headline/description/tag surface

### Rejected Categories
- **Corporate announcements:** dividend/earnings releases, equity offerings, debenture issuances (matched by headline patterns)
- **Exterior-only coverage:** international stories without direct Brazil market context (no Brazil keywords detected)
- **Editorial content:** columnist pieces and opinion-driven articles (detected by URL path patterns)
- **Roundups & live coverage:** "latest news" compilations, live event coverage (generic title markers)

## 📜 License

MIT. Articles sourced from copyright-protected publications (InfoMoney, Valor Econômico, Exame) — research and educational use only.