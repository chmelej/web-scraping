# Summary of Changes - Session 01

## 1. Database Refactoring
- **Table Renaming:** All tables now have the `scr_` prefix (e.g., `scr_scrape_queue`, `scr_scrape_results`).
- **Column Renaming:** Renamed `unit_listing_id` to `uni_listing_id` across all tables and code.
- **Constraints:** Adjusted code to respect the new `UNIQUE(url)` constraint on `scr_scrape_queue`.

## 2. Scraper Improvements (`src/workers/scraper.py`)
- **Crawlee Integration:** Fixed `PlaywrightCrawler` usage:
    - Passed `Request` objects instead of dictionaries.
    - Added `--no-sandbox` argument to fix crashing on Linux.
    - Implemented `failed_request_handler` to properly log and save failed requests (e.g., connection refused) to the database.
- **SQL Fixes:**
    - Corrected `fetch_batch` query to use `NOT EXISTS` and proper parameter escaping (`%%`).
    - Updated `INSERT` statements to handle `ON CONFLICT (url)` correctly.
- **Next Scrape Scheduling:** Updated `request_handler` to set `next_scrape_at` to `REQUEUE_INTERVAL_DAYS` (90 days) in the future upon successful scrape.

## 3. Parser Enhancements (`src/workers/parser.py`)
- **Footer Preservation:** Modified `extract_text_content` to **preserve** `<footer>` and `<nav>` tags, as they contain critical contact information (address, org number).
- **Subpage Discovery:** Implemented logic to discover promising subpages (contact, about, products) during parsing.
    - Added `add_subpages_to_queue` method.
    - Uses `find_promising_links` with country context.
- **Social Media Extraction:**
    - Added `extract_social_media_from_soup` to extract links directly from `href` attributes (instead of just text).
    - Expanded patterns for Facebook, Twitter/X, Instagram, LinkedIn, YouTube, and Google Business (including `business.google.com`).
- **Conflict Resolution:** Implemented logic where `org_num` takes precedence if a string is identified as both a phone number and an organization number.
- **Exit Logic:** Parser now exits cleanly when the queue is empty instead of looping indefinitely.

## 4. Pattern Matching & Validation (`src/utils/patterns.py`)
- **Country Context:**
    - Refactored `PATTERNS` to be keyed by ISO country codes (`be`, `cz`, `gb`, etc.).
    - Updated extraction functions (`extract_phones`, `extract_org_num`) to accept a `country` argument.
- **Organization Numbers (`org_num`):**
    - Renamed from `ico`.
    - **Belgium (BE):**
        - Added regex to support optional `BE` prefix (e.g., `BE0833.310.766`).
        - Implemented strict validation: 10 digits, starts with 0 or 1, range check (if starts with 0, next digit >= 2), and Modulo 97 checksum.
    - **Czechia (CZ):**
        - Implemented Modulo 11 checksum validation.
- **Phones:**
    - Improved BE phone regex to handle various formats (single digit area codes like `02`, `03`, `04`, `09`).
    - Added normalization to strip non-digits.

## 5. Address Extraction (`src/utils/address.py`)
- **Bloom Filters:**
    - Integrated `profusion` library (installed via `uv add`).
    - Implemented `AddressExtractor` using bloom filters (`be_address_streets`, `municipalities`, `post_codes`) to extract Belgian addresses from text.
    - Logic ported and adapted from old scripts.

## 6. Country Detection (`src/utils/country.py`)
- Created `detect_country(url, language)` to determine the country context based on TLD (e.g., `.be`, `.cz`) and language fallback.

## 7. Testing
- Created `tests/test_patterns.py` with comprehensive unit tests for:
    - Phone extraction (BE, CZ).
    - Org num extraction and validation (BE, CZ), including edge cases and range checks.
    - Social media extraction from HTML soup.
- Verified fixes against real data (HTML snapshots from database).

## 8. Scripts
- Created helper scripts (`run_scraper.sh`, `run_parser.sh`, etc.) using `uv run python -m ...` for easy execution.
