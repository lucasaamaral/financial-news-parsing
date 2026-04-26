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
Downloads historical sitemaps from all sources. Child-sitemap fetching runs in parallel (10 workers default) for optimal performance.

### Phase 2: In-Memory Pre-filter
Discards weak candidates using title, URL slug, and section — without opening any pages.

### Phase 3: Enrichment — **Parallelized**
Downloads and performs fine-grained filtering on promising candidates, persisting each approved record immediately to output JSONL. Default: 8 worker threads.

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

### Metadata Only (No Article Body)
```pwsh
python main.py --start-date 2025-01-01 --end-date 2025-12-31 --metadata-only
```

## Project Structure

```
financial-news-parsing/
├── main.py                  # Entry point
├── domain/
│   ├── config.py           # Global settings, keyword lists, filtering thresholds
│   └── models.py           # Data models (CandidateArticle, ArticleRecord, FilterContext)
├── fetcher/
│   ├── client.py           # HTTP client with disk-based cache
│   ├── adapters.py         # Adapters per source (InfoMoney, Valor, Exame)
│   └── sitemaps.py         # XML sitemap parser
├── pipeline/
│   ├── collection.py       # Phases 1 & 2 (collection + pre-filter)
│   └── enrichment.py       # Phase 3 (parallel enrichment + fine-grained filtering)
├── processing/
│   ├── extractor.py        # HTML extraction (title, lead, authors, tags, etc)
│   ├── analyzer.py         # Financial signal counting helpers
│   ├── filters.py          # Multi-stage relevance filtering logic
│   └── text.py             # Text normalization and utilities
```

## Output Format (JSONL)

Each line is a JSON object with the following fields:

```json
{
  "source": "Valor Econômico",
  "url": "https://valor.globo.com/financas/...",
  "section": "mercados",
  "authors": ["Reporter Name"],
  "tags": ["Ibovespa", "Selic", "Banco Central"],
  "title": "Article Headline",
  "description": "Subtitle or summary line",
  "lead": "First substantive paragraph (bylines removed)",
  "sentiment_text": "Title + Description + Lead (ready for sentiment analysis)",
  "published_at": "2025-04-21T10:30:00+00:00",
  "week_key": "2025-W17",
  "week_start": "2025-04-21",
  "week_end": "2025-04-27",
  "weekday": 0
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | News outlet: `"InfoMoney"`, `"Valor Econômico"`, or `"Exame"` |
| `url` | string | Article URL (may redirect) |
| `section` | string \| null | Website section slug (e.g., `"mercados"`, `"economia"`) |
| `authors` | array[string] | Extracted author names |
| `tags` | array[string] | Editorial tags/keywords |
| `title` | string | Article headline |
| `description` | string \| null | Subtitle or summary |
| `lead` | string \| null | First paragraph of body text |
| `sentiment_text` | string | Concatenated title + description + lead for sentiment classifiers |
| `published_at` | ISO 8601 | Publication timestamp (UTC) |
| `week_key` | string | ISO week format (e.g., `"2025-W17"`) |
| `week_start` | date | Week start date (YYYY-MM-DD) |
| `week_end` | date | Week end date (YYYY-MM-DD) |
| `weekday` | int | Day of week (0=Monday, 6=Sunday) |

## Relevance Filtering

The pipeline uses multi-stage filtering to ensure high-quality financial news:

### Pre-Filter (Title & URL only)
- ✅ Requires focused financial topic signals (keywords such as ibovespa, selic, cambio, juros, tesouro, etc.)
- ✅ Rewards direct Brazil market context and clear financial-strength signals
- ✅ Allows technical-analysis pieces when they are anchored in Brazilian market instruments
- ❌ Rejects: individual corporate announcements/results, exterior-only stories, editorial pieces, roundups, live coverage

### Fine-Grained Filter (Full Article)
- Analyzes title, description, lead paragraph, and body text
- Validates financial relevance with multi-pass keyword analysis
- Filters sponsored content, editorial recommendations, roundups, and exterior-only coverage
- Re-checks direct Brazil market context from the headline/lead/tag surface

### Rejected Categories
- Corporate announcements: dividend/earnings releases, equity offerings, company operational updates, debenture issuances
- Exterior-only coverage: international stories without direct Brazil market context
- Editorial content: columnist recommendations, opinion pieces
- Sponsored content: content marked as institutional partnership
- Roundups: live event coverage, "latest news" compilations

## 📜 License

MIT. Articles sourced from copyright-protected publications (InfoMoney, Valor Econômico, Exame) — research and educational use only.