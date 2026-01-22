# Další kroky pro zprovoznění systému

Na základě analýzy existujícího kódu a dokumentace je systém kompletně implementován.
Následující kroky popisují, jak systém uvést do provozu.

## 1. Příprava prostředí

V kořenovém adresáři byl vytvořen soubor `.env` na základě `.env.example`.
Závislosti byly nainstalovány (`requirements.txt`).

Pokud potřebujete přeinstalovat:
```bash
pip install -r requirements.txt
playwright install chromium
```

## 2. Databáze

Systém vyžaduje běžící PostgreSQL databázi. Konfigurace je v `.env`.

1. Nastartujte PostgreSQL server.
2. Inicializujte databázi pomocí skriptu:
```bash
python scripts/init_db.py
```
*Poznámka: Tento skript aplikuje migrace z adresáře `migrations/`.*

## 3. Testování

Funkčnost systému byla ověřena sadou testů. Pro spuštění testů:
```bash
pytest tests/
```
Testy pokrývají:
- Připojení k DB (mocked)
- Scraper (včetně Playwright)
- Parser (regexy, extrakce)
- Utils (jazyk, URL)

## 4. Spuštění workerů

Systém se skládá ze čtyř workerů. Spusťte je paralelně (ideálně přes systemd, viz `docs/admin_manual.md`):

```bash
python src/workers/scraper.py
python src/workers/parser.py
python src/workers/change_detector.py
python src/workers/requeue.py
```

## 5. Správa fronty

Pro přidání URL do fronty použijte admin skript:

```bash
python scripts/queue_admin.py add "https://example.com" --unit-id 1
```

## Archivace
Staré skripty byly přesunuty do adresáře `archive/old-scripts/`.
