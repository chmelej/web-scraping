# Gemini AI Agent - Project Documentation

## Identity & Role
I am a specialized Software Engineering Agent acting within this project to automate web scraping, parsing, and data analysis tasks. My primary objective is to deliver robust, maintainable, and idiomatic Python code using modern tooling.

## Project Technical Stack
*   **Language:** Python 3.10+
*   **Package Manager:** [uv](https://github.com/astral-sh/uv)
*   **Database:** PostgreSQL (using `psycopg2-binary`)
*   **Scraping Engine:** [Crawlee for Python](https://crawlee.dev/python/) with [Playwright](https://playwright.dev/python/)
*   **Parsing:** BeautifulSoup4, lxml, Langdetect
*   **Data Structures:** Bloom Filters (via `profusion`)
*   **Testing:** Pytest

## Core Components
### 1. Workers (`src/workers/`)
*   **Scraper (`scraper.py`):** Asynchronous worker using `PlaywrightCrawler`. Handles headless/headful browsing, retries, and result persistence.
*   **Parser (`parser.py`):** Extracts structured data (emails, phones, org numbers, social media, addresses). Implements subpage discovery.
*   **Change Detector (`change_detector.py`):** Compares successive parsing results to identify and log changes in company data.
*   **Requeue Worker (`requeue.py`):** Periodically reschedules listings for re-scraping based on configurable intervals.

### 2. Utilities (`src/utils/`)
*   **Patterns (`patterns.py`):** Country-aware regex patterns and validation logic (Modulo 97 for BE, Modulo 11 for CZ).
*   **Address (`address.py`):** Logic for extracting Belgian addresses using Bloom filters.
*   **Country (`country.py`):** Heuristics for detecting country context from URLs and language.
*   **DB (`db.py`):** Centralized connection management with autocommit enabled.

## Operating Instructions
### Running the Workers
Use the provided shell scripts for standard execution:
```bash
./run_scraper.sh
./run_parser.sh
./run_detector.sh
./run_requeue.sh
```
Or run all at once:
```bash
./run_all.sh
```

### Environment Configuration
Ensure `.env` contains valid `DATABASE_URL` and `SCRAPE_TIMEOUT_SECONDS`.

## AI-Specific Knowledge (Memory)
*   **Database Prefix:** All project tables MUST use the `scr_` prefix.
*   **Listing IDs:** Use `uni_listing_id` consistently (not `unit_listing_id`).
*   **Validation First:** Extraction of `org_num` and `phones` must include checksum validation where applicable to avoid false positives.
*   **Priority:** When `org_num` and `phones` collide on the same string, `org_num` always wins.
*   **DOM Preservation:** Do not strip `<footer>` or `<nav>` during text extraction, as they are rich sources of contact data.
