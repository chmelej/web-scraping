# Web Scraper

System for scraping company data from websites.

## Setup

1. Install dependencies:
   ```bash
   # Make sure to install crawlee and playwright browsers
   uv sync
   # OR
   pip install .
   playwright install
   ```

   **Important:** This project uses `crawlee` for advanced scraping.
   If you encounter `ModuleNotFoundError: No module named 'crawlee'`, run:
   ```bash
   pip install crawlee
   playwright install
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

## Troubleshooting

- **Empty results:** Check logs in `logs/` directory.
- **Crawlee missing:** Run `pip install crawlee`.
