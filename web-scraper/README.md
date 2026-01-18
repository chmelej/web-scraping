# Web Scraper

System for scraping company data from websites.

## Setup

1. Install dependencies:
   ```bash
   pip install .
   # or with uv
   uv sync
   ```

2. Setup Database:
   - Create PostgreSQL database
   - Run migrations in `migrations/`

3. Configuration:
   - Copy `.env.example` to `.env`
   - Adjust settings

4. Run Workers:
   - `python src/workers/scraper.py`
   - `python src/workers/parser.py`
