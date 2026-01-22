# Web Scraper

System for scraping company data from websites.

## Setup

1. Install dependencies:
   ```bash
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

2. Install Playwright browser (Chromium only):
   ```bash
   uv run playwright install chromium
   ```

3. Setup Database:
   - Create PostgreSQL database
   - Run migrations in `migrations/`

4. Configuration:
   - Copy `.env.example` to `.env`
   - Adjust settings

5. Run Workers:
   - `./run_all.sh` or individual `./run_*.sh` scripts
