# Web Scraper - Administrátorský manuál

## Obsah

1. [Požadavky na systém](#požadavky-na-systém)
2. [Instalace](#instalace)
3. [Konfigurace](#konfigurace)
4. [První spuštění](#první-spuštění)
5. [Provoz aplikace](#provoz-aplikace)
6. [Monitoring a diagnostika](#monitoring-a-diagnostika)
7. [Údržba](#údržba)
8. [Řešení problémů](#řešení-problémů)
9. [Backup a obnova](#backup-a-obnova)
10. [Bezpečnost](#bezpečnost)

---

## Požadavky na systém

### Hardware minimální konfigurace
* **CPU:** 2 cores
* **RAM:** 4 GB (doporučeno 8 GB)
* **Disk:** 50 GB volného místa (SSD doporučeno)
* **Síť:** Stabilní připojení k internetu

### Software
* **OS:** Linux (Ubuntu 22.04 LTS nebo Debian 11+) nebo macOS
* **Python:** 3.10+
* **PostgreSQL:** 14+
* **Git:** pro instalaci z repository

### Volitelné
* **Ollama:** pro lokální LLM modely (šetří náklady na API)
* **Systemd:** pro automatický běh workerů (Linux)

---

## Instalace

### 1. Příprava systému

```bash
# Update systému
sudo apt update && sudo apt upgrade -y

# Instalace závislostí
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib git curl

# Instalace UV (moderní Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

### 2. PostgreSQL setup

```bash
# Zapni PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Vytvoř databázi a uživatele
sudo -u postgres psql <<EOF
CREATE USER scraper_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE web_scraper OWNER scraper_user;
GRANT ALL PRIVILEGES ON DATABASE web_scraper TO scraper_user;
\q
EOF

# Test připojení
psql -U scraper_user -d web_scraper -h localhost
```

### 3. Stažení aplikace

```bash
# Vytvoř adresář pro aplikaci
sudo mkdir -p /opt/web-scraper
sudo chown $USER:$USER /opt/web-scraper
cd /opt/web-scraper

# Clone repository
git clone https://github.com/your-repo/web-scraper.git .
```

### 4. Python prostředí

```bash
# Vytvoř virtual environment pomocí UV
uv venv
source .venv/bin/activate

# Instaluj dependencies
uv sync

# Nebo pokud nemáš pyproject.toml s UV
uv pip install psycopg2-binary playwright beautifulsoup4 lxml langdetect \
              spacy click pyyaml python-dotenv phonenumbers pybloom-live

# Stáhni spaCy jazykové modely (jen co potřebuješ)
uv run python -m spacy download cs_core_news_lg  # čeština
uv run python -m spacy download en_core_web_lg   # angličtina

# Instaluj Playwright prohlížeče
uv run playwright install chromium
```

### 5. Databázové migrace

```bash
# Aplikuj schema
psql -U scraper_user -d web_scraper -h localhost < migrations/001_initial_schema.sql

# Seed data (prompty, config)
psql -U scraper_user -d web_scraper -h localhost < migrations/002_seed_prompts.sql

# Monitoring views
psql -U scraper_user -d web_scraper -h localhost < migrations/003_monitoring_views.sql
```

---

## Konfigurace

### 1. Hlavní konfigurační soubor (.env)

```bash
cp .env.example .env
nano .env
```

**Obsah .env:**
```bash
# === Database ===
DATABASE_URL=postgresql://scraper_user:your_secure_password@localhost:5432/web_scraper

# === Scraping nastavení ===
SCRAPE_DELAY_SECONDS=2          # Delay mezi requesty na stejnou doménu
MAX_RETRIES=3                    # Počet opakování při selhání
PLAYWRIGHT_HEADLESS=true         # Headless browser mode
USER_AGENT=Mozilla/5.0 (compatible; YourBot/1.0; +https://yoursite.com/bot-info)

# === API klíče (volitelné) ===
# Pro LLM - pokud nepoužíváš Ollama
ANTHROPIC_API_KEY=sk-ant-...    # Claude API
OPENAI_API_KEY=sk-...            # OpenAI GPT API

# === Logging ===
LOG_LEVEL=INFO                   # DEBUG, INFO, WARNING, ERROR
LOG_DIR=logs

# === Workers ===
SCRAPER_WORKERS=1                # Počet paralelních scraper workerů
PARSER_WORKERS=1                 # Počet paralelních parser workerů

# === Re-queue nastavení ===
REQUEUE_INTERVAL_DAYS=90         # Jak často re-scrapovat kvalitní stránky

# === Blacklist ===
BLACKLIST_THRESHOLD=3            # Počet failů před auto-blacklistem
```

### 2. Inicializace Bloom filtrů

```bash
source .venv/bin/activate
python scripts/bloom_admin.py create emails --capacity 5000000
python scripts/bloom_admin.py create phones --capacity 5000000
python scripts/bloom_admin.py create ico --capacity 500000
```

---

## První spuštění

### 1. Manuální test

```bash
cd /opt/web-scraper
source .venv/bin/activate

# Test databázového připojení
python -c "from src.utils.db import get_db_connection; conn = get_db_connection(); print('DB OK' if conn else 'FAIL')"

# Přidej testovací URL
python scripts/queue_admin.py add "https://example.com" --unit-id 1 --priority 10

# Spusť scraper (zpracuje 1 URL a skončí)
python -c "from src.workers.scraper import Scraper; s = Scraper(); s.process_one()"

# Zkontroluj výsledek
psql -U scraper_user -d web_scraper -h localhost -c \
  "SELECT url, status_code, detected_language FROM scrape_results ORDER BY id DESC LIMIT 1;"

# Spusť parser (zpracuje 1 výsledek)
python -c "from src.workers.parser import Parser; p = Parser(); p.process_one()"

# Zkontroluj parsovaná data
python scripts/monitor.py listing 1
```

### 2. Bulk import URLs

```bash
# Připrav soubor s URL (jeden per řádek)
cat > /tmp/urls.txt <<EOF
https://example.com
https://example.org
https://wikipedia.org
EOF

# Import
python scripts/queue_admin.py bulk-add /tmp/urls.txt --unit-id 1
```

---

## Provoz aplikace

### Spuštění workerů

#### Varianta A: Manuální spuštění (testování)

```bash
cd /opt/web-scraper
source .venv/bin/activate

# Spusť workers v samostatných terminálech nebo s &
python src/workers/scraper.py &
python src/workers/parser.py &
python src/workers/change_detector.py &
python src/workers/requeue.py &
```

#### Varianta B: Systemd (production, doporučeno)

Viz detailní instrukce v implementačním plánu pro vytvoření `.service` souborů.

---

## Monitoring a diagnostika

### Základní health check

```bash
python scripts/monitor.py health
```

### Statistiky

```bash
# Statistiky za posledních 7 dní
python scripts/monitor.py stats --days 7

# Quality score distribuce
python scripts/monitor.py quality

# Recent změny
python scripts/monitor.py changes

# Blacklist přehled
python scripts/monitor.py blacklist
```

### Log monitoring

```bash
tail -f logs/scraper.log
tail -f logs/parser.log
```

---

## Údržba

### Denní úkoly
* `python scripts/monitor.py health`
* Kontrola logů na errory

### Týdenní úkoly
* `python scripts/monitor.py stats`
* Review blacklistu

### Měsíční úkoly
* Clean old data (>6 měsíců)
* Rebuild bloom filters
