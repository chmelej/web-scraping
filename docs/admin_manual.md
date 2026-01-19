# Web Scraper - Administrátorský manuál

## Obsah

1. Požadavky na systém
2. Instalace
3. Konfigurace
4. První spuštění
5. Provoz aplikace
6. Monitoring a diagnostika
7. Údržba
8. Řešení problémů
9. Backup a obnova
10. Bezpečnost

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
```

### 3. Stažení aplikace

```bash
git clone https://github.com/your-repo/web-scraper.git /opt/web-scraper
cd /opt/web-scraper
```

### 4. Python prostředí

```bash
# Vytvoř virtual environment
uv venv
source .venv/bin/activate

# Instaluj dependencies
uv sync # nebo pip install -r requirements.txt

# Stáhni spaCy modely
python -m spacy download cs_core_news_lg
python -m spacy download en_core_web_lg

# Instaluj Playwright prohlížeče
playwright install chromium
```

### 5. Databázové migrace

```bash
# Inicializace databáze
python scripts/init_db.py
```

---

## Konfigurace

Edituj soubor `.env` (vytvoř kopii z `.env.example`):

```bash
DATABASE_URL=postgresql://scraper_user:your_secure_password@localhost:5432/web_scraper
SCRAPE_DELAY_SECONDS=2
MAX_RETRIES=3
PLAYWRIGHT_HEADLESS=true
```

---

## První spuštění

```bash
# Aktivuj venv
source .venv/bin/activate

# Přidej URL do fronty
python scripts/queue_admin.py add "https://example.com" --unit-id 1

# Spusť scraper
python src/workers/scraper.py
```

---

## Provoz aplikace

Doporučujeme spustit workery jako systemd služby nebo v Docker kontejnerech.

Seznam workerů:
* `src/workers/scraper.py`
* `src/workers/parser.py`
* `src/workers/change_detector.py`
* `src/workers/requeue.py`

---

## Monitoring

Použijte přiložený skript `scripts/monitor.py`:

```bash
python scripts/monitor.py health
python scripts/monitor.py stats --days 7
```

---

## Administrace

### Správa fronty
```bash
python scripts/queue_admin.py --help
```

### Správa Bloom filtrů
```bash
python scripts/bloom_admin.py --help
```

### Správa Promptů
```bash
python scripts/prompt_admin.py --help
```
