Web scraping systém pro extrakci firemních dat

Projekt pro scraping dat z webových stránek. Do vstupní fronty se nahrají URL \+ uniListindId (vazební klíč k naší aplikaci )

* z URL se pokusíme stáhnout HTML.  
* Výsledek uložíme včetně meta dat, IP, stav DNS. Došlo k přesmerovani? Výsledek 200, 401, ...  
* pak by mělo dojít k vyhodnocení jestli je stránky, jestli je v pořádku, chybové stránky. Zaparkované weby. Zablokované stránky. Prázdné stránky, ... Pokud je stránka v pořádku, začneme na ni hledat hodnotné údaje. Zajímá nás: název firmy, adresa, otevírací doba, činnost firmy, Klíčová slova, obrázky do galerie, logo. Souřadnice, kontakty (telefon, e-mail, web, Facebook, LinkedIn, ... ) oblast kde působí, IČO... K tomu to rozpoznávání máme jednoduché skripty s regulárními vyrazy, Bloom filtry. Případně by se hodil nějaký jednoduchý model pro dohledání a formátování (např otevírací doba nemá zavedený formát, takže LLM ma nejlepší účinnost, ale pro hledani e-mailu je to kanon na vrabce). Nalezená data se uloží ve formě JSON. Kde se dal mohou zpracovávat. Pokud se Stránka stáhne o obsahuje data, tak by se mělo cca po 3 měsících znovu vložit do fronty a celý proces opakovat. Navíc by se mělo provést detekce změn (nový kontakt, změna OH ,...) a ty uložit extra .

Předpokládám že by měla být jedna databáze PostgreSQL pro všechny data, a několik nezávislých procesů, jeden pro stahování HTML dat, jiný pro parsování a další pro detekci změn, pro opakované vkládání do fronty.

Použité nástroje: Python, playwright, cravlee, beautifulsoap, UV, ...

Plánujeme, co ještě bys doplnil?

2:23 PM

Dobrý základ\! Tady jsou návrhy na doplnění a upřesnění:

## **Architektura & Infrastruktura**

**Message Queue místo prosté fronty**

* Redis \+ Bull/BullMQ nebo RabbitMQ pro robustní frontu s retry mechanikou  
* Oddělené fronty: `scraping`, `parsing`, `change_detection`, `requeue`  
* Dead letter queue pro opakované selhání

**Cache vrstva**

* Redis pro DNS záznamy (TTL 24h), robots.txt, známé bloky  
* Předchází opakovaným dotazům na stejné zdroje

**Rate limiting & Politeness**

* Respektování robots.txt  
* Dynamický delay podle domény (např. 1-5s mezi requesty na stejnou doménu)  
* User-agent rotation, proxy pool pro velké objemy  
* Circuit breaker pro domény co vrací časté errory

## **Datový model (PostgreSQL)**

sql  
*\-- Základní tabulky*  
\- scrape\_queue (url, unit\_listing\_id, priority, next\_scrape\_at, retry\_count)  
\- scrape\_results (id, url, html, headers, status\_code, redirects, ip, dns\_info, scraped\_at, processing\_status)  
\- parsed\_data (scrape\_result\_id, json\_data, extracted\_at, confidence\_scores)  
\- change\_history (unit\_listing\_id, field\_name, old\_value, new\_value, detected\_at)

\- domain\_metadata (domain, last\_scraped, avg\_response\_time, error\_rate, robots\_txt)

**Indexy:** url, unit\_listing\_id, next\_scrape\_at, domain

## **Detekce kvality stránky**

Doplnil bych:

* **Content hash** pro rychlou detekci změn  
* **Jazykovou detekci** (langdetect) \- filtr nerelevantních jazyků  
* **Duplicitní content** \- domény co hostují stejný obsah  
* **Spam score** \- podezřelé keywords, příliš mnoho odkazů  
* **Accessibility check** \- validní HTML structure

## **Extraction pipeline**

**Multi-stage approach:**

1. **Regex \+ selektory** pro strukturované data (JSON-LD, microdata, OpenGraph)  
2. **Bloom filtry** pro rychlé ANO/NE (má IČO, email, telefon?)  
3. **LLM fallback** pouze pro:  
   * Nestrukturovanou otevírací dobu  
   * Popis činnosti (summarization)  
   * Extrakce z PDF/obrázků (OCR \+ GPT-4V)

**Konkrétní extraction strategie:**

* JSON-LD, Schema.org markup (často obsahuje vše)  
* Meta tags (og:, twitter:)  
* Strukturované selektory (hCard, vCard microformats)  
* Fallback regex pattern matching  
* LLM jako poslední instance s confidence score

## **Monitoring & Observability**

* **Metriky:** scraping rate, success/fail ratio, avg response time, queue depth  
* **Alerting:** vysoká error rate, plná fronta, DNS failures  
* **Logging:** strukturované logy (JSON) s trace\_id pro celou pipeline  
* **Dashboard:** Grafana/Metabase pro sledování health

## **Optimalizace**

**Playwright je heavy, zvážit:**

* `httpx` nebo `aiohttp` pro statické stránky (90% případů)  
* Playwright jen pro JavaScript-heavy weby (detekovat pomocí hlavičky `Content-Type`)  
* Headless browser pool (max 5-10 instancí paralelně)

**Crawlee výhody:**

* Automatické retry, request throttling  
* Built-in session management  
* Integrace s Playwright i Cheerio

**BeautifulSoup alternativy:**

* `lxml` (rychlejší parsování)  
* `selectolax` (5-10x rychlejší než BS4)

## **Bezpečnost & Compliance**

* **GDPR:** anonymizace osobních údajů, opt-out mechanismus  
* **Sandbox** pro stahování (kontejnery/izolace)  
* **Content Security:** skenování na malware v HTML/JS  
* **Copyright:** respektování `noindex`, `noarchive`

## **Škálovatelnost**

* **Horizontální scaling:** více scraping workerů (Kubernetes/Docker Swarm)  
* **Partitioning:** rozdělení podle domény/geografie  
* **Incremental scraping:** jen změněné části (ETag, Last-Modified headers)

## **Testování**

* **Unit testy** pro extrakční regex/funkce  
* **Integration testy** s mockovanými HTML responses  
* **E2E testy** na vzorových real-world stránkách  
* **Regression suite** pro detekci změn v extraction accuracy

## **Co ještě zvážit**

* **Duplicate detection** už při queue insertu (bloom filter na URL)  
* **Priority queue** \- důležitější listings častěji  
* **Incremental updates** \- partial scraping známých stránek  
* **Fallback strategie** při long-term failures (email majiteli?)  
* **Data retention policy** \- jak dlouho držet staré HTML snapshoty

Chceš, abych rozpracoval některou konkrétní část detailněji?

Dobre připomínky, projekt bude dlouhodoby pomalý. Čitelnost a jednoduchost architektury je důležitější než výkon. Opravdu je potřeba redis?

Ještě asi je potřeba mít nějaky Black list pokud se do fronty budou opakovaně dostávat URL na domény ze kterých se data dostat nelze. Nebo nechceme tak to ani nemá smysl zkoušet.

Naopak některé weby mají informace na několika stránkách takže pokud najdeme na stránce nadějný odkaz můžeme ho přidat do fronty s odkazem na původní stránku a odkazem na uniListindId

2:36 PM

Máš pravdu \- pro pomalý, dlouhodobý projekt je Redis overkill. PostgreSQL zvládne frontu i bez něj.

## **Zjednodušená architektura (bez Redis)**

**PostgreSQL jako jediná databáze:**

sql  
*\-- Fronta s prioritami a stavem*  
CREATE TABLE scrape\_queue (  
    id SERIAL PRIMARY KEY,  
    url TEXT NOT NULL,  
    unit\_listing\_id INTEGER,  
    parent\_scrape\_id INTEGER, *\-- odkaz na původní stránku*  
    priority INTEGER DEFAULT 0,  
    status VARCHAR(20) DEFAULT 'pending', *\-- pending, processing, completed, failed*  
    retry\_count INTEGER DEFAULT 0,  
    next\_scrape\_at TIMESTAMP,  
    added\_at TIMESTAMP DEFAULT NOW(),  
    UNIQUE(url, unit\_listing\_id)  
);

*\-- Blacklist domén*  
CREATE TABLE domain\_blacklist (  
    domain TEXT PRIMARY KEY,  
    reason VARCHAR(50), *\-- no\_data, blocked, parked, malware, manual*  
    fail\_count INTEGER DEFAULT 0,  
    first\_failed\_at TIMESTAMP,  
    last\_failed\_at TIMESTAMP,  
    auto\_added BOOLEAN DEFAULT TRUE, *\-- true \= systém, false \= manuální*  
    notes TEXT  
);

*\-- Whitelist pro vícestránkové scrapování*  
CREATE TABLE domain\_multipage\_rules (  
    domain TEXT PRIMARY KEY,  
    url\_patterns TEXT\[\], *\-- pole regexů pro nadějné odkazy*  
    max\_depth INTEGER DEFAULT 2,  
    enabled BOOLEAN DEFAULT TRUE

);

**Jednoduché vyzvedávání z fronty:**

python  
*\# Worker prostě SELECT s FOR UPDATE SKIP LOCKED*  
SELECT \* FROM scrape\_queue   
WHERE status \= 'pending'   
  AND next\_scrape\_at \<= NOW()  
  AND url NOT LIKE ANY(SELECT '%' || domain || '%' FROM domain\_blacklist)  
ORDER BY priority DESC, added\_at ASC  
LIMIT 1

FOR UPDATE SKIP LOCKED;

## **Blacklist logika**

**Automatické přidávání:**

python  
*\# Po 3 neúspěšných pokusech za sebou*  
if retry\_count \>= 3 and status in \['parked', 'blocked', 'empty', 'error'\]:  
    INSERT INTO domain\_blacklist   
    VALUES (domain, reason, fail\_count, ...)

    ON CONFLICT DO UPDATE ...

**Typy blacklistu:**

* **Permanentní:** parked domains, malware, explicit block  
* **Dočasný (TTL):** rate-limited (retry za 7 dní), DNS failures (retry za 1 den)  
* **Soft blacklist:** nízká priorita místo bloku (může se změnit)

**Manuální správa:**

sql  
*\-- Tabulka pro review pochybných případů*  
CREATE TABLE blacklist\_candidates (  
    domain TEXT,  
    auto\_reason VARCHAR(50),  
    sample\_urls TEXT\[\],  
    needs\_review BOOLEAN DEFAULT TRUE

);

## **Vícestránkové scrapování**

**Heuristiky pro "nadějné odkazy":**

python  
*\# Patterns pro odkazy co můžou obsahovat další data*  
PROMISING\_PATTERNS \= {  
    'kontakt': r'/(kontakt|contact|o-nas|about)',  
    'lokace': r'/(pobocky|branches|locations|kde-nas-najdete)',  
    'sluzby': r'/(sluzby|services|nabidka|portfolio)',  
    'galerie': r'/(galerie|gallery|realizace|reference)'  
}

def is\_promising\_link(url, base\_url):  
    *\# Musí být stejná doména*  
    if not same\_domain(url, base\_url):  
        return False  
      
    *\# Matched pattern?*  
    for pattern in PROMISING\_PATTERNS.values():  
        if re.search(pattern, url, re.IGNORECASE):  
            return True  
      
    *\# Nebo je to subdirectory (ne parametr)*  
    parsed \= urlparse(url)  
    if parsed.path.count('/') \<= 3 and '?' not in url:  
        return True  
    

    return False

**Limitace hloubky:**

sql  
*\-- Tracking hloubky scrapování*  
ALTER TABLE scrape\_queue ADD COLUMN depth INTEGER DEFAULT 0;

*\-- Při přidávání sub-stránek*  
INSERT INTO scrape\_queue (url, unit\_listing\_id, parent\_scrape\_id, depth)  
VALUES (:url, :unit\_listing\_id, :parent\_id, :parent\_depth \+ 1)  
WHERE :parent\_depth \< (  
    SELECT COALESCE(max\_depth, 2)   
    FROM domain\_multipage\_rules   
    WHERE domain \= :domain

);

**Prevence duplicit a smyček:**

sql  
*\-- URL normalizace před INSERT*  
CREATE UNIQUE INDEX idx\_normalized\_url   
ON scrape\_queue (  
    lower(regexp\_replace(url, '/$', '')), *\-- bez trailing slash*  
    unit\_listing\_id  
);

*\-- Kontrola už navštívených*  
SELECT 1 FROM scrape\_results   
WHERE normalized\_url \= :url 

  AND scraped\_at \> NOW() \- INTERVAL '3 months';

## **Pracovní flow**

**Scraper worker:**

1. SELECT z fronty (s blacklist kontrolou)  
2. Stáhne HTML  
3. Zapíše do `scrape_results`  
4. Označí jako `completed`  
5. Pokud našel nadějné odkazy → přidá do fronty

**Parser worker:**

python  
*\# Zpracuje nové scrape\_results*  
SELECT \* FROM scrape\_results   
WHERE processing\_status \= 'new'  
ORDER BY scraped\_at DESC  
LIMIT 100;

*\# Extrahuje data, uloží JSON*

*\# Pokud quality\_score \< threshold → blacklist kandidát*

**Re-queue worker:**

python  
*\# 1x denně, najde záznamy k refresh*  
INSERT INTO scrape\_queue (url, unit\_listing\_id, next\_scrape\_at)  
SELECT url, unit\_listing\_id, NOW() \+ INTERVAL '3 months'  
FROM scrape\_results  
WHERE scraped\_at \< NOW() \- INTERVAL '3 months'  
  AND quality\_score \> 0.5

  AND domain NOT IN (SELECT domain FROM domain\_blacklist);

## **Monitoring \- jednoduché SQL views**

sql  
*\-- Dashboard queries*  
CREATE VIEW scraping\_stats AS  
SELECT   
    DATE(scraped\_at) as date,  
    COUNT(\*) as total\_scrapes,  
    COUNT(\*) FILTER (WHERE status\_code \= 200) as successful,  
    COUNT(\*) FILTER (WHERE quality\_score \> 0.5) as quality\_pages  
FROM scrape\_results  
GROUP BY DATE(scraped\_at);

CREATE VIEW queue\_health AS  
SELECT   
    status,  
    COUNT(\*) as count,  
    AVG(retry\_count) as avg\_retries  
FROM scrape\_queue

GROUP BY status;

## **Konfigurace (jednoduché .env nebo config tabulka)**

sql  
CREATE TABLE config (  
    key TEXT PRIMARY KEY,  
    value TEXT,  
    description TEXT  
);

INSERT INTO config VALUES   
('scrape\_delay\_seconds', '2', 'Delay mezi requesty na stejnou doménu'),  
('blacklist\_threshold', '3', 'Počet failů před blacklistem'),  
('max\_scrape\_depth', '2', 'Max hloubka pro multi-page'),

('requeue\_interval\_days', '90', 'Interval pro refresh');

**Výhody tohoto přístupu:**

* Jedna databáze, žádné external dependencies  
* Snadné SQL dotazy pro debugging  
* Transakční konzistence  
* Stačí `psycopg2` a Python worker skripty

Stačí ti to takhle jednoduše, nebo chceš ještě něco doladit?

Jake modely (mensi je lepší) doporučiš pro výše uvedené akce? Má smysl trénovat něco vlastního? Aplikace by měla zahrnovat i nástroje pro správu Bloom filtru. Lze očekávat že se budou měnit vylepšovat podle stažených dat. Regexp stačí mít v kódu. Stejně se o to bude starat programátor

2:56 PM

## **Modely pro extraction**

**Pro tvůj use case bych šel primárně BEZ vlastních modelů.** Důvody:

* Máš jasně definované úlohy (NER, klasifikace)  
* Malý team, údržba modelů je overhead  
* Off-the-shelf řešení jsou dost dobrá

### **Konkrétní doporučení:**

**1\. Otevírací doba (normalizace textu)**

* **Mistral 7B** nebo **Llama 3.2 3B** (lokálně přes Ollama)  
* Prompt: "Převeď do JSON formátu: Po-Pá 9-17, So 10-14"  
* Fallback: Promptuj Claude/GPT-4o-mini přes API (10x dražší, ale přesnější)

**2\. Named Entity Recognition (firma, adresa, IČO)**

* **spaCy** s českým modelem `cs_core_news_lg` (350MB)  
* Rozpozná: osoby, organizace, lokace, datumy  
* Vlastní NER entity: `nlp.add_pipe("entity_ruler")` pro IČO pattern

**3\. Klasifikace činnosti firmy**

* **Sentence transformers** \- `paraphrase-multilingual-mpnet-base-v2` (278MB)  
* Embeddings \+ cosine similarity k předem definovaným kategoriím (NACE kódy)  
* Nebo jen keyword matching \- může stačit\!

**4\. Detekce kvality stránky**

* **Jednoduchý klasifikátor:** scikit-learn Random Forest  
* Features: word count, link ratio, has\_contact, language, HTML structure score  
* Dataset: ručně označit 500-1000 stránek (quality/spam/parked/empty)

**5\. Detekce změn**

* **Žádný model** \- čistě diffing JSONů \+ pravidla  
* Pro text: Levenshtein distance, difflib  
* Pro strukturovaná data: JSON diff

### **Má smysl trénovat vlastní?**

**ANO, ale jen jedno:**

**Micro-model pro klasifikaci stránky (quality score)**

python  
from sklearn.ensemble import RandomForestClassifier

features \= \[  
    'word\_count', 'has\_email', 'has\_phone', 'has\_ico',  
    'link\_density', 'image\_count', 'meta\_quality\_score',  
    'has\_opening\_hours', 'has\_address', 'content\_length',  
    'domain\_age\_days', 'has\_social\_links'  
\]

*\# 4 třídy: quality, empty, parked, spam*  
*\# Natrénuješ na 1000 ručně označených stránek*

*\# Model pod 1MB, inference \<10ms*

**NE pro:**

* NER (spaCy je lepší než cokoliv co natrénuješ)  
* Otevírací dobu (LLM prompt engineering stačí)  
* Extraction (regex \+ selektory \+ fallback LLM)

## **Bloom filter management**

**Struktura:**

sql  
CREATE TABLE bloom\_filters (  
    id SERIAL PRIMARY KEY,  
    name VARCHAR(50) UNIQUE, *\-- 'emails', 'phones', 'ico', 'domains'*  
    filter\_data BYTEA, *\-- serializovaný bloom filter*  
    item\_count INTEGER,  
    false\_positive\_rate FLOAT,  
    created\_at TIMESTAMP,  
    last\_updated TIMESTAMP  
);

CREATE TABLE bloom\_filter\_items (  
    filter\_name VARCHAR(50),  
    item TEXT,  
    added\_at TIMESTAMP,  
    source VARCHAR(50), *\-- 'scraped', 'manual', 'imported'*  
    PRIMARY KEY (filter\_name, item)

);

**Python admin nástroje:**

python  
from pybloom\_live import BloomFilter  
import psycopg2

class BloomFilterManager:  
    def \_\_init\_\_(self, db\_conn):  
        self.conn \= db\_conn  
      
    def create\_filter(self, name, capacity\=1000000, error\_rate\=0.001):  
        """Vytvoří nový bloom filter"""  
        bf \= BloomFilter(capacity\=capacity, error\_rate\=error\_rate)  
          
        *\# Uložit do DB*  
        self.conn.execute(  
            "INSERT INTO bloom\_filters (name, filter\_data, item\_count, false\_positive\_rate) "  
            "VALUES (%s, %s, 0, %s)",  
            (name, bf.bitarray.tobytes(), error\_rate)  
        )  
      
    def load\_filter(self, name):  
        """Načte bloom filter z DB"""  
        row \= self.conn.execute(  
            "SELECT filter\_data FROM bloom\_filters WHERE name \= %s",   
            (name,)  
        ).fetchone()  
          
        bf \= BloomFilter.fromfile(io.BytesIO(row\[0\]))  
        return bf  
      
    def add\_items(self, filter\_name, items, source\='scraped'):  
        """Přidá items do filtru i do tabulky"""  
        bf \= self.load\_filter(filter\_name)  
          
        for item in items:  
            bf.add(item)  
            self.conn.execute(  
                "INSERT INTO bloom\_filter\_items VALUES (%s, %s, NOW(), %s) "  
                "ON CONFLICT DO NOTHING",  
                (filter\_name, item, source)  
            )  
          
        *\# Update filtru v DB*  
        self.conn.execute(  
            "UPDATE bloom\_filters SET filter\_data \= %s, item\_count \= %s, "  
            "last\_updated \= NOW() WHERE name \= %s",  
            (bf.bitarray.tobytes(), len(bf), filter\_name)  
        )  
      
    def rebuild\_from\_db(self, filter\_name):  
        """Rebuil filtru z bloom\_filter\_items (když se změní parametry)"""  
        items \= self.conn.execute(  
            "SELECT item FROM bloom\_filter\_items WHERE filter\_name \= %s",  
            (filter\_name,)  
        ).fetchall()  
          
        *\# Smaž starý*  
        self.conn.execute("DELETE FROM bloom\_filters WHERE name \= %s", (filter\_name,))  
          
        *\# Vytvoř nový s novými parametry*  
        self.create\_filter(filter\_name, capacity\=len(items)\*2)  
        bf \= self.load\_filter(filter\_name)  
          
        for (item,) in items:  
            bf.add(item)  
          
        *\# Ulož*  
        self.conn.execute(  
            "UPDATE bloom\_filters SET filter\_data \= %s WHERE name \= %s",  
            (bf.bitarray.tobytes(), filter\_name)  
        )  
      
    def stats(self, filter\_name):  
        """Statistiky filtru"""  
        return self.conn.execute(  
            "SELECT item\_count, false\_positive\_rate, last\_updated "  
            "FROM bloom\_filters WHERE name \= %s",  
            (filter\_name,)

        ).fetchone()

**Admin CLI nástroje:**

python  
*\# scripts/bloom\_admin.py*  
import click

@click.group()  
def cli():  
    pass

@cli.command()  
@click.argument('filter\_name')  
@click.argument('capacity', type\=int, default\=1000000)  
def create(filter\_name, capacity):  
    """Vytvoří nový bloom filter"""  
    manager \= BloomFilterManager(get\_db())  
    manager.create\_filter(filter\_name, capacity)  
    click.echo(f"✓ Filter '{filter\_name}' vytvořen (kapacita: {capacity})")

@cli.command()  
@click.argument('filter\_name')  
@click.argument('file', type\=click.File('r'))  
def import\_items(filter\_name, file):  
    """Importuje items ze souboru (1 per line)"""  
    manager \= BloomFilterManager(get\_db())  
    items \= \[line.strip() for line in file\]  
    manager.add\_items(filter\_name, items, source\='imported')  
    click.echo(f"✓ Importováno {len(items)} items do '{filter\_name}'")

@cli.command()  
@click.argument('filter\_name')  
def rebuild(filter\_name):  
    """Rebuild filtru z DB (např. po změně parametrů)"""  
    manager \= BloomFilterManager(get\_db())  
    manager.rebuild\_from\_db(filter\_name)  
    click.echo(f"✓ Filter '{filter\_name}' přestavěn")

@cli.command()  
@click.argument('filter\_name')  
def stats(filter\_name):  
    """Zobrazí statistiky"""  
    manager \= BloomFilterManager(get\_db())  
    count, fpr, updated \= manager.stats(filter\_name)  
    click.echo(f"Filter: {filter\_name}")  
    click.echo(f"  Items: {count:,}")  
    click.echo(f"  False positive rate: {fpr}")  
    click.echo(f"  Last updated: {updated}")

@cli.command()  
def list():  
    """Seznam všech filtrů"""  
    *\# ... SELECT \* FROM bloom\_filters*

if \_\_name\_\_ \== '\_\_main\_\_':

    cli()

**Použití:**

bash  
*\# Vytvoř filtry*  
python bloom\_admin.py create emails 5000000  
python bloom\_admin.py create ico 500000  
python bloom\_admin.py create blacklist\_domains 100000

*\# Import existujících dat*  
python bloom\_admin.py import-items emails known\_emails.txt

*\# Po scrapingu \- automaticky*  
*\# parser worker volá manager.add\_items() s nově nalezenými emails*

*\# Rebuild když potřebuješ změnit parametry*  
python bloom\_admin.py rebuild emails

*\# Stats*

python bloom\_admin.py stats emails

**Kdy updatovat filtry:**

1. **Real-time** \- parser worker průběžně přidává nově nalezené items  
2. **Batch nightly** \- rebuild pro optimalizaci (volitelné)  
3. **Manuálně** \- import z externích zdrojů (veřejné registry IČO, ...)

**Typy filtrů co dávají smysl:**

* `emails` \- už viděné emaily (deduplikace)  
* `phones` \- už viděné telefony  
* `ico` \- známé IČO (rychlá validace)  
* `blacklist_domains` \- in-memory check před DB query  
* `seen_urls` \- už scrapované URLs (doplněk k DB)

Regex opravdu nech v kódu \- je to flexibilnější a nemá smysl to komplikovat. Programátor je upraví rychleji než by se to loadovalo z DB.

Takto to dává smysl?

Předpokládám data budou v několika jazycich (nl,fr,cz,sk,to,en) jaký to dopad na aplikaci? Datový model, zvolené nástroje, atd... ?

3:14 PM

## **Dopad multijazyčnosti na projekt**

### **1\. Datový model**

**Rozšíření schémat:**

sql  
*\-- Detekovaný jazyk u každého scrape*  
ALTER TABLE scrape\_results   
ADD COLUMN detected\_language VARCHAR(5), *\-- 'cs', 'sk', 'en', 'nl', 'fr', 'de'*  
ADD COLUMN language\_confidence FLOAT;

*\-- Parsovaná data s jazykem*  
ALTER TABLE parsed\_data  
ADD COLUMN content\_language VARCHAR(5);

*\-- Bloom filtry per jazyk (volitelné, pro specifika)*  
ALTER TABLE bloom\_filters  
ADD COLUMN language VARCHAR(5); *\-- NULL \= language-agnostic*

*\-- Blacklist může být language-specific*  
ALTER TABLE domain\_blacklist  
ADD COLUMN primary\_language VARCHAR(5);

*\-- Multi-page rules podle jazyka*  
ALTER TABLE domain\_multipage\_rules

ADD COLUMN url\_patterns\_i18n JSONB; *\-- {'cs': \[...\], 'en': \[...\]}*

**JSON struktura parsovaných dat:**

json  
{  
  "language": "cs",  
  "company\_name": "Příklad s.r.o.",  
  "address": {  
    "raw": "Václavské náměstí 1, Praha",  
    "structured": {...}  
  },  
  "opening\_hours": {  
    "raw\_text": "Po-Pá 9-17",  
    "normalized": \[...\],  
    "extraction\_method": "llm" *// protože nestrukturované*  
  },  
  "contacts": {  
    "phone": \["+420123456789"\],  
    "email": \["info@example.cz"\]  
  },  
  "business\_activity": {  
    "raw\_text\_cs": "Výroba nábytku na zakázku",  
    "nace\_code": "31.01" *// mezinárodní klasifikace*  
  }

}

### **2\. Detekce jazyka**

**Přidej na začátek pipeline:**

python  
from langdetect import detect\_langs  *\# lehká knihovna, 1MB*  
*\# nebo: from lingua import LanguageDetectorBuilder (přesnější, 50MB)*

def detect\_language(html\_text):  
    """Detekuje jazyk z textu"""  
    *\# Očisti HTML*  
    text \= BeautifulSoup(html\_text, 'lxml').get\_text()  
    text \= ' '.join(text.split())\[:10000\]  *\# prvních 10k znaků stačí*  
      
    try:  
        *\# langdetect vrací \[(lang, probability), ...\]*  
        results \= detect\_langs(text)  
        return results\[0\].lang, results\[0\].prob  
    except:  
        return 'unknown', 0.0

*\# V scraper workeru:*  
language, confidence \= detect\_language(html)  
cursor.execute(  
    "UPDATE scrape\_results SET detected\_language=%s, language\_confidence=%s WHERE id=%s",  
    (language, confidence, scrape\_id)  
)

*\# Pokud confidence \< 0.8 → flag pro manuální review*

**Jazyková priorita:**

* Pokud najdeš `<html lang="cs">` → důvěřuj tomu  
* Jinak detekce z textu  
* Meta tags: `<meta property="og:locale" content="cs_CZ">`

### **3\. NER a extrakce per jazyk**

**spaCy modely:**

python  
*\# Instalace modelů pro všechny jazyky*  
*\# uv pip install spacy*  
*\# python \-m spacy download cs\_core\_news\_lg      \# čeština*  
*\# python \-m spacy download de\_core\_news\_lg      \# němčina*    
*\# python \-m spacy download en\_core\_web\_lg       \# angličtina*  
*\# python \-m spacy download fr\_core\_news\_lg      \# francouzština*  
*\# python \-m spacy download nl\_core\_news\_lg      \# holandština*

MODELS \= {  
    'cs': 'cs\_core\_news\_lg',  
    'sk': 'cs\_core\_news\_lg',  *\# slovenština sdílí s češtinou*  
    'en': 'en\_core\_web\_lg',  
    'de': 'de\_core\_news\_lg',  
    'fr': 'fr\_core\_news\_lg',  
    'nl': 'nl\_core\_news\_lg'  
}

import spacy

class MultilingualNER:  
    def \_\_init\_\_(self):  
        self.nlp\_models \= {}  
      
    def get\_nlp(self, lang):  
        """Lazy load modelu"""  
        if lang not in self.nlp\_models:  
            model\_name \= MODELS.get(lang, 'en\_core\_web\_lg')  
            self.nlp\_models\[lang\] \= spacy.load(model\_name)  
        return self.nlp\_models\[lang\]  
      
    def extract\_entities(self, text, lang):  
        nlp \= self.get\_nlp(lang)  
        doc \= nlp(text)  
          
        return {  
            'organizations': \[ent.text for ent in doc.ents if ent.label\_ \== 'ORG'\],  
            'locations': \[ent.text for ent in doc.ents if ent.label\_ in \['LOC', 'GPE'\]\],  
            'persons': \[ent.text for ent in doc.ents if ent.label\_ \== 'PERSON'\]

        }

**Regex patterns per jazyk:**

python  
*\# regex\_patterns.py*  
PATTERNS \= {  
    'phone': {  
        'cs': r'\\+?420\\s?\\d{3}\\s?\\d{3}\\s?\\d{3}',  
        'sk': r'\\+?421\\s?\\d{3}\\s?\\d{3}\\s?\\d{3}',  
        'de': r'\\+?49\\s?\\d{3,4}\\s?\\d{3,8}',  
        'nl': r'\\+?31\\s?\\d{2,3}\\s?\\d{6,7}',  
        'fr': r'\\+?33\\s?\\d{1}\\s?\\d{2}\\s?\\d{2}\\s?\\d{2}\\s?\\d{2}',  
        'en': r'\\+?44\\s?\\d{4}\\s?\\d{6}',  *\# UK*  
    },  
    'ico': {  
        'cs': r'\\b\\d{8}\\b',  *\# IČO*  
        'sk': r'\\b\\d{8}\\b',  *\# IČO*    
        'de': r'\\b(DE)?\\d{9}\\b',  *\# USt-IdNr*  
        'nl': r'\\b\\d{9}B\\d{2}\\b',  *\# BTW-nummer*  
        'fr': r'\\bSIRET\\s?\\d{14}\\b',  
        'en': r'\\b\\d{8,10}\\b',  *\# Company number UK*  
    },  
    'email': r'\[a-zA-Z0-9.\_%+-\]+@\[a-zA-Z0-9.-\]+\\.\[a-zA-Z\]{2,}',  *\# universal*  
      
    'opening\_hours\_keywords': {  
        'cs': \['otevírací doba', 'otevřeno', 'po-pá', 'pondělí'\],  
        'sk': \['otváracie hodiny', 'otvorené', 'po-pi', 'pondelok'\],  
        'de': \['öffnungszeiten', 'geöffnet', 'mo-fr', 'montag'\],  
        'nl': \['openingstijden', 'geopend', 'ma-vr', 'maandag'\],  
        'fr': \['horaires', 'ouvert', 'lun-ven', 'lundi'\],  
        'en': \['opening hours', 'open', 'mon-fri', 'monday'\]  
    }  
}

def extract\_phone(text, lang):  
    pattern \= PATTERNS\['phone'\].get(lang, PATTERNS\['phone'\]\['en'\])

    return re.findall(pattern, text)

### **4\. LLM prompting per jazyk**

**Otevírací doba \- language-aware prompt:**

python  
PROMPTS \= {  
    'cs': """Převeď následující text otevírací doby do JSON formátu.  
Výstup musí být pouze JSON, bez vysvětlení.  
Formát: {{"days": \[{{"day": "monday", "open": "09:00", "close": "17:00"}}\]}}

Text: {text}""",  
      
    'de': """Konvertiere die folgenden Öffnungszeiten in JSON.  
Nur JSON ausgeben, keine Erklärung.  
Format: {{"days": \[{{"day": "monday", "open": "09:00", "close": "17:00"}}\]}}

Text: {text}""",  
      
    'en': """Convert the following opening hours to JSON.  
Output only JSON, no explanation.  
Format: {{"days": \[{{"day": "monday", "open": "09:00", "close": "17:00"}}\]}}

Text: {text}"""  
}

def normalize\_opening\_hours(text, lang):  
    prompt \= PROMPTS.get(lang, PROMPTS\['en'\]).format(text\=text)  
      
    *\# Malý model stačí: Llama 3.2 3B přes Ollama*  
    response \= ollama.generate(model\='llama3.2:3b', prompt\=prompt)

    return json.loads(response\['response'\])

**Alternativa \- bez LLM:**

python  
from datetime import time

*\# Univerzální parser (funguje pro většinu jazyků)*  
import datefinder  *\# najde časy v textu*

def simple\_hours\_parser(text):  
    """Jednoduchý parser bez LLM"""  
    *\# Najdi všechny časy*  
    times \= list(datefinder.find\_dates(text, source\=True))  
      
    *\# Detekuj pattern: "9-17", "9:00-17:00"*  
    hours \= re.findall(r'(\\d{1,2}):?(\\d{2})?\\s\*-\\s\*(\\d{1,2}):?(\\d{2})?', text)  
      
    if hours:  
        open\_h, open\_m, close\_h, close\_m \= hours\[0\]  
        return {  
            'open': f"{open\_h}:{open\_m or '00'}",   
            'close': f"{close\_h}:{close\_m or '00'}"  
        }  
    

    return None  *\# fallback k LLM*

### **5\. Bloom filtry \- multijazyčné**

**Dva přístupy:**

**A) Společné filtry (doporučuji):**

python  
*\# Email, telefon, IČO jsou language-agnostic*  
*\# Stačí jeden bloom filter pro všechny jazyky*  
bloom\_filters \= {  
    'emails': BloomFilter(5000000),  
    'phones': BloomFilter(5000000),  
    'company\_ids': BloomFilter(1000000),  *\# IČO, VAT, company numbers*

}

**B) Per-language (jen když nutné):**

python  
*\# Pokud bys chtěl filtrovat např. názvy firem per jazyk*  
bloom\_filters \= {  
    'company\_names\_cs': BloomFilter(1000000),  
    'company\_names\_de': BloomFilter(1000000),  
    *\# ...*

}

**Normalizace před vložením:**

python  
def normalize\_for\_bloom(text, field\_type):  
    """Normalizace před vložením do bloom filtru"""  
    text \= text.lower().strip()  
      
    if field\_type \== 'phone':  
        *\# Odstraň mezery, předvolby*  
        text \= re.sub(r'\[\\s\\-\\(\\)\]', '', text)  
        text \= re.sub(r'^\\+\\d{1,3}', '', text)  *\# remove country code*  
      
    elif field\_type \== 'email':  
        text \= text.lower()  
      
    elif field\_type \== 'company\_name':  
        *\# Odstraň právní formy (s.r.o., GmbH, Ltd, ...)*  
        legal\_forms \= \['s.r.o.', 'a.s.', 'gmbh', 'ltd', 'b.v.', 'sarl'\]  
        for form in legal\_forms:  
            text \= text.replace(form, '').strip()  
    

    return text

### **6\. Multi-page crawling per jazyk**

python  
*\# domain\_multipage\_rules rozšířené*  
MULTIPAGE\_PATTERNS \= {  
    'cs': {  
        'contact': r'/(kontakt|kontakty|spojeni)',  
        'about': r'/(o-nas|o-firme|profil)',  
        'services': r'/(sluzby|nabidka|co-delame)',  
        'locations': r'/(pobocky|kde-nas-najdete|provozovny)'  
    },  
    'de': {  
        'contact': r'/(kontakt|kontaktieren)',  
        'about': r'/(uber-uns|unternehmen|profil)',  
        'services': r'/(leistungen|dienstleistungen|angebot)',  
        'locations': r'/(standorte|filialen)'  
    },  
    'en': {  
        'contact': r'/(contact|contact-us|get-in-touch)',  
        'about': r'/(about|about-us|company)',  
        'services': r'/(services|what-we-do|solutions)',  
        'locations': r'/(locations|branches|find-us)'  
    },  
    *\# ... nl, fr, sk*  
}

def get\_promising\_links(html, base\_url, language):  
    """Najdi nadějné odkazy podle jazyka stránky"""  
    soup \= BeautifulSoup(html, 'lxml')  
    patterns \= MULTIPAGE\_PATTERNS.get(language, MULTIPAGE\_PATTERNS\['en'\])  
      
    promising \= \[\]  
    for link in soup.find\_all('a', href\=True):  
        url \= urljoin(base\_url, link\['href'\])  
          
        for category, pattern in patterns.items():  
            if re.search(pattern, url, re.IGNORECASE):  
                promising.append((url, category))  
                break  
    

    return promising

### **7\. Kvalita stránky \- language-aware**

python  
def calculate\_quality\_score(scrape\_result, parsed\_data, language):  
    """Quality score s ohledem na jazyk"""  
    score \= 0  
      
    *\# Základní metriky (universal)*  
    if parsed\_data.get('email'): score \+= 20  
    if parsed\_data.get('phone'): score \+= 20  
    if parsed\_data.get('address'): score \+= 15  
    if parsed\_data.get('company\_name'): score \+= 10  
      
    *\# Language-specific bonusy*  
    if language in \['cs', 'sk'\]:  
        if parsed\_data.get('ico'): score \+= 15  *\# IČO je důležité*  
        if parsed\_data.get('dic'): score \+= 5   *\# DIČ*  
      
    elif language \== 'de':  
        if parsed\_data.get('ust\_id'): score \+= 15  
        if parsed\_data.get('handelsregister'): score \+= 10  
      
    elif language \== 'nl':  
        if parsed\_data.get('kvk\_number'): score \+= 15  *\# KvK číslo*  
        if parsed\_data.get('btw\_number'): score \+= 10  
      
    *\# Penalizace pro špatný jazyk (pokud filtuješ)*  
    if language not in \['cs', 'sk', 'de', 'nl', 'fr', 'en'\]:  
        score \*= 0.5  
    

    return min(score, 100)

### **8\. Config per jazyk**

sql  
*\-- Language-specific konfigurace*  
CREATE TABLE language\_config (  
    language VARCHAR(5) PRIMARY KEY,  
    enabled BOOLEAN DEFAULT TRUE,  
    spacy\_model VARCHAR(50),  
    priority INTEGER DEFAULT 0,  *\-- vyšší \= scraped častěji*  
    llm\_fallback\_enabled BOOLEAN DEFAULT TRUE,  
    notes TEXT  
);

INSERT INTO language\_config VALUES  
('cs', true, 'cs\_core\_news\_lg', 100, true, 'Primary market'),  
('sk', true, 'cs\_core\_news\_lg', 90, true, 'Secondary market'),  
('de', true, 'de\_core\_news\_lg', 50, true, NULL),  
('en', true, 'en\_core\_web\_lg', 30, false, 'International only'),

('nl', false, 'nl\_core\_news\_lg', 10, false, 'Disabled for now');

### **9\. Doporučené nástroje \- finální výběr**

python  
*\# requirements.txt*  
langdetect\==1.0.9           *\# 1MB, detekce jazyka*  
spacy\==3.7.0                *\# NER*  
cs\-core\-news\-lg @ https://... *\# spaCy modely per jazyk*  
beautifulsoup4\==4.12.0  
lxml\==5.1.0                 *\# rychlý HTML parser*  
selectolax\==0.3.0           *\# (volitelně, 5-10x rychlejší než BS4)*

*\# LLM (volitelně, lokálně)*  
ollama                      *\# Python binding pro Llama 3.2*

*\# Bloom filters*  
pybloom\-live\==4.0.0

*\# Utils*  
python\-dateutil\==2.8.2      *\# parsování datumů*

phonenumbers\==8.13.0        *\# mezinárodní tel. čísla*

### **10\. Náklady LLM per jazyk**

**Pokud používáš LLM přes API:**

python  
*\# Levné modely per use-case*  
LLM\_CONFIG \= {  
    'opening\_hours': {  
        'model': 'claude-3-5-haiku-20241022',  *\# $0.25/1M tokens*  
        'max\_tokens': 200,  
        'languages': \['cs', 'sk', 'de'\]  *\# jen kde regex selže*  
    },  
    'business\_description': {  
        'model': 'gpt-4o-mini',  *\# $0.15/1M tokens*  
        'max\_tokens': 150,  
        'languages': \['cs'\]  *\# jen primary market*  
    }  
}

*\# Fallback lokálně (Ollama \- FREE)*

OLLAMA\_FALLBACK \= 'llama3.2:3b'  *\# 2GB RAM, dobrý pro většinu úkolů*

**Strategie:**

1. **Regex first** (free) → 70% případů  
2. **spaCy NER** (free) → 20% případů  
3. **LLM fallback** (paid/local) → 10% případů

### **Shrnutí dopadů**

| Oblast | Dopad | Řešení |
| ----- | ----- | ----- |
| **DB model** | Přidat `language` sloupce | Malý (3-4 sloupce) |
| **Detekce jazyka** | Nový krok v pipeline | `langdetect` (1MB) |
| **NER** | 6 spaCy modelů | \~2GB disk space |
| **Regex** | Per-language patterns | Dict v kódu |
| **LLM** | Multi-language prompty | Jen pro CS/SK/DE |
| **Bloom** | Normalizace | Společné filtry OK |
| **Crawling** | URL patterns per lang | Dict rozšíření |
| **Kvalita** | Language-aware scoring | \+20 řádků kódu |

**Celkově:** Multijazyčnost přidává **komplexitu \+30%**, ale nijak to projekt neláme. Největší změna je 6 spaCy modelů, zbytek je jen rozšíření existujících struktur.

Dává to smysl?

Ruznojazycne prompty by asi neměly být v kódu ale v propertis filé nebo v db. Nebo ne?

4:43 PM

**Máš absolutně pravdu.** Prompty patří buď do config souborů nebo DB, rozhodně ne natvrdo do kódu.

## **Doporučené řešení: DB \+ fallback soubor**

**Proč DB:**

* ✅ Snadná editace bez deploymentu  
* ✅ Verzování změn (audit log)  
* ✅ A/B testování variant promptů  
* ✅ Per-jazyk i per-use-case customizace  
* ✅ Možnost UI pro non-tech editaci

**Proč ne jen DB:**

* ❌ Závislost \- pokud DB spadne, aplikace nefunguje  
* ❌ Bootstrap problém \- první spuštění

**→ Hybrid: DB primary \+ config fallback**

---

## **Implementace**

### **1\. Databázové schema**

sql  
CREATE TABLE llm\_prompts (  
    id SERIAL PRIMARY KEY,  
    use\_case VARCHAR(50) NOT NULL,  *\-- 'opening\_hours', 'business\_description', ...*  
    language VARCHAR(5) NOT NULL,   *\-- 'cs', 'de', 'en', ...*  
    version INTEGER DEFAULT 1,  
    prompt\_template TEXT NOT NULL,  
    system\_prompt TEXT,             *\-- volitelný system prompt*  
    model VARCHAR(50),              *\-- 'claude-3-5-haiku', 'llama3.2:3b'*  
    max\_tokens INTEGER DEFAULT 200,  
    temperature FLOAT DEFAULT 0.0,  
      
    is\_active BOOLEAN DEFAULT TRUE,  
    created\_at TIMESTAMP DEFAULT NOW(),  
    updated\_at TIMESTAMP DEFAULT NOW(),  
    created\_by VARCHAR(50),  
    notes TEXT,  
      
    UNIQUE(use\_case, language, version)  
);

*\-- Pro A/B testování a sledování performance*  
CREATE TABLE prompt\_performance (  
    id SERIAL PRIMARY KEY,  
    prompt\_id INTEGER REFERENCES llm\_prompts(id),  
    executions INTEGER DEFAULT 0,  
    successes INTEGER DEFAULT 0,  
    failures INTEGER DEFAULT 0,  
    avg\_tokens\_used FLOAT,  
    avg\_response\_time\_ms FLOAT,  
    last\_used\_at TIMESTAMP,  
      
    success\_rate AS (CASE WHEN executions \> 0   
                     THEN successes::float / executions   
                     ELSE 0 END) STORED  
);

*\-- Audit log změn*  
CREATE TABLE prompt\_changelog (  
    id SERIAL PRIMARY KEY,  
    prompt\_id INTEGER REFERENCES llm\_prompts(id),  
    changed\_by VARCHAR(50),  
    changed\_at TIMESTAMP DEFAULT NOW(),  
    old\_template TEXT,  
    new\_template TEXT,  
    change\_reason TEXT

);

### **2\. Seed data (initial prompts)**

sql  
*\-- prompts/seed\_prompts.sql*  
INSERT INTO llm\_prompts (use\_case, language, prompt\_template, system\_prompt, model, notes) VALUES

*\-- Otevírací doba \- čeština*  
('opening\_hours', 'cs',   
'Převeď následující text otevírací doby do JSON formátu.  
Výstup musí být POUZE validní JSON, bez jakéhokoliv jiného textu.

Formát výstupu:  
{"days": \[{"day": "monday", "open": "09:00", "close": "17:00"}\]}

Pokud je zavřeno, použij: {"day": "monday", "closed": true}

Text k parsování:  
{text}',  
'Jsi precizní parser otevírací doby. Odpovídáš pouze validním JSON.',  
'claude-3-5-haiku-20241022',  
'Používá se když regex selže'),

*\-- Otevírací doba \- němčina*  
('opening\_hours', 'de',  
'Konvertiere die folgenden Öffnungszeiten in JSON-Format.  
Ausgabe NUR gültiges JSON, ohne weitere Erklärungen.

Ausgabeformat:  
{"days": \[{"day": "monday", "open": "09:00", "close": "17:00"}\]}

Wenn geschlossen: {"day": "monday", "closed": true}

Zu parsender Text:  
{text}',  
'Du bist ein präziser Öffnungszeiten-Parser. Du antwortest nur mit gültigem JSON.',  
'claude-3-5-haiku-20241022',  
NULL),

*\-- Business description \- čeština*  
('business\_description', 'cs',  
'Na základě následujícího textu z webové stránky shrň hlavní činnost firmy do 1-2 vět.

Zaměř se na:  
\- Co firma dělá/prodává/nabízí  
\- Hlavní obor podnikání  
\- Klíčové služby/produkty

Odpověz POUZE shrnutím, bez úvodu typu "Firma se zabývá...".

Text:  
{text}',  
'Jsi business analytik. Vytváříš stručné, faktické popisy firem.',  
'gpt-4o-mini',  
'Max 150 tokenů obvykle stačí'),

*\-- Extrakce kontaktů \- multi-language fallback*  
('contact\_extraction', 'en',  
'Extract contact information from the following text.

Return ONLY valid JSON with this structure:  
{  
  "emails": \["email1@example.com"\],  
  "phones": \["+1234567890"\],  
  "social": {  
    "facebook": "url",  
    "linkedin": "url"  
  }  
}

If nothing found, return empty arrays.

Text:  
{text}',  
'You are a contact information extractor. Output only valid JSON.',  
'llama3.2:3b',

'Local model fallback pro jednoduché extraction');

### **3\. Python wrapper s caching**

python  
*\# llm/prompt\_manager.py*  
import psycopg2  
from psycopg2.extras import RealDictCursor  
from functools import lru\_cache  
import yaml  
import os

class PromptManager:  
    def \_\_init\_\_(self, db\_conn, fallback\_config\_path\='config/prompts.yaml'):  
        self.conn \= db\_conn  
        self.fallback\_config \= self.\_load\_fallback(fallback\_config\_path)  
        self.\_cache \= {}  
      
    def \_load\_fallback(self, path):  
        """Load fallback prompts from YAML if DB fails"""  
        if os.path.exists(path):  
            with open(path, 'r', encoding\='utf-8') as f:  
                return yaml.safe\_load(f)  
        return {}  
      
    @lru\_cache(maxsize\=128)  
    def get\_prompt(self, use\_case, language\='en', version\=None):  
        """  
        Získá prompt z DB nebo fallbacku  
          
        Args:  
            use\_case: 'opening\_hours', 'business\_description', ...  
            language: 'cs', 'de', 'en', ...  
            version: specific version or None for latest active  
        """  
        try:  
            with self.conn.cursor(cursor\_factory\=RealDictCursor) as cur:  
                if version:  
                    cur.execute("""  
                        SELECT \* FROM llm\_prompts   
                        WHERE use\_case \= %s AND language \= %s AND version \= %s  
                    """, (use\_case, language, version))  
                else:  
                    cur.execute("""  
                        SELECT \* FROM llm\_prompts   
                        WHERE use\_case \= %s AND language \= %s AND is\_active \= TRUE  
                        ORDER BY version DESC LIMIT 1  
                    """, (use\_case, language))  
                  
                result \= cur.fetchone()  
                  
                if result:  
                    return dict(result)  
                  
                *\# Fallback na angličtinu*  
                if language \!= 'en':  
                    return self.get\_prompt(use\_case, 'en', version)  
                  
        except Exception as e:  
            print(f"DB prompt fetch failed: {e}, using fallback")  
          
        *\# Fallback na config file*  
        return self.\_get\_fallback\_prompt(use\_case, language)  
      
    def \_get\_fallback\_prompt(self, use\_case, language):  
        """Fallback na YAML config"""  
        prompts \= self.fallback\_config.get(use\_case, {})  
        prompt \= prompts.get(language) or prompts.get('en')  
          
        if not prompt:  
            raise ValueError(f"No prompt found for {use\_case}/{language}")  
          
        return {  
            'prompt\_template': prompt\['template'\],  
            'system\_prompt': prompt.get('system'),  
            'model': prompt.get('model', 'claude-3-5-haiku-20241022'),  
            'max\_tokens': prompt.get('max\_tokens', 200),  
            'temperature': prompt.get('temperature', 0.0)  
        }  
      
    def render\_prompt(self, use\_case, language, \*\*kwargs):  
        """  
        Získá a vyrendruje prompt s proměnnými  
          
        Usage:  
            prompt \= pm.render\_prompt('opening\_hours', 'cs', text=hours\_text)  
        """  
        config \= self.get\_prompt(use\_case, language)  
        rendered \= config\['prompt\_template'\].format(\*\*kwargs)  
          
        return {  
            'prompt': rendered,  
            'system': config.get('system\_prompt'),  
            'model': config\['model'\],  
            'max\_tokens': config\['max\_tokens'\],  
            'temperature': config.get('temperature', 0.0),  
            'prompt\_id': config.get('id')  *\# pro tracking*  
        }  
      
    def log\_usage(self, prompt\_id, success, tokens\_used, response\_time\_ms):  
        """Track prompt performance"""  
        if not prompt\_id:  
            return  
          
        try:  
            with self.conn.cursor() as cur:  
                cur.execute("""  
                    INSERT INTO prompt\_performance   
                    (prompt\_id, executions, successes, failures,   
                     avg\_tokens\_used, avg\_response\_time\_ms, last\_used\_at)  
                    VALUES (%s, 1, %s, %s, %s, %s, NOW())  
                    ON CONFLICT (prompt\_id) DO UPDATE SET  
                        executions \= prompt\_performance.executions \+ 1,  
                        successes \= prompt\_performance.successes \+ %s,  
                        failures \= prompt\_performance.failures \+ %s,  
                        avg\_tokens\_used \= (prompt\_performance.avg\_tokens\_used \*   
                                          prompt\_performance.executions \+ %s) /   
                                         (prompt\_performance.executions \+ 1),  
                        avg\_response\_time\_ms \= (prompt\_performance.avg\_response\_time\_ms \*   
                                               prompt\_performance.executions \+ %s) /   
                                              (prompt\_performance.executions \+ 1),  
                        last\_used\_at \= NOW()  
                """, (prompt\_id, 1 if success else 0, 0 if success else 1,  
                      tokens\_used, response\_time\_ms,  
                      1 if success else 0, 0 if success else 1,  
                      tokens\_used, response\_time\_ms))  
                self.conn.commit()  
        except Exception as e:  
            print(f"Failed to log prompt usage: {e}")  
      
    def update\_prompt(self, use\_case, language, new\_template, changed\_by, reason):  
        """Update prompt s changelog"""  
        with self.conn.cursor() as cur:  
            *\# Get current version*  
            cur.execute("""  
                SELECT id, version, prompt\_template   
                FROM llm\_prompts   
                WHERE use\_case \= %s AND language \= %s AND is\_active \= TRUE  
            """, (use\_case, language))  
              
            current \= cur.fetchone()  
              
            if current:  
                old\_id, old\_version, old\_template \= current  
                  
                *\# Deactivate old version*  
                cur.execute("""  
                    UPDATE llm\_prompts SET is\_active \= FALSE   
                    WHERE id \= %s  
                """, (old\_id,))  
                  
                *\# Insert new version*  
                cur.execute("""  
                    INSERT INTO llm\_prompts   
                    (use\_case, language, version, prompt\_template, created\_by)  
                    VALUES (%s, %s, %s, %s, %s)  
                    RETURNING id  
                """, (use\_case, language, old\_version \+ 1, new\_template, changed\_by))  
                  
                new\_id \= cur.fetchone()\[0\]  
                  
                *\# Log change*  
                cur.execute("""  
                    INSERT INTO prompt\_changelog   
                    (prompt\_id, changed\_by, old\_template, new\_template, change\_reason)  
                    VALUES (%s, %s, %s, %s, %s)  
                """, (new\_id, changed\_by, old\_template, new\_template, reason))  
                  
                self.conn.commit()  
                  
                *\# Clear cache*

                self.get\_prompt.cache\_clear()

### **4\. Fallback config file**

yaml  
*\# config/prompts.yaml*  
opening\_hours:  
  cs:  
    template: |  
      Převeď následující text otevírací doby do JSON formátu.  
      Výstup musí být POUZE validní JSON, bez jakéhokoliv jiného textu.  
        
      Formát: {{"days": \[{{"day": "monday", "open": "09:00", "close": "17:00"}}\]}}  
        
      Text: {text}  
    system: "Jsi precizní parser otevírací doby."  
    model: "claude-3-5-haiku-20241022"  
    max\_tokens: 200  
    temperature: 0.0  
    
  de:  
    template: |  
      Konvertiere die Öffnungszeiten in JSON.  
      Nur JSON, keine Erklärung.  
        
      Format: {{"days": \[{{"day": "monday", "open": "09:00", "close": "17:00"}}\]}}  
        
      Text: {text}  
    system: "Du bist ein Parser für Öffnungszeiten."  
    model: "claude-3-5-haiku-20241022"  
    
  en:  
    template: |  
      Convert opening hours to JSON.  
      Output only JSON.  
        
      Format: {{"days": \[{{"day": "monday", "open": "09:00", "close": "17:00"}}\]}}  
        
      Text: {text}  
    model: "llama3.2:3b"  *\# Local fallback*

business\_description:  
  cs:  
    template: |  
      Shrň hlavní činnost firmy do 1-2 vět podle textu:  
        
      {text}  
    model: "gpt-4o-mini"

    max\_tokens: 150

### **5\. Použití v kódu**

python  
*\# parser\_worker.py*  
from llm.prompt\_manager import PromptManager  
import time

pm \= PromptManager(db\_conn)

def extract\_opening\_hours(text, language):  
    """Extract s použitím managed promptu"""  
      
    *\# Render prompt*  
    config \= pm.render\_prompt('opening\_hours', language, text\=text)  
      
    start \= time.time()  
      
    try:  
        *\# Call LLM*  
        response \= call\_llm(  
            model\=config\['model'\],  
            prompt\=config\['prompt'\],  
            system\=config\['system'\],  
            max\_tokens\=config\['max\_tokens'\],  
            temperature\=config\['temperature'\]  
        )  
          
        result \= json.loads(response)  
          
        *\# Log success*  
        pm.log\_usage(  
            prompt\_id\=config.get('prompt\_id'),  
            success\=True,  
            tokens\_used\=len(response.split()),  
            response\_time\_ms\=(time.time() \- start) \* 1000  
        )  
          
        return result  
          
    except Exception as e:  
        *\# Log failure*  
        pm.log\_usage(  
            prompt\_id\=config.get('prompt\_id'),  
            success\=False,  
            tokens\_used\=0,  
            response\_time\_ms\=(time.time() \- start) \* 1000  
        )

        raise

### **6\. Admin CLI pro správu promptů**

python  
*\# scripts/prompt\_admin.py*  
import click  
from llm.prompt\_manager import PromptManager

@click.group()  
def cli():  
    pass

@cli.command()  
@click.argument('use\_case')  
@click.argument('language')  
def show(use\_case, language):  
    """Zobrazí aktivní prompt"""  
    pm \= PromptManager(get\_db())  
    config \= pm.get\_prompt(use\_case, language)  
      
    click.echo(f"Use case: {use\_case}/{language}")  
    click.echo(f"Model: {config\['model'\]}")  
    click.echo(f"Version: {config.get('version', 'fallback')}")  
    click.echo("\\nTemplate:")  
    click.echo(config\['prompt\_template'\])

@cli.command()  
@click.argument('use\_case')  
@click.argument('language')  
@click.option('--file', type\=click.File('r'), help\='Read template from file')  
def update(use\_case, language, file):  
    """Update prompt"""  
    new\_template \= file.read() if file else click.edit()  
      
    if not new\_template:  
        click.echo("Aborted")  
        return  
      
    changed\_by \= click.prompt("Your name")  
    reason \= click.prompt("Reason for change")  
      
    pm \= PromptManager(get\_db())  
    pm.update\_prompt(use\_case, language, new\_template, changed\_by, reason)  
      
    click.echo("✓ Prompt updated")

@cli.command()  
@click.argument('use\_case')  
@click.argument('language')  
def stats(use\_case, language):  
    """Performance statistiky"""  
    pm \= PromptManager(get\_db())  
    config \= pm.get\_prompt(use\_case, language)  
      
    with get\_db().cursor() as cur:  
        cur.execute("""  
            SELECT executions, success\_rate, avg\_tokens\_used, avg\_response\_time\_ms  
            FROM prompt\_performance  
            WHERE prompt\_id \= %s  
        """, (config.get('id'),))  
          
        row \= cur.fetchone()  
        if row:  
            execs, success, tokens, time\_ms \= row  
            click.echo(f"Executions: {execs}")  
            click.echo(f"Success rate: {success:.1%}")  
            click.echo(f"Avg tokens: {tokens:.0f}")  
            click.echo(f"Avg response: {time\_ms:.0f}ms")

@cli.command()  
def list\_all():  
    """Seznam všech promptů"""  
    with get\_db().cursor() as cur:  
        cur.execute("""  
            SELECT use\_case, language, version, is\_active, model  
            FROM llm\_prompts  
            ORDER BY use\_case, language, version DESC  
        """)  
          
        for row in cur.fetchall():  
            active \= "✓" if row\[3\] else " "  
            click.echo(f"{active} {row\[0\]}/{row\[1\]} v{row\[2\]} ({row\[4\]})")

if \_\_name\_\_ \== '\_\_main\_\_':

    cli()

### **Použití CLI:**

bash  
*\# Zobraz prompt*  
python prompt\_admin.py show opening\_hours cs

*\# Update z editoru*  
python prompt\_admin.py update opening\_hours cs

*\# Update ze souboru*  
python prompt\_admin.py update opening\_hours de \--file prompts/oh\_de\_v2.txt

*\# Stats*  
python prompt\_admin.py stats opening\_hours cs

*\# List*

python prompt\_admin.py list-all

---

## **Výhody tohoto řešení:**

✅ **Prompty v DB** \- snadná editace bez deploymentu  
 ✅ **Fallback config** \- funguje i bez DB  
 ✅ **Verzování** \- track změn, rollback možný  
 ✅ **Performance tracking** \- vidíš co funguje  
 ✅ **Multi-language** \- centrální správa všech jazyků  
 ✅ **A/B testing ready** \- můžeš mít více verzí paralelně  
 ✅ **CLI tools** \- rychlá správa z terminálu

Takto to dává mnohem větší smysl?

Pokud db spadne aplikace nefunguje. Je korektní předpoklad. A není potřeba s tím bojovat. Není to ha aplikace 24/7 pod zátěží. Spíš občas dostane data a v klidu je projde a zpracuje minuta sem minuta tam...

4:47 PM

**Perfektní přístup.** Máš úplně pravdu \- pro batch processing, kde není time-critical SLA, je zbytečné řešit fallbacky a složitou resilience.

## **Zjednodušená verze \- jen DB**

sql  
*\-- Prompty přímo v DB, žádné fallbacky*  
CREATE TABLE llm\_prompts (  
    id SERIAL PRIMARY KEY,  
    use\_case VARCHAR(50) NOT NULL,  
    language VARCHAR(5) NOT NULL,  
    prompt\_template TEXT NOT NULL,  
    system\_prompt TEXT,  
    model VARCHAR(50) DEFAULT 'claude-3-5-haiku-20241022',  
    max\_tokens INTEGER DEFAULT 200,  
    temperature FLOAT DEFAULT 0.0,  
      
    is\_active BOOLEAN DEFAULT TRUE,  
    created\_at TIMESTAMP DEFAULT NOW(),  
    notes TEXT,  
      
    UNIQUE(use\_case, language)  *\-- jen jedna aktivní verze per use\_case/lang*  
);

*\-- Jednoduchý performance tracking*  
CREATE TABLE prompt\_stats (  
    prompt\_id INTEGER REFERENCES llm\_prompts(id),  
    date DATE DEFAULT CURRENT\_DATE,  
    executions INTEGER DEFAULT 0,  
    successes INTEGER DEFAULT 0,  
    avg\_tokens INTEGER,  
      
    PRIMARY KEY (prompt\_id, date)

);

## **Zjednodušený Python wrapper**

python  
*\# llm/prompts.py*  
from psycopg2.extras import RealDictCursor

class PromptManager:  
    def \_\_init\_\_(self, db\_conn):  
        self.conn \= db\_conn  
      
    def get\_prompt(self, use\_case, language\='cs'):  
        """Prostě SELECT z DB, hotovo"""  
        with self.conn.cursor(cursor\_factory\=RealDictCursor) as cur:  
            cur.execute("""  
                SELECT prompt\_template, system\_prompt, model, max\_tokens, temperature, id  
                FROM llm\_prompts   
                WHERE use\_case \= %s AND language \= %s AND is\_active \= TRUE  
            """, (use\_case, language))  
              
            result \= cur.fetchone()  
              
            if not result:  
                *\# Fallback na angličtinu*  
                cur.execute("""  
                    SELECT prompt\_template, system\_prompt, model, max\_tokens, temperature, id  
                    FROM llm\_prompts   
                    WHERE use\_case \= %s AND language \= 'en' AND is\_active \= TRUE  
                """, (use\_case,))  
                result \= cur.fetchone()  
              
            if not result:  
                raise ValueError(f"No prompt for {use\_case}/{language}")  
              
            return dict(result)  
      
    def render(self, use\_case, language, \*\*variables):  
        """Získá prompt a doplní proměnné"""  
        config \= self.get\_prompt(use\_case, language)  
          
        return {  
            'prompt': config\['prompt\_template'\].format(\*\*variables),  
            'system': config\['system\_prompt'\],  
            'model': config\['model'\],  
            'max\_tokens': config\['max\_tokens'\],  
            'temperature': config\['temperature'\],  
            'prompt\_id': config\['id'\]  
        }  
      
    def log\_execution(self, prompt\_id, success\=True, tokens\=0):  
        """Prostý counter, den po dni"""  
        with self.conn.cursor() as cur:  
            cur.execute("""  
                INSERT INTO prompt\_stats (prompt\_id, executions, successes, avg\_tokens)  
                VALUES (%s, 1, %s, %s)  
                ON CONFLICT (prompt\_id, date) DO UPDATE SET  
                    executions \= prompt\_stats.executions \+ 1,  
                    successes \= prompt\_stats.successes \+ EXCLUDED.successes,  
                    avg\_tokens \= (prompt\_stats.avg\_tokens \* prompt\_stats.executions \+ %s)   
                                 / (prompt\_stats.executions \+ 1\)  
            """, (prompt\_id, 1 if success else 0, tokens, tokens))

            self.conn.commit()

## **Použití v kódu**

python  
*\# parser\_worker.py*  
pm \= PromptManager(db\_conn)

def extract\_opening\_hours(text, language):  
    config \= pm.render('opening\_hours', language, text\=text)  
      
    response \= call\_llm(  
        model\=config\['model'\],  
        prompt\=config\['prompt'\],  
        system\=config\['system'\],  
        max\_tokens\=config\['max\_tokens'\]  
    )  
      
    pm.log\_execution(config\['prompt\_id'\], success\=True, tokens\=len(response))

    return json.loads(response)

## **Jednoduchý admin CLI**

python  
*\# scripts/prompts.py*  
import click  
import psycopg2

@click.group()  
def cli():  
    pass

@cli.command()  
@click.argument('use\_case')  
@click.argument('language')  
def show(use\_case, language):  
    """Zobraz prompt"""  
    conn \= psycopg2.connect(...)  
    cur \= conn.cursor()  
      
    cur.execute("""  
        SELECT prompt\_template, model FROM llm\_prompts   
        WHERE use\_case=%s AND language=%s  
    """, (use\_case, language))  
      
    template, model \= cur.fetchone()  
    click.echo(f"Model: {model}\\n")  
    click.echo(template)

@cli.command()  
@click.argument('use\_case')  
@click.argument('language')  
def edit(use\_case, language):  
    """Edituj prompt v $EDITOR"""  
    conn \= psycopg2.connect(...)  
    cur \= conn.cursor()  
      
    *\# Načti current*  
    cur.execute("SELECT prompt\_template FROM llm\_prompts WHERE use\_case=%s AND language=%s",   
                (use\_case, language))  
    current \= cur.fetchone()  
    current\_text \= current\[0\] if current else ""  
      
    *\# Edituj*  
    new\_text \= click.edit(current\_text)  
    if not new\_text:  
        return  
      
    *\# Ulož*  
    cur.execute("""  
        INSERT INTO llm\_prompts (use\_case, language, prompt\_template)  
        VALUES (%s, %s, %s)  
        ON CONFLICT (use\_case, language) DO UPDATE   
        SET prompt\_template \= EXCLUDED.prompt\_template  
    """, (use\_case, language, new\_text))  
      
    conn.commit()  
    click.echo("✓ Saved")

@cli.command()  
def stats():  
    """Poslední týden usage"""  
    conn \= psycopg2.connect(...)  
    cur \= conn.cursor()  
      
    cur.execute("""  
        SELECT p.use\_case, p.language,   
               SUM(s.executions) as total,   
               AVG(s.successes::float/s.executions) as success\_rate  
        FROM llm\_prompts p  
        JOIN prompt\_stats s ON p.id \= s.prompt\_id  
        WHERE s.date \> CURRENT\_DATE \- 7  
        GROUP BY p.use\_case, p.language  
        ORDER BY total DESC  
    """)  
      
    for row in cur:  
        click.echo(f"{row\[0\]}/{row\[1\]}: {row\[2\]} calls, {row\[3\]:.1%} success")

if \_\_name\_\_ \== '\_\_main\_\_':

    cli()

## **Initial seed promptů**

sql  
*\-- migrations/002\_seed\_prompts.sql*  
INSERT INTO llm\_prompts (use\_case, language, prompt\_template, system\_prompt, model) VALUES

('opening\_hours', 'cs',   
'Převeď otevírací dobu do JSON.  
Formát: {"days": \[{"day": "monday", "open": "09:00", "close": "17:00"}\]}

Text: {text}',  
'Odpovídáš pouze JSON.',   
'claude-3-5-haiku-20241022'),

('opening\_hours', 'de',  
'Konvertiere in JSON.  
Format: {"days": \[{"day": "monday", "open": "09:00", "close": "17:00"}\]}

Text: {text}',  
'Nur JSON.',  
'claude-3-5-haiku-20241022'),

('opening\_hours', 'en',  
'Convert to JSON.  
Format: {"days": \[{"day": "monday", "open": "09:00", "close": "17:00"}\]}

Text: {text}',  
'JSON only.',  
'llama3.2:3b'),

('business\_description', 'cs',  
'Shrň činnost firmy do 1-2 vět:

{text}',  
NULL,

'gpt-4o-mini');

## **Workflow**

bash  
*\# Setup*  
psql \-d scraper \< migrations/002\_seed\_prompts.sql

*\# Běžná práce*  
python scripts/prompts.py show opening\_hours cs  
python scripts/prompts.py edit opening\_hours cs  
python scripts/prompts.py stats

*\# Workers prostě jedou, pokud DB běží*  
python workers/scraper.py

python workers/parser.py

---

**Pokud DB spadne:**

* Workers prostě skončí s chybou  
* Nic se neděje, žádná data nejsou ztracená  
* Restart DB, restart workers, pokračuje se dál  
* Pro batch processing je to naprosto OK

**Výhody:**

* 🎯 Jednoduchý kód (\~50 řádků místo 200\)  
* 🎯 Žádné komplexní fallbacky  
* 🎯 Žádné cache invalidace starosti  
* 🎯 Stačí jedna source of truth (DB)  
* 🎯 Prompty editovatelné přes SQL nebo CLI

Takhle je to mnohem čistší, souhlasíš?

Ano. Myslím že základní představu máme. Takže postupný plán. Seznam kroku. Pro implementaci a Postup při testování . Plán by měl sloužit agentům aby byli schopni bez většího pobízení pracovat na implementaci.

6:49 PM

# **Implementační plán \- Web Scraping Project**

## **Fáze 0: Setup projektu (1-2 hodiny)**

### **0.1 Inicializace projektu**

bash  
*\# Vytvoř strukturu*  
mkdir web-scraper && cd web-scraper  
mkdir \-p {src/{workers,models,utils,llm},migrations,scripts,config,tests}  
touch README.md .env.example .gitignore

*\# UV init*  
uv init  
uv venv

source .venv/bin/activate  *\# nebo .venv\\Scripts\\activate na Windows*

### **0.2 Dependencies**

bash  
*\# pyproject.toml \- přidej dependencies*  
uv add psycopg2-binary playwright beautifulsoup4 lxml langdetect  
uv add spacy click pyyaml python-dotenv phonenumbers  
uv add pybloom-live

*\# Development dependencies*  
uv add \--dev pytest pytest-cov black ruff

*\# Stáhni spaCy modely (jen co potřebuješ teď)*  
uv run python \-m spacy download cs\_core\_news\_lg

uv run python \-m spacy download en\_core\_web\_lg

### **0.3 Database setup**

sql  
*\-- migrations/001\_initial\_schema.sql*  
CREATE DATABASE web\_scraper;

CREATE TABLE scrape\_queue (  
    id SERIAL PRIMARY KEY,  
    url TEXT NOT NULL,  
    unit\_listing\_id INTEGER,  
    parent\_scrape\_id INTEGER,  
    depth INTEGER DEFAULT 0,  
    priority INTEGER DEFAULT 0,  
    status VARCHAR(20) DEFAULT 'pending',  
    retry\_count INTEGER DEFAULT 0,  
    next\_scrape\_at TIMESTAMP DEFAULT NOW(),  
    added\_at TIMESTAMP DEFAULT NOW(),  
    UNIQUE(url, unit\_listing\_id)  
);

CREATE INDEX idx\_queue\_status ON scrape\_queue(status, next\_scrape\_at);  
CREATE INDEX idx\_queue\_unit ON scrape\_queue(unit\_listing\_id);

CREATE TABLE scrape\_results (  
    id SERIAL PRIMARY KEY,  
    queue\_id INTEGER REFERENCES scrape\_queue(id),  
    url TEXT NOT NULL,  
    html TEXT,  
    status\_code INTEGER,  
    headers JSONB,  
    ip\_address INET,  
    redirected\_from TEXT,  
    detected\_language VARCHAR(5),  
    language\_confidence FLOAT,  
    scraped\_at TIMESTAMP DEFAULT NOW(),  
    processing\_status VARCHAR(20) DEFAULT 'new',  
    error\_message TEXT  
);

CREATE INDEX idx\_results\_processing ON scrape\_results(processing\_status);  
CREATE INDEX idx\_results\_language ON scrape\_results(detected\_language);

CREATE TABLE parsed\_data (  
    id SERIAL PRIMARY KEY,  
    scrape\_result\_id INTEGER REFERENCES scrape\_results(id),  
    unit\_listing\_id INTEGER,  
    content\_language VARCHAR(5),  
    data JSONB,  
    quality\_score INTEGER,  
    extracted\_at TIMESTAMP DEFAULT NOW()  
);

CREATE INDEX idx\_parsed\_unit ON parsed\_data(unit\_listing\_id);  
CREATE INDEX idx\_parsed\_quality ON parsed\_data(quality\_score);

CREATE TABLE change\_history (  
    id SERIAL PRIMARY KEY,  
    unit\_listing\_id INTEGER NOT NULL,  
    field\_name VARCHAR(100),  
    old\_value TEXT,  
    new\_value TEXT,  
    detected\_at TIMESTAMP DEFAULT NOW()  
);

CREATE INDEX idx\_changes\_unit ON change\_history(unit\_listing\_id);  
CREATE INDEX idx\_changes\_date ON change\_history(detected\_at);

CREATE TABLE domain\_blacklist (  
    domain TEXT PRIMARY KEY,  
    reason VARCHAR(50),  
    fail\_count INTEGER DEFAULT 0,  
    first\_failed\_at TIMESTAMP,  
    last\_failed\_at TIMESTAMP,  
    auto\_added BOOLEAN DEFAULT TRUE,  
    notes TEXT  
);

CREATE TABLE domain\_multipage\_rules (  
    domain TEXT PRIMARY KEY,  
    url\_patterns JSONB,  
    max\_depth INTEGER DEFAULT 2,  
    enabled BOOLEAN DEFAULT TRUE  
);

CREATE TABLE bloom\_filters (  
    id SERIAL PRIMARY KEY,  
    name VARCHAR(50) UNIQUE,  
    filter\_data BYTEA,  
    item\_count INTEGER DEFAULT 0,  
    false\_positive\_rate FLOAT DEFAULT 0.001,  
    created\_at TIMESTAMP DEFAULT NOW(),  
    last\_updated TIMESTAMP DEFAULT NOW()  
);

CREATE TABLE bloom\_filter\_items (  
    filter\_name VARCHAR(50),  
    item TEXT,  
    added\_at TIMESTAMP DEFAULT NOW(),  
    source VARCHAR(50),  
    PRIMARY KEY (filter\_name, item)  
);

CREATE TABLE llm\_prompts (  
    id SERIAL PRIMARY KEY,  
    use\_case VARCHAR(50) NOT NULL,  
    language VARCHAR(5) NOT NULL,  
    prompt\_template TEXT NOT NULL,  
    system\_prompt TEXT,  
    model VARCHAR(50) DEFAULT 'claude-3-5-haiku-20241022',  
    max\_tokens INTEGER DEFAULT 200,  
    temperature FLOAT DEFAULT 0.0,  
    is\_active BOOLEAN DEFAULT TRUE,  
    created\_at TIMESTAMP DEFAULT NOW(),  
    notes TEXT,  
    UNIQUE(use\_case, language)  
);

CREATE TABLE prompt\_stats (  
    prompt\_id INTEGER REFERENCES llm\_prompts(id),  
    date DATE DEFAULT CURRENT\_DATE,  
    executions INTEGER DEFAULT 0,  
    successes INTEGER DEFAULT 0,  
    avg\_tokens INTEGER,  
    PRIMARY KEY (prompt\_id, date)  
);

CREATE TABLE config (  
    key TEXT PRIMARY KEY,  
    value TEXT,  
    description TEXT

);

bash  
*\# Aplikuj migraci*

psql \-U postgres \< migrations/001\_initial\_schema.sql

### **0.4 Config files**

python  
*\# .env.example*  
DATABASE\_URL\=postgresql://user:password@localhost:5432/web\_scraper  
SCRAPE\_DELAY\_SECONDS\=2  
MAX\_RETRIES\=3  
PLAYWRIGHT\_HEADLESS\=true  
USER\_AGENT\=Mozilla/5.0 (compatible; YourBot/1.0)

*\# API keys (optional)*  
ANTHROPIC\_API\_KEY\=

OPENAI\_API\_KEY\=

python  
*\# config/settings.py*  
from dotenv import load\_dotenv  
import os

load\_dotenv()

DATABASE\_URL \= os.getenv('DATABASE\_URL')  
SCRAPE\_DELAY \= int(os.getenv('SCRAPE\_DELAY\_SECONDS', 2))  
MAX\_RETRIES \= int(os.getenv('MAX\_RETRIES', 3))

USER\_AGENT \= os.getenv('USER\_AGENT')

---

## **Fáze 1: Core utilities (2-3 hodiny)**

### **1.1 Database connector**

python  
*\# src/utils/db.py*  
import psycopg2  
from psycopg2.extras import RealDictCursor  
from config.settings import DATABASE\_URL

def get\_db\_connection():  
    """Vytvoř DB connection"""  
    return psycopg2.connect(DATABASE\_URL)

def get\_cursor(conn, dict\_cursor\=True):  
    """Vytvoř cursor"""  
    if dict\_cursor:  
        return conn.cursor(cursor\_factory\=RealDictCursor)

    return conn.cursor()

**Test:**

python  
*\# tests/test\_db.py*  
from src.utils.db import get\_db\_connection

def test\_db\_connection():  
    conn \= get\_db\_connection()  
    assert conn is not None  
    cur \= conn.cursor()  
    cur.execute("SELECT 1")  
    assert cur.fetchone()\[0\] \== 1

    conn.close()

### **1.2 Language detection**

python  
*\# src/utils/language.py*  
from langdetect import detect\_langs  
from bs4 import BeautifulSoup

def detect\_language(html):  
    """  
    Detekuje jazyk z HTML  
    Returns: (language\_code, confidence)  
    """  
    *\# Zkus HTML lang attribute*  
    soup \= BeautifulSoup(html, 'lxml')  
    html\_tag \= soup.find('html')  
    if html\_tag and html\_tag.get('lang'):  
        lang \= html\_tag.get('lang')\[:2\].lower()  
        return lang, 0.99  
      
    *\# Extract text*  
    text \= soup.get\_text(separator\=' ', strip\=True)  
    text \= ' '.join(text.split())\[:10000\]  
      
    if len(text) \< 50:  
        return 'unknown', 0.0  
      
    try:  
        results \= detect\_langs(text)  
        return results\[0\].lang, results\[0\].prob  
    except:

        return 'unknown', 0.0

**Test:**

python  
*\# tests/test\_language.py*  
from src.utils.language import detect\_language

def test\_detect\_czech():  
    html \= '\<html\>\<body\>Dobrý den, vítejte na našich stránkách.\</body\>\</html\>'  
    lang, conf \= detect\_language(html)  
    assert lang \== 'cs'  
    assert conf \> 0.9

def test\_detect\_from\_html\_tag():  
    html \= '\<html lang="de"\>\<body\>Hello\</body\>\</html\>'  
    lang, conf \= detect\_language(html)  
    assert lang \== 'de'

    assert conf \== 0.99

### **1.3 URL utilities**

python  
*\# src/utils/urls.py*  
from urllib.parse import urlparse, urljoin  
import re

def normalize\_url(url):  
    """Normalizuje URL pro deduplikaci"""  
    url \= url.lower().strip()  
    url \= re.sub(r'/$', '', url)  *\# remove trailing slash*  
    url \= re.sub(r'\#.\*$', '', url)  *\# remove fragment*  
    url \= re.sub(r'\\?.\*$', '', url)  *\# remove query params (optional)*  
    return url

def extract\_domain(url):  
    """Extrahuje doménu z URL"""  
    parsed \= urlparse(url)  
    return parsed.netloc.lower()

def same\_domain(url1, url2):  
    """Kontroluje zda jsou URL ze stejné domény"""  
    return extract\_domain(url1) \== extract\_domain(url2)

def is\_valid\_url(url):  
    """Základní validace URL"""  
    try:  
        result \= urlparse(url)  
        return all(\[result.scheme, result.netloc\])  
    except:

        return False

**Test:**

python  
*\# tests/test\_urls.py*  
from src.utils.urls import normalize\_url, extract\_domain, same\_domain

def test\_normalize\_url():  
    assert normalize\_url('https://Example.com/') \== 'https://example.com'  
    assert normalize\_url('http://test.com\#anchor') \== 'http://test.com'

def test\_extract\_domain():  
    assert extract\_domain('https://www.example.com/path') \== 'www.example.com'

def test\_same\_domain():  
    assert same\_domain('https://test.com/a', 'https://test.com/b') \== True

    assert same\_domain('https://test.com', 'https://other.com') \== False

---

## **Fáze 2: Scraper worker (3-4 hodiny)**

### **2.1 Basic scraper**

python  
*\# src/workers/scraper.py*  
import time  
from playwright.sync\_api import sync\_playwright  
from bs4 import BeautifulSoup  
import socket  
from src.utils.db import get\_db\_connection, get\_cursor  
from src.utils.language import detect\_language  
from src.utils.urls import extract\_domain, normalize\_url  
from config.settings import SCRAPE\_DELAY, USER\_AGENT, MAX\_RETRIES

class Scraper:  
    def \_\_init\_\_(self):  
        self.conn \= get\_db\_connection()  
        self.last\_domain\_access \= {}  
      
    def get\_next\_url(self):  
        """Získá další URL z fronty"""  
        with get\_cursor(self.conn) as cur:  
            cur.execute("""  
                SELECT id, url, unit\_listing\_id, retry\_count  
                FROM scrape\_queue  
                WHERE status \= 'pending'  
                  AND next\_scrape\_at \<= NOW()  
                  AND url NOT LIKE ANY(  
                      SELECT '%' || domain || '%' FROM domain\_blacklist  
                  )  
                ORDER BY priority DESC, added\_at ASC  
                LIMIT 1  
                FOR UPDATE SKIP LOCKED  
            """)  
            return cur.fetchone()  
      
    def respect\_rate\_limit(self, domain):  
        """Enforce delay between requests na stejnou doménu"""  
        if domain in self.last\_domain\_access:  
            elapsed \= time.time() \- self.last\_domain\_access\[domain\]  
            if elapsed \< SCRAPE\_DELAY:  
                time.sleep(SCRAPE\_DELAY \- elapsed)  
          
        self.last\_domain\_access\[domain\] \= time.time()  
      
    def scrape\_url(self, url):  
        """  
        Stáhne HTML z URL  
        Returns: dict s html, status\_code, headers, ip, redirects  
        """  
        domain \= extract\_domain(url)  
        self.respect\_rate\_limit(domain)  
          
        result \= {  
            'html': None,  
            'status\_code': None,  
            'headers': {},  
            'ip\_address': None,  
            'redirected\_from': None,  
            'error': None  
        }  
          
        try:  
            *\# Resolve IP*  
            result\['ip\_address'\] \= socket.gethostbyname(domain)  
              
            *\# Playwright scrape (fallback: httpx pro static pages)*  
            with sync\_playwright() as p:  
                browser \= p.chromium.launch(headless\=True)  
                context \= browser.new\_context(user\_agent\=USER\_AGENT)  
                page \= context.new\_page()  
                  
                response \= page.goto(url, wait\_until\='networkidle', timeout\=30000)  
                  
                result\['status\_code'\] \= response.status  
                result\['headers'\] \= dict(response.headers)  
                  
                *\# Check redirects*  
                if response.url \!= url:  
                    result\['redirected\_from'\] \= url  
                  
                if response.status \== 200:  
                    result\['html'\] \= page.content()  
                  
                browser.close()  
          
        except Exception as e:  
            result\['error'\] \= str(e)  
          
        return result  
      
    def save\_result(self, queue\_id, url, scrape\_result):  
        """Uloží výsledek scrape"""  
        with get\_cursor(self.conn, dict\_cursor\=False) as cur:  
            *\# Detekce jazyka*  
            lang, lang\_conf \= 'unknown', 0.0  
            if scrape\_result\['html'\]:  
                lang, lang\_conf \= detect\_language(scrape\_result\['html'\])  
              
            cur.execute("""  
                INSERT INTO scrape\_results   
                (queue\_id, url, html, status\_code, headers, ip\_address,   
                 redirected\_from, detected\_language, language\_confidence, error\_message)  
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)  
                RETURNING id  
            """, (  
                queue\_id, url, scrape\_result\['html'\], scrape\_result\['status\_code'\],  
                scrape\_result.get('headers'), scrape\_result.get('ip\_address'),  
                scrape\_result.get('redirected\_from'), lang, lang\_conf,  
                scrape\_result.get('error')  
            ))  
              
            result\_id \= cur.fetchone()\[0\]  
            self.conn.commit()  
            return result\_id  
      
    def update\_queue\_status(self, queue\_id, status, retry\_count\=None, next\_scrape\_at\=None):  
        """Update stav fronty"""  
        with get\_cursor(self.conn, dict\_cursor\=False) as cur:  
            if retry\_count is not None:  
                cur.execute("""  
                    UPDATE scrape\_queue   
                    SET status \= %s, retry\_count \= %s, next\_scrape\_at \= %s  
                    WHERE id \= %s  
                """, (status, retry\_count, next\_scrape\_at, queue\_id))  
            else:  
                cur.execute("""  
                    UPDATE scrape\_queue SET status \= %s WHERE id \= %s  
                """, (status, queue\_id))  
              
            self.conn.commit()  
      
    def process\_one(self):  
        """Zpracuje jedno URL"""  
        item \= self.get\_next\_url()  
        if not item:  
            return False  
          
        queue\_id \= item\['id'\]  
        url \= item\['url'\]  
        retry\_count \= item\['retry\_count'\]  
          
        print(f"Scraping: {url}")  
          
        *\# Mark as processing*  
        self.update\_queue\_status(queue\_id, 'processing')  
          
        *\# Scrape*  
        result \= self.scrape\_url(url)  
          
        *\# Save*  
        self.save\_result(queue\_id, url, result)  
          
        *\# Update queue*  
        if result\['status\_code'\] \== 200 and result\['html'\]:  
            self.update\_queue\_status(queue\_id, 'completed')  
        elif retry\_count \>= MAX\_RETRIES:  
            self.update\_queue\_status(queue\_id, 'failed')  
            *\# TODO: možná přidat do blacklistu*  
        else:  
            *\# Retry za hodinu*  
            import datetime  
            next\_try \= datetime.datetime.now() \+ datetime.timedelta(hours\=1)  
            self.update\_queue\_status(queue\_id, 'pending', retry\_count \+ 1, next\_try)  
          
        return True  
      
    def run(self, max\_items\=None):  
        """Main loop"""  
        processed \= 0  
          
        while True:  
            if max\_items and processed \>= max\_items:  
                break  
              
            if not self.process\_one():  
                print("Queue empty, waiting...")  
                time.sleep(60)  
                continue  
              
            processed \+= 1  
          
        self.conn.close()

if \_\_name\_\_ \== '\_\_main\_\_':  
    scraper \= Scraper()

    scraper.run()

**Test:**

python  
*\# tests/test\_scraper.py*  
import pytest  
from src.workers.scraper import Scraper  
from src.utils.db import get\_db\_connection

@pytest.fixture  
def scraper():  
    return Scraper()

def test\_scrape\_google(scraper):  
    """Test scraping simple page"""  
    result \= scraper.scrape\_url('https://www.google.com')  
    assert result\['status\_code'\] \== 200  
    assert result\['html'\] is not None  
    assert 'google' in result\['html'\].lower()

def test\_queue\_processing(scraper):  
    """Test queue pick \+ process"""  
    *\# Insert test URL*  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
    cur.execute("""  
        INSERT INTO scrape\_queue (url, unit\_listing\_id)  
        VALUES ('https://example.com', 1\)  
    """)  
    conn.commit()  
      
    *\# Process*  
    success \= scraper.process\_one()  
    assert success \== True  
      
    *\# Check result saved*  
    cur.execute("SELECT COUNT(\*) FROM scrape\_results WHERE url \= 'https://example.com'")

    assert cur.fetchone()\[0\] \== 1

---

## **Fáze 3: Parser worker \- Regex extraction (3-4 hodiny)**

### **3.1 Regex patterns**

python  
*\# src/utils/patterns.py*  
import re

PATTERNS \= {  
    'email': r'\[a-zA-Z0-9.\_%+-\]+@\[a-zA-Z0-9.-\]+\\.\[a-zA-Z\]{2,}',  
      
    'phone': {  
        'cs': r'\\+?420\\s?\\d{3}\\s?\\d{3}\\s?\\d{3}',  
        'sk': r'\\+?421\\s?\\d{3}\\s?\\d{3}\\s?\\d{3}',  
        'de': r'\\+?49\\s?\\d{3,4}\\s?\\d{3,8}',  
        'nl': r'\\+?31\\s?\\d{2,3}\\s?\\d{6,7}',  
        'fr': r'\\+?33\\s?\\d{1}\\s?\\d{2}\\s?\\d{2}\\s?\\d{2}\\s?\\d{2}',  
        'en': r'\\+?44\\s?\\d{4}\\s?\\d{6}',  
    },  
      
    'ico': {  
        'cs': r'\\b(IČO?:?\\s\*)?(\\d{8})\\b',  
        'sk': r'\\b(IČO?:?\\s\*)?(\\d{8})\\b',  
    },  
      
    'social\_media': {  
        'facebook': r'(?:https?://)?(?:www\\.)?facebook\\.com/\[\\w\\-\\.\]+',  
        'linkedin': r'(?:https?://)?(?:www\\.)?linkedin\\.com/(?:company|in)/\[\\w\\-\]+',  
        'instagram': r'(?:https?://)?(?:www\\.)?instagram\\.com/\[\\w\\-\\.\]+',  
    }  
}

def extract\_emails(text):  
    """Extract všechny emaily"""  
    return list(set(re.findall(PATTERNS\['email'\], text, re.IGNORECASE)))

def extract\_phones(text, language\='cs'):  
    """Extract telefony podle jazyka"""  
    pattern \= PATTERNS\['phone'\].get(language, PATTERNS\['phone'\]\['cs'\])  
    phones \= re.findall(pattern, text)  
    return \[re.sub(r'\\s', '', p) for p in phones\]  *\# normalize*

def extract\_ico(text, language\='cs'):  
    """Extract IČO"""  
    pattern \= PATTERNS\['ico'\].get(language)  
    if not pattern:  
        return None  
      
    matches \= re.findall(pattern, text)  
    if matches:  
        *\# Vrať samotné číslo (bez "IČO:" prefixu)*  
        return matches\[0\]\[1\] if isinstance(matches\[0\], tuple) else matches\[0\]  
    return None

def extract\_social\_media(text):  
    """Extract social media links"""  
    result \= {}  
    for platform, pattern in PATTERNS\['social\_media'\].items():  
        matches \= re.findall(pattern, text, re.IGNORECASE)  
        if matches:  
            result\[platform\] \= matches\[0\]

    return result

**Test:**

python  
*\# tests/test\_patterns.py*  
from src.utils.patterns import extract\_emails, extract\_phones, extract\_ico

def test\_extract\_email():  
    text \= "Kontakt: info@firma.cz a podpora@firma.cz"  
    emails \= extract\_emails(text)  
    assert 'info@firma.cz' in emails  
    assert len(emails) \== 2

def test\_extract\_phone\_cs():  
    text \= "Telefon: \+420 123 456 789"  
    phones \= extract\_phones(text, 'cs')  
    assert '+420123456789' in phones

def test\_extract\_ico():  
    text \= "IČO: 12345678"  
    ico \= extract\_ico(text, 'cs')

    assert ico \== '12345678'

### **3.2 Basic parser**

python  
*\# src/workers/parser.py*  
from bs4 import BeautifulSoup  
import json  
from src.utils.db import get\_db\_connection, get\_cursor  
from src.utils.patterns import (  
    extract\_emails, extract\_phones, extract\_ico, extract\_social\_media  
)

class Parser:  
    def \_\_init\_\_(self):  
        self.conn \= get\_db\_connection()  
      
    def get\_next\_scrape\_result(self):  
        """Získá další scrape\_result k parsování"""  
        with get\_cursor(self.conn) as cur:  
            cur.execute("""  
                SELECT id, html, detected\_language, url  
                FROM scrape\_results  
                WHERE processing\_status \= 'new'  
                  AND html IS NOT NULL  
                ORDER BY scraped\_at ASC  
                LIMIT 1  
                FOR UPDATE SKIP LOCKED  
            """)  
            return cur.fetchone()  
      
    def extract\_structured\_data(self, soup):  
        """Extract JSON-LD, microdata, OpenGraph"""  
        data \= {}  
          
        *\# JSON-LD*  
        json\_ld \= soup.find('script', type\='application/ld+json')  
        if json\_ld:  
            try:  
                data\['json\_ld'\] \= json.loads(json\_ld.string)  
            except:  
                pass  
          
        *\# OpenGraph*  
        og\_tags \= soup.find\_all('meta', property\=lambda x: x and x.startswith('og:'))  
        if og\_tags:  
            data\['opengraph'\] \= {  
                tag.get('property')\[3:\]: tag.get('content')   
                for tag in og\_tags  
            }  
          
        return data  
      
    def extract\_text\_content(self, soup):  
        """Extract plain text z HTML"""  
        *\# Remove script, style*  
        for elem in soup(\['script', 'style', 'nav', 'footer'\]):  
            elem.decompose()  
          
        return soup.get\_text(separator\=' ', strip\=True)  
      
    def parse\_html(self, html, language, url):  
        """  
        Parse HTML a extrahuje data  
        Returns: dict s extracted data  
        """  
        soup \= BeautifulSoup(html, 'lxml')  
        text \= self.extract\_text\_content(soup)  
          
        data \= {  
            'url': url,  
            'language': language,  
            'emails': extract\_emails(text),  
            'phones': extract\_phones(text, language),  
            'ico': extract\_ico(text, language),  
            'social\_media': extract\_social\_media(text),  
        }  
          
        *\# Structured data*  
        structured \= self.extract\_structured\_data(soup)  
        if structured:  
            data\['structured'\] \= structured  
          
        *\# Company name attempts*  
        *\# 1\. JSON-LD*  
        if 'json\_ld' in structured and structured\['json\_ld'\].get('name'):  
            data\['company\_name'\] \= structured\['json\_ld'\]\['name'\]  
        *\# 2\. OpenGraph*  
        elif 'opengraph' in structured and structured\['opengraph'\].get('site\_name'):  
            data\['company\_name'\] \= structured\['opengraph'\]\['site\_name'\]  
        *\# 3\. Title tag*  
        elif soup.title:  
            data\['company\_name'\] \= soup.title.string.strip()  
          
        return data  
      
    def calculate\_quality\_score(self, data, language):  
        """Spočítá quality score"""  
        score \= 0  
          
        if data.get('emails'): score \+= 20  
        if data.get('phones'): score \+= 20  
        if data.get('company\_name'): score \+= 15  
        if data.get('ico'): score \+= 15  
        if data.get('social\_media'): score \+= 10  
          
        *\# Bonus za structured data*  
        if data.get('structured'): score \+= 10  
          
        return min(score, 100)  
      
    def save\_parsed\_data(self, scrape\_result\_id, unit\_listing\_id, data, language):  
        """Uloží parsed data"""  
        quality\_score \= self.calculate\_quality\_score(data, language)  
          
        with get\_cursor(self.conn, dict\_cursor\=False) as cur:  
            cur.execute("""  
                INSERT INTO parsed\_data   
                (scrape\_result\_id, unit\_listing\_id, content\_language, data, quality\_score)  
                VALUES (%s, %s, %s, %s, %s)  
                RETURNING id  
            """, (  
                scrape\_result\_id, unit\_listing\_id, language,   
                json.dumps(data), quality\_score  
            ))  
              
            parsed\_id \= cur.fetchone()\[0\]  
              
            *\# Mark scrape\_result as processed*  
            cur.execute("""  
                UPDATE scrape\_results   
                SET processing\_status \= 'processed'  
                WHERE id \= %s  
            """, (scrape\_result\_id,))  
              
            self.conn.commit()  
            return parsed\_id  
      
    def process\_one(self):  
        """Zpracuje jeden scrape result"""  
        item \= self.get\_next\_scrape\_result()  
        if not item:  
            return False  
          
        scrape\_id \= item\['id'\]  
        html \= item\['html'\]  
        language \= item\['detected\_language'\]  
        url \= item\['url'\]  
          
        print(f"Parsing: {url} ({language})")  
          
        *\# Parse*  
        data \= self.parse\_html(html, language, url)  
          
        *\# Save*  
        *\# TODO: get unit\_listing\_id from scrape\_queue via scrape\_result*  
        self.save\_parsed\_data(scrape\_id, None, data, language)  
          
        return True  
      
    def run(self, max\_items\=None):  
        """Main loop"""  
        import time  
        processed \= 0  
          
        while True:  
            if max\_items and processed \>= max\_items:  
                break  
              
            if not self.process\_one():  
                print("Nothing to parse, waiting...")  
                time.sleep(30)  
                continue  
              
            processed \+= 1  
          
        self.conn.close()

if \_\_name\_\_ \== '\_\_main\_\_':  
    parser \= Parser()

    parser.run()

**Test:**

python  
*\# tests/test\_parser.py*  
from src.workers.parser import Parser

def test\_parse\_simple\_page():  
    html \= """  
    \<html\>  
    \<head\>\<title\>Test Firma s.r.o.\</title\>\</head\>  
    \<body\>  
        \<p\>Email: info@test.cz\</p\>  
        \<p\>Tel: \+420 123 456 789\</p\>  
        \<p\>IČO: 12345678\</p\>  
    \</body\>  
    \</html\>  
    """  
      
    parser \= Parser()  
    data \= parser.parse\_html(html, 'cs', 'https://test.cz')  
      
    assert 'info@test.cz' in data\['emails'\]  
    assert len(data\['phones'\]) \> 0  
    assert data\['ico'\] \== '12345678'

    assert data\['company\_name'\] \== 'Test Firma s.r.o.'

---

## **Fáze 4: Bloom filters (2 hodiny)**

### **4.1 Bloom filter manager**

python  
*\# src/utils/bloom.py*  
from pybloom\_live import BloomFilter  
import io  
from src.utils.db import get\_db\_connection, get\_cursor

class BloomFilterManager:  
    def \_\_init\_\_(self):  
        self.conn \= get\_db\_connection()  
        self.filters \= {}  
      
    def create\_filter(self, name, capacity\=1000000, error\_rate\=0.001):  
        """Vytvoří nový bloom filter"""  
        bf \= BloomFilter(capacity\=capacity, error\_rate\=error\_rate)  
          
        with get\_cursor(self.conn, dict\_cursor\=False) as cur:  
            cur.execute("""  
                INSERT INTO bloom\_filters   
                (name, filter\_data, item\_count, false\_positive\_rate)  
                VALUES (%s, %s, 0, %s)  
                ON CONFLICT (name) DO NOTHING  
            """, (name, bf.bitarray.tobytes(), error\_rate))  
            self.conn.commit()  
          
        self.filters\[name\] \= bf  
        return bf  
      
    def load\_filter(self, name):  
        """Načte bloom filter z DB"""  
        if name in self.filters:  
            return self.filters\[name\]  
          
        with get\_cursor(self.conn) as cur:  
            cur.execute("""  
                SELECT filter\_data FROM bloom\_filters WHERE name \= %s  
            """, (name,))  
            row \= cur.fetchone()  
              
            if not row:  
                *\# Create if doesn't exist*  
                return self.create\_filter(name)  
              
            *\# Deserialize*  
            bf \= BloomFilter.fromfile(io.BytesIO(row\['filter\_data'\]))  
            self.filters\[name\] \= bf  
            return bf  
      
    def add(self, filter\_name, item, source\='scraped'):  
        """Přidá item do filtru"""  
        bf \= self.load\_filter(filter\_name)  
          
        if item in bf:  
            return False  *\# already exists*  
          
        bf.add(item)  
          
        *\# Save to DB*  
        with get\_cursor(self.conn, dict\_cursor\=False) as cur:  
            *\# Update filter*  
            cur.execute("""  
                UPDATE bloom\_filters   
                SET filter\_data \= %s, 

                    item\_

Continue

6:51 PM  
python  
                   item\_count \= item\_count \+ 1,  
                    last\_updated \= NOW()  
                WHERE name \= %s  
            """, (bf.bitarray.tobytes(), filter\_name))  
              
            \# Save item to items table  
            cur.execute("""  
                INSERT INTO bloom\_filter\_items (filter\_name, item, source)  
                VALUES (%s, %s, %s)  
                ON CONFLICT DO NOTHING  
            """, (filter\_name, item, source))  
              
            self.conn.commit()  
          
        return True  
      
    def check(self, filter\_name, item):  
        """Zkontroluje zda item existuje v filtru"""  
        bf \= self.load\_filter(filter\_name)  
        return item in bf  
      
    def stats(self, filter\_name):  
        """Statistiky filtru"""  
        with get\_cursor(self.conn) as cur:  
            cur.execute("""  
                SELECT item\_count, false\_positive\_rate, last\_updated  
                FROM bloom\_filters WHERE name \= %s  
            """, (filter\_name,))

            return cur.fetchone()

### **4.2 CLI pro správu bloom filtrů**

python  
*\# scripts/bloom\_admin.py*  
import click  
from src.utils.bloom import BloomFilterManager  
from src.utils.db import get\_db\_connection

@click.group()  
def cli():  
    """Bloom filter management"""  
    pass

@cli.command()  
@click.argument('name')  
@click.option('--capacity', default\=1000000, help\='Max items')  
@click.option('--error-rate', default\=0.001, help\='False positive rate')  
def create(name, capacity, error\_rate):  
    """Vytvoř nový bloom filter"""  
    bfm \= BloomFilterManager()  
    bfm.create\_filter(name, capacity, error\_rate)  
    click.echo(f"✓ Filter '{name}' created (capacity: {capacity:,})")

@cli.command()  
@click.argument('name')  
@click.argument('file', type\=click.File('r'))  
def import\_items(name, file):  
    """Import items ze souboru"""  
    bfm \= BloomFilterManager()  
      
    items \= \[line.strip() for line in file if line.strip()\]  
      
    added \= 0  
    for item in items:  
        if bfm.add(name, item, source\='imported'):  
            added \+= 1  
      
    click.echo(f"✓ Added {added}/{len(items)} items to '{name}'")

@cli.command()  
@click.argument('name')  
def stats(name):  
    """Zobraz statistiky"""  
    bfm \= BloomFilterManager()  
    stats \= bfm.stats(name)  
      
    if not stats:  
        click.echo(f"Filter '{name}' not found")  
        return  
      
    click.echo(f"Filter: {name}")  
    click.echo(f"  Items: {stats\['item\_count'\]:,}")  
    click.echo(f"  False positive rate: {stats\['false\_positive\_rate'\]}")  
    click.echo(f"  Last updated: {stats\['last\_updated'\]}")

@cli.command()  
def list\_filters():  
    """Seznam všech filtrů"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    cur.execute("""  
        SELECT name, item\_count, last\_updated   
        FROM bloom\_filters   
        ORDER BY name  
    """)  
      
    for row in cur.fetchall():  
        click.echo(f"{row\[0\]:\<20} {row\[1\]:\>10,} items  (updated: {row\[2\]})")

if \_\_name\_\_ \== '\_\_main\_\_':

    cli()

**Test:**

bash  
*\# Vytvoř základní filtry*  
python scripts/bloom\_admin.py create emails \--capacity 5000000  
python scripts/bloom\_admin.py create phones \--capacity 5000000  
python scripts/bloom\_admin.py create ico \--capacity 500000

*\# Stats*  
python scripts/bloom\_admin.py stats emails

python scripts/bloom\_admin.py list-filters

---

## **Fáze 5: LLM Prompts (2 hodiny)**

### **5.1 Seed prompts**

sql  
*\-- migrations/002\_seed\_prompts.sql*  
INSERT INTO llm\_prompts (use\_case, language, prompt\_template, system\_prompt, model, notes) VALUES

('opening\_hours', 'cs',   
'Převeď následující text otevírací doby do JSON formátu.  
Výstup musí být POUZE validní JSON, bez jakéhokoliv jiného textu.

Formát výstupu:  
{"days": \[{"day": "monday", "open": "09:00", "close": "17:00"}\]}

Pokud je zavřeno, použij: {"day": "monday", "closed": true}

Text k parsování:  
{text}',  
'Jsi precizní parser otevírací doby. Odpovídáš pouze validním JSON.',  
'claude-3-5-haiku-20241022',  
'Fallback když regex selže'),

('opening\_hours', 'de',  
'Konvertiere die folgenden Öffnungszeiten in JSON-Format.  
Ausgabe NUR gültiges JSON.

Format: {"days": \[{"day": "monday", "open": "09:00", "close": "17:00"}\]}

Text: {text}',  
'Du bist ein Parser. Nur JSON.',  
'claude-3-5-haiku-20241022',  
NULL),

('opening\_hours', 'en',  
'Convert opening hours to JSON.  
Output ONLY valid JSON.

Format: {"days": \[{"day": "monday", "open": "09:00", "close": "17:00"}\]}

Text: {text}',  
'You are a parser. JSON only.',  
'llama3.2:3b',

'Local model fallback');

bash

psql \-U postgres \-d web\_scraper \< migrations/002\_seed\_prompts.sql

### **5.2 Prompt manager**

python  
*\# src/llm/prompts.py*  
from src.utils.db import get\_db\_connection, get\_cursor  
from psycopg2.extras import RealDictCursor

class PromptManager:  
    def \_\_init\_\_(self):  
        self.conn \= get\_db\_connection()  
      
    def get\_prompt(self, use\_case, language\='cs'):  
        """Získá prompt z DB"""  
        with get\_cursor(self.conn) as cur:  
            cur.execute("""  
                SELECT prompt\_template, system\_prompt, model, max\_tokens, temperature, id  
                FROM llm\_prompts   
                WHERE use\_case \= %s AND language \= %s AND is\_active \= TRUE  
            """, (use\_case, language))  
              
            result \= cur.fetchone()  
              
            if not result:  
                *\# Fallback na EN*  
                cur.execute("""  
                    SELECT prompt\_template, system\_prompt, model, max\_tokens, temperature, id  
                    FROM llm\_prompts   
                    WHERE use\_case \= %s AND language \= 'en' AND is\_active \= TRUE  
                """, (use\_case,))  
                result \= cur.fetchone()  
              
            if not result:  
                raise ValueError(f"No prompt for {use\_case}/{language}")  
              
            return dict(result)  
      
    def render(self, use\_case, language, \*\*variables):  
        """Získá a vyrendruje prompt"""  
        config \= self.get\_prompt(use\_case, language)  
          
        return {  
            'prompt': config\['prompt\_template'\].format(\*\*variables),  
            'system': config\['system\_prompt'\],  
            'model': config\['model'\],  
            'max\_tokens': config\['max\_tokens'\],  
            'temperature': config\['temperature'\],  
            'prompt\_id': config\['id'\]  
        }  
      
    def log\_execution(self, prompt\_id, success\=True, tokens\=0):  
        """Log usage stats"""  
        with get\_cursor(self.conn, dict\_cursor\=False) as cur:  
            cur.execute("""  
                INSERT INTO prompt\_stats (prompt\_id, executions, successes, avg\_tokens)  
                VALUES (%s, 1, %s, %s)  
                ON CONFLICT (prompt\_id, date) DO UPDATE SET  
                    executions \= prompt\_stats.executions \+ 1,  
                    successes \= prompt\_stats.successes \+ EXCLUDED.successes,  
                    avg\_tokens \= (prompt\_stats.avg\_tokens \* prompt\_stats.executions \+ %s)   
                                 / (prompt\_stats.executions \+ 1\)  
            """, (prompt\_id, 1 if success else 0, tokens, tokens))

            self.conn.commit()

### **5.3 CLI pro správu promptů**

python  
*\# scripts/prompt\_admin.py*  
import click  
from src.llm.prompts import PromptManager  
from src.utils.db import get\_db\_connection

@click.group()  
def cli():  
    """LLM prompt management"""  
    pass

@cli.command()  
@click.argument('use\_case')  
@click.argument('language')  
def show(use\_case, language):  
    """Zobraz prompt"""  
    pm \= PromptManager()  
    config \= pm.get\_prompt(use\_case, language)  
      
    click.echo(f"Use case: {use\_case}/{language}")  
    click.echo(f"Model: {config\['model'\]}")  
    click.echo(f"Max tokens: {config\['max\_tokens'\]}")  
    click.echo("\\nTemplate:")  
    click.echo(config\['prompt\_template'\])

@cli.command()  
@click.argument('use\_case')  
@click.argument('language')  
def edit(use\_case, language):  
    """Edit prompt v $EDITOR"""  
    pm \= PromptManager()  
    conn \= get\_db\_connection()  
      
    *\# Get current*  
    try:  
        config \= pm.get\_prompt(use\_case, language)  
        current \= config\['prompt\_template'\]  
    except:  
        current \= ""  
      
    *\# Edit*  
    new\_text \= click.edit(current)  
    if not new\_text:  
        click.echo("Aborted")  
        return  
      
    *\# Save*  
    cur \= conn.cursor()  
    cur.execute("""  
        INSERT INTO llm\_prompts (use\_case, language, prompt\_template)  
        VALUES (%s, %s, %s)  
        ON CONFLICT (use\_case, language) DO UPDATE   
        SET prompt\_template \= EXCLUDED.prompt\_template  
    """, (use\_case, language, new\_text))  
    conn.commit()  
      
    click.echo("✓ Saved")

@cli.command()  
def stats():  
    """Usage statistics"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    cur.execute("""  
        SELECT p.use\_case, p.language,   
               SUM(s.executions) as total,  
               ROUND(AVG(s.successes::float/NULLIF(s.executions,0)) \* 100, 1\) as success\_rate  
        FROM llm\_prompts p  
        LEFT JOIN prompt\_stats s ON p.id \= s.prompt\_id  
        WHERE s.date \> CURRENT\_DATE \- 7  
        GROUP BY p.use\_case, p.language  
        ORDER BY total DESC NULLS LAST  
    """)  
      
    click.echo(f"{'Use Case':\<20} {'Lang':\<6} {'Calls':\>8} {'Success':\>8}")  
    click.echo("-" \* 50)  
      
    for row in cur.fetchall():  
        calls \= row\[2\] or 0  
        success \= row\[3\] or 0  
        click.echo(f"{row\[0\]:\<20} {row\[1\]:\<6} {calls:\>8} {success:\>7}%")

@cli.command()  
def list\_all():  
    """Seznam všech promptů"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    cur.execute("""  
        SELECT use\_case, language, model, is\_active  
        FROM llm\_prompts  
        ORDER BY use\_case, language  
    """)  
      
    for row in cur.fetchall():  
        active \= "✓" if row\[3\] else "✗"  
        click.echo(f"{active} {row\[0\]}/{row\[1\]} ({row\[2\]})")

if \_\_name\_\_ \== '\_\_main\_\_':

    cli()

---

## **Fáze 6: Multi-page crawling (2-3 hodiny)**

### **6.1 Promising link patterns**

python  
*\# src/utils/multipage.py*  
import re  
from urllib.parse import urljoin  
from bs4 import BeautifulSoup  
from src.utils.urls import same\_domain

MULTIPAGE\_PATTERNS \= {  
    'cs': {  
        'contact': r'/(kontakt|kontakty|spojeni)',  
        'about': r'/(o-nas|o-firme|profil)',  
        'services': r'/(sluzby|nabidka|co-delame)',  
        'locations': r'/(pobocky|kde-nas-najdete|provozovny)'  
    },  
    'sk': {  
        'contact': r'/(kontakt|kontakty)',  
        'about': r'/(o-nas|profil)',  
        'services': r'/(sluzby|ponuka)',  
        'locations': r'/(pobocky|kde-nas-najdete)'  
    },  
    'de': {  
        'contact': r'/(kontakt|kontaktieren)',  
        'about': r'/(uber-uns|unternehmen|profil)',  
        'services': r'/(leistungen|dienstleistungen|angebot)',  
        'locations': r'/(standorte|filialen)'  
    },  
    'en': {  
        'contact': r'/(contact|contact-us|get-in-touch)',  
        'about': r'/(about|about-us|company)',  
        'services': r'/(services|what-we-do|solutions)',  
        'locations': r'/(locations|branches|find-us)'  
    },  
    'nl': {  
        'contact': r'/(contact|contacteer)',  
        'about': r'/(over-ons|bedrijf)',  
        'services': r'/(diensten|aanbod)',  
        'locations': r'/(locaties|vestigingen)'  
    },  
    'fr': {  
        'contact': r'/(contact|contactez)',  
        'about': r'/(a-propos|entreprise)',  
        'services': r'/(services|prestations)',  
        'locations': r'/(emplacements|agences)'  
    }  
}

def find\_promising\_links(html, base\_url, language):  
    """  
    Najde nadějné odkazy na stejné doméně  
    Returns: list of (url, category)  
    """  
    soup \= BeautifulSoup(html, 'lxml')  
    patterns \= MULTIPAGE\_PATTERNS.get(language, MULTIPAGE\_PATTERNS\['en'\])  
      
    promising \= \[\]  
    seen \= set()  
      
    for link in soup.find\_all('a', href\=True):  
        url \= urljoin(base\_url, link\['href'\])  
          
        *\# Musí být stejná doména*  
        if not same\_domain(url, base\_url):  
            continue  
          
        *\# Už přidáno?*  
        if url in seen:  
            continue  
          
        *\# Match pattern?*  
        for category, pattern in patterns.items():  
            if re.search(pattern, url, re.IGNORECASE):  
                promising.append((url, category))  
                seen.add(url)  
                break  
    

    return promising

### **6.2 Update scraper pro multi-page**

python  
*\# src/workers/scraper.py \- rozšíření*  
from src.utils.multipage import find\_promising\_links

class Scraper:  
    *\# ... existing code ...*  
      
    def add\_subpages\_to\_queue(self, parent\_id, parent\_url, html, language, unit\_listing\_id, depth):  
        """Přidá sub-stránky do fronty"""  
        max\_depth \= self.get\_max\_depth(parent\_url)  
          
        if depth \>= max\_depth:  
            return  
          
        promising \= find\_promising\_links(html, parent\_url, language)  
          
        with get\_cursor(self.conn, dict\_cursor\=False) as cur:  
            for url, category in promising:  
                cur.execute("""  
                    INSERT INTO scrape\_queue   
                    (url, unit\_listing\_id, parent\_scrape\_id, depth, priority)  
                    VALUES (%s, %s, %s, %s, 5\)  
                    ON CONFLICT (url, unit\_listing\_id) DO NOTHING  
                """, (url, unit\_listing\_id, parent\_id, depth \+ 1))  
              
            self.conn.commit()  
          
        print(f"  → Added {len(promising)} sub-pages to queue")  
      
    def get\_max\_depth(self, url):  
        """Získá max\_depth pro doménu"""  
        from src.utils.urls import extract\_domain  
        domain \= extract\_domain(url)  
          
        with get\_cursor(self.conn) as cur:  
            cur.execute("""  
                SELECT max\_depth FROM domain\_multipage\_rules   
                WHERE domain \= %s AND enabled \= TRUE  
            """, (domain,))  
              
            row \= cur.fetchone()  
            return row\['max\_depth'\] if row else 2  *\# default*  
      
    def process\_one(self):  
        """Zpracuje jedno URL \- s multi-page support"""  
        item \= self.get\_next\_url()  
        if not item:  
            return False  
          
        queue\_id \= item\['id'\]  
        url \= item\['url'\]  
        retry\_count \= item\['retry\_count'\]  
        unit\_listing\_id \= item.get('unit\_listing\_id')  
        depth \= item.get('depth', 0)  
          
        print(f"Scraping \[{depth}\]: {url}")  
          
        self.update\_queue\_status(queue\_id, 'processing')  
          
        result \= self.scrape\_url(url)  
          
        *\# Save result*  
        scrape\_result\_id \= self.save\_result(queue\_id, url, result)  
          
        *\# If successful, add sub-pages*  
        if result\['status\_code'\] \== 200 and result\['html'\]:  
            self.update\_queue\_status(queue\_id, 'completed')  
              
            *\# Detect language*  
            from src.utils.language import detect\_language  
            lang, \_ \= detect\_language(result\['html'\])  
              
            *\# Add sub-pages*  
            if unit\_listing\_id:  
                self.add\_subpages\_to\_queue(  
                    scrape\_result\_id, url, result\['html'\],   
                    lang, unit\_listing\_id, depth  
                )  
          
        elif retry\_count \>= MAX\_RETRIES:  
            self.update\_queue\_status(queue\_id, 'failed')  
        else:  
            import datetime  
            next\_try \= datetime.datetime.now() \+ datetime.timedelta(hours\=1)  
            self.update\_queue\_status(queue\_id, 'pending', retry\_count \+ 1, next\_try)  
        

        return True

**Test:**

python  
*\# tests/test\_multipage.py*  
from src.utils.multipage import find\_promising\_links

def test\_find\_promising\_links\_cs():  
    html \= """  
    \<html\>  
    \<body\>  
        \<a href="/kontakt"\>Kontakt\</a\>  
        \<a href="/o-nas"\>O nás\</a\>  
        \<a href="https://facebook.com"\>Facebook\</a\>  
    \</body\>  
    \</html\>  
    """  
      
    base\_url \= "https://test.cz"  
    links \= find\_promising\_links(html, base\_url, 'cs')  
      
    assert len(links) \== 2

    assert any('kontakt' in url for url, \_ in links)

---

## **Fáze 7: Change detection (2 hodiny)**

### **7.1 Change detector**

python  
*\# src/workers/change\_detector.py*  
import json  
from src.utils.db import get\_db\_connection, get\_cursor

class ChangeDetector:  
    def \_\_init\_\_(self):  
        self.conn \= get\_db\_connection()  
      
    def get\_latest\_data(self, unit\_listing\_id):  
        """Získá 2 nejnovější parsovaná data pro listing"""  
        with get\_cursor(self.conn) as cur:  
            cur.execute("""  
                SELECT id, data, extracted\_at  
                FROM parsed\_data  
                WHERE unit\_listing\_id \= %s  
                ORDER BY extracted\_at DESC  
                LIMIT 2  
            """, (unit\_listing\_id,))  
              
            return cur.fetchall()  
      
    def detect\_changes(self, old\_data, new\_data):  
        """  
        Porovná 2 JSON objekty a vrátí změny  
        Returns: list of (field\_name, old\_value, new\_value)  
        """  
        changes \= \[\]  
          
        *\# Fields to track*  
        tracked\_fields \= \[  
            'company\_name', 'emails', 'phones', 'ico',   
            'address', 'opening\_hours', 'social\_media'  
        \]  
          
        for field in tracked\_fields:  
            old\_val \= old\_data.get(field)  
            new\_val \= new\_data.get(field)  
              
            *\# Normalize lists for comparison*  
            if isinstance(old\_val, list):  
                old\_val \= sorted(old\_val)  
            if isinstance(new\_val, list):  
                new\_val \= sorted(new\_val)  
              
            if old\_val \!= new\_val:  
                changes.append((  
                    field,  
                    json.dumps(old\_val) if old\_val else None,  
                    json.dumps(new\_val) if new\_val else None  
                ))  
          
        return changes  
      
    def save\_changes(self, unit\_listing\_id, changes):  
        """Uloží změny do change\_history"""  
        if not changes:  
            return  
          
        with get\_cursor(self.conn, dict\_cursor\=False) as cur:  
            for field, old\_val, new\_val in changes:  
                cur.execute("""  
                    INSERT INTO change\_history   
                    (unit\_listing\_id, field\_name, old\_value, new\_value)  
                    VALUES (%s, %s, %s, %s)  
                """, (unit\_listing\_id, field, old\_val, new\_val))  
              
            self.conn.commit()  
      
    def process\_one(self):  
        """Zpracuje jeden listing"""  
        *\# Get listings s více než 1 parsovaným výsledkem*  
        with get\_cursor(self.conn) as cur:  
            cur.execute("""  
                SELECT unit\_listing\_id, COUNT(\*) as cnt  
                FROM parsed\_data  
                WHERE unit\_listing\_id IS NOT NULL  
                GROUP BY unit\_listing\_id  
                HAVING COUNT(\*) \>= 2  
                ORDER BY MAX(extracted\_at) DESC  
                LIMIT 1  
            """)  
              
            row \= cur.fetchone()  
            if not row:  
                return False  
              
            unit\_listing\_id \= row\['unit\_listing\_id'\]  
          
        *\# Get latest 2 data*  
        results \= self.get\_latest\_data(unit\_listing\_id)  
        if len(results) \< 2:  
            return False  
          
        new\_data \= results\[0\]\['data'\]  
        old\_data \= results\[1\]\['data'\]  
          
        print(f"Checking changes for listing {unit\_listing\_id}")  
          
        *\# Detect changes*  
        changes \= self.detect\_changes(old\_data, new\_data)  
          
        if changes:  
            print(f"  → Found {len(changes)} changes")  
            self.save\_changes(unit\_listing\_id, changes)  
          
        return True  
      
    def run(self):  
        """Main loop"""  
        import time  
          
        while True:  
            if not self.process\_one():  
                print("No changes to detect, waiting...")  
                time.sleep(300)  *\# 5 minut*  
                continue

if \_\_name\_\_ \== '\_\_main\_\_':  
    detector \= ChangeDetector()

    detector.run()

**Test:**

python  
*\# tests/test\_change\_detector.py*  
from src.workers.change\_detector import ChangeDetector

def test\_detect\_changes():  
    old \= {  
        'emails': \['old@test.cz'\],  
        'phones': \['+420123456789'\],  
        'company\_name': 'Test s.r.o.'  
    }  
      
    new \= {  
        'emails': \['new@test.cz', 'old@test.cz'\],  
        'phones': \['+420123456789'\],  
        'company\_name': 'Test s.r.o.'  
    }  
      
    detector \= ChangeDetector()  
    changes \= detector.detect\_changes(old, new)  
      
    assert len(changes) \== 1

    assert changes\[0\]\[0\] \== 'emails'

---

## **Fáze 8: Re-queue worker (1 hodina)**

### **8.1 Re-queue worker**

python  
*\# src/workers/requeue.py*  
from datetime import datetime, timedelta  
from src.utils.db import get\_db\_connection, get\_cursor

class RequeueWorker:  
    def \_\_init\_\_(self):  
        self.conn \= get\_db\_connection()  
      
    def requeue\_old\_listings(self, days\_old\=90):  
        """  
        Najde listings starší než X dní a přidá je zpět do fronty  
        """  
        with get\_cursor(self.conn, dict\_cursor\=False) as cur:  
            *\# Get listings to requeue*  
            cur.execute("""  
                SELECT DISTINCT pd.unit\_listing\_id, sr.url  
                FROM parsed\_data pd  
                JOIN scrape\_results sr ON sr.id \= pd.scrape\_result\_id  
                WHERE pd.quality\_score \> 50  
                  AND pd.extracted\_at \< NOW() \- INTERVAL '%s days'  
                  AND sr.url NOT IN (  
                      SELECT url FROM domain\_blacklist  
                      WHERE auto\_added \= TRUE  
                  )  
                  AND NOT EXISTS (  
                      SELECT 1 FROM scrape\_queue sq  
                      WHERE sq.url \= sr.url   
                        AND sq.status IN ('pending', 'processing')  
                  )  
            """, (days\_old,))  
              
            results \= cur.fetchall()  
              
            *\# Re-add to queue*  
            count \= 0  
            for unit\_listing\_id, url in results:  
                next\_scrape \= datetime.now() \+ timedelta(days\=days\_old)  
                  
                cur.execute("""  
                    INSERT INTO scrape\_queue   
                    (url, unit\_listing\_id, next\_scrape\_at, priority)  
                    VALUES (%s, %s, %s, 1\)  
                    ON CONFLICT (url, unit\_listing\_id) DO UPDATE  
                    SET next\_scrape\_at \= EXCLUDED.next\_scrape\_at,  
                        status \= 'pending'  
                """, (url, unit\_listing\_id, next\_scrape))  
                  
                count \+= 1  
              
            self.conn.commit()  
            print(f"Re-queued {count} listings")  
            return count  
      
    def run\_daily(self):  
        """Denní běh"""  
        print(f"Running requeue worker at {datetime.now()}")  
        self.requeue\_old\_listings(days\_old\=90)

if \_\_name\_\_ \== '\_\_main\_\_':  
    import time  
      
    worker \= RequeueWorker()  
      
    while True:  
        worker.run\_daily()  
        *\# Sleep 24 hodin*

        time.sleep(86400)

---

## **Fáze 9: Testing & Integration (3-4 hodiny)**

### **9.1 Integration test**

python  
*\# tests/test\_integration.py*  
import pytest  
from src.workers.scraper import Scraper  
from src.workers.parser import Parser  
from src.workers.change\_detector import ChangeDetector  
from src.utils.db import get\_db\_connection

@pytest.fixture  
def clean\_db():  
    """Clean test data before each test"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    cur.execute("TRUNCATE scrape\_queue, scrape\_results, parsed\_data, change\_history CASCADE")  
    conn.commit()  
      
    yield conn  
      
    conn.close()

def test\_full\_pipeline(clean\_db):  
    """Test celého flow: scrape → parse → changes"""  
    conn \= clean\_db  
    cur \= conn.cursor()  
      
    *\# 1\. Add URL to queue*  
    cur.execute("""  
        INSERT INTO scrape\_queue (url, unit\_listing\_id)  
        VALUES ('https://example.com', 1\)  
    """)  
    conn.commit()  
      
    *\# 2\. Scrape*  
    scraper \= Scraper()  
    success \= scraper.process\_one()  
    assert success \== True  
      
    *\# Check scrape\_results*  
    cur.execute("SELECT COUNT(\*) FROM scrape\_results")  
    assert cur.fetchone()\[0\] \== 1  
      
    *\# 3\. Parse*  
    parser \= Parser()  
    success \= parser.process\_one()  
    assert success \== True  
      
    *\# Check parsed\_data*  
    cur.execute("SELECT COUNT(\*) FROM parsed\_data")  
    assert cur.fetchone()\[0\] \== 1  
      
    *\# 4\. Scrape again (simulate re-scrape after 3 months)*  
    cur.execute("""  
        INSERT INTO scrape\_queue (url, unit\_listing\_id)  
        VALUES ('https://example.com', 1\)  
        ON CONFLICT DO NOTHING  
    """)  
    conn.commit()  
      
    scraper.process\_one()  
    parser.process\_one()  
      
    *\# 5\. Detect changes*  
    detector \= ChangeDetector()

    *\# (changes depend on whether example.com actually changed)*

### **9.2 Unit tests checklist**

bash  
*\# Spusť všechny testy*  
pytest tests/ \-v

*\# S coverage*

pytest tests/ \--cov\=src \--cov-report\=html

---

## **Fáze 10: Deployment & Monitoring (2 hodiny)**

### **10.1 Systemd services (Linux)**

ini  
*\# /etc/systemd/system/scraper-worker.service*  
\[Unit\]  
Description\=Web Scraper Worker  
After\=network.target postgresql.service

\[Service\]  
Type\=simple  
User\=scraper  
WorkingDirectory\=/opt/web-scraper  
ExecStart\=/opt/web-scraper/.venv/bin/python src/workers/scraper.py  
Restart\=always  
RestartSec\=10

\[Install\]

WantedBy\=multi-user.target

ini  
*\# /etc/systemd/system/parser-worker.service*  
\[Unit\]  
Description\=Parser Worker  
After\=network.target postgresql.service

\[Service\]  
Type\=simple  
User\=scraper  
WorkingDirectory\=/opt/web-scraper  
ExecStart\=/opt/web-scraper/.venv/bin/python src/workers/parser.py  
Restart\=always  
RestartSec\=10

\[Install\]

WantedBy\=multi-user.target

bash  
*\# Enable and start*  
sudo systemctl enable scraper-worker parser-worker change-detector requeue-worker

sudo systemctl start scraper-worker parser-worker

### **10.2 Simple monitoring SQL views**

sql  
*\-- migrations/003\_monitoring\_views.sql*  
CREATE VIEW scraping\_health AS  
SELECT   
    status,  
    COUNT(\*) as count,  
    AVG(retry\_count) as avg\_retries  
FROM scrape\_queue  
GROUP BY status;

CREATE VIEW daily\_stats AS  
SELECT   
    DATE(scraped\_at) as date,  
    COUNT(\*) as total\_scrapes,  
    COUNT(\*) FILTER (WHERE status\_code \= 200) as successful,  
    COUNT(DISTINCT detected\_language) as languages  
FROM scrape\_results  
WHERE scraped\_at \> NOW() \- INTERVAL '30 days'  
GROUP BY DATE(scraped\_at)  
ORDER BY date DESC;

CREATE VIEW quality\_distribution AS  
SELECT   
    CASE   
        WHEN quality\_score \>= 80 THEN 'excellent'  
        WHEN quality\_score \>= 60 THEN 'good'  
        WHEN quality\_score \>= 40 THEN 'fair'  
        ELSE 'poor'  
    END as quality,  
    COUNT(\*) as count  
FROM parsed\_data

GROUP BY

Continue

6:53 PM  
sql  
GROUP BY   
    CASE   
        WHEN quality\_score \>= 80 THEN 'excellent'  
        WHEN quality\_score \>= 60 THEN 'good'  
        WHEN quality\_score \>= 40 THEN 'fair'  
        ELSE 'poor'  
    END  
ORDER BY quality DESC;

CREATE VIEW recent\_changes AS  
SELECT   
    unit\_listing\_id,  
    field\_name,  
    COUNT(\*) as change\_count,  
    MAX(detected\_at) as last\_change  
FROM change\_history  
WHERE detected\_at \> NOW() \- INTERVAL '30 days'  
GROUP BY unit\_listing\_id, field\_name  
ORDER BY last\_change DESC  
LIMIT 100;

CREATE VIEW blacklist\_summary AS  
SELECT   
    reason,  
    COUNT(\*) as domain\_count,  
    AVG(fail\_count) as avg\_fails  
FROM domain\_blacklist  
GROUP BY reason

ORDER BY domain\_count DESC;

bash

psql \-U postgres \-d web\_scraper \< migrations/003\_monitoring\_views.sql

### **10.3 Monitoring CLI tool**

python  
*\# scripts/monitor.py*  
import click  
from src.utils.db import get\_db\_connection  
from datetime import datetime

@click.group()  
def cli():  
    """Monitoring and stats"""  
    pass

@cli.command()  
def health():  
    """System health check"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    *\# Queue status*  
    click.echo("=== Queue Status \===")  
    cur.execute("SELECT \* FROM scraping\_health")  
    for row in cur.fetchall():  
        click.echo(f"{row\[0\]:\<12} {row\[1\]:\>6} (avg retries: {row\[2\]:.1f})")  
      
    *\# Recent activity*  
    click.echo("\\n=== Last 24h Activity \===")  
    cur.execute("""  
        SELECT   
            COUNT(\*) as scrapes,  
            COUNT(DISTINCT detected\_language) as languages  
        FROM scrape\_results  
        WHERE scraped\_at \> NOW() \- INTERVAL '24 hours'  
    """)  
    row \= cur.fetchone()  
    click.echo(f"Scrapes: {row\[0\]}")  
    click.echo(f"Languages: {row\[1\]}")  
      
    *\# Parsing backlog*  
    cur.execute("""  
        SELECT COUNT(\*) FROM scrape\_results   
        WHERE processing\_status \= 'new'  
    """)  
    backlog \= cur.fetchone()\[0\]  
    click.echo(f"\\nParsing backlog: {backlog}")

@cli.command()  
@click.option('--days', default\=7, help\='Number of days')  
def stats(days):  
    """Statistics for last N days"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    click.echo(f"=== Stats for last {days} days \===\\n")  
      
    cur.execute(f"""  
        SELECT \* FROM daily\_stats   
        WHERE date \> CURRENT\_DATE \- {days}  
        ORDER BY date DESC  
    """)  
      
    click.echo(f"{'Date':\<12} {'Total':\>8} {'Success':\>8} {'Languages':\>10}")  
    click.echo("-" \* 45)  
    for row in cur.fetchall():  
        click.echo(f"{row\[0\]} {row\[1\]:\>8} {row\[2\]:\>8} {row\[3\]:\>10}")

@cli.command()  
def quality():  
    """Quality score distribution"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    cur.execute("SELECT \* FROM quality\_distribution")  
      
    click.echo("=== Quality Distribution \===")  
    for row in cur.fetchall():  
        click.echo(f"{row\[0\]:\<12} {row\[1\]:\>6}")

@cli.command()  
def changes():  
    """Recent changes summary"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    cur.execute("SELECT \* FROM recent\_changes LIMIT 20")  
      
    click.echo("=== Recent Changes (Top 20\) \===")  
    click.echo(f"{'Listing ID':\<12} {'Field':\<20} {'Count':\>6} {'Last Change'}")  
    click.echo("-" \* 60)  
      
    for row in cur.fetchall():  
        click.echo(f"{row\[0\]:\<12} {row\[1\]:\<20} {row\[2\]:\>6} {row\[3\]}")

@cli.command()  
def blacklist():  
    """Blacklist summary"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    cur.execute("SELECT \* FROM blacklist\_summary")  
      
    click.echo("=== Blacklist Summary \===")  
    click.echo(f"{'Reason':\<20} {'Domains':\>8} {'Avg Fails':\>10}")  
    click.echo("-" \* 45)  
      
    for row in cur.fetchall():  
        click.echo(f"{row\[0\]:\<20} {row\[1\]:\>8} {row\[2\]:\>10.1f}")

@cli.command()  
@click.argument('unit\_listing\_id', type\=int)  
def listing(unit\_listing\_id):  
    """Detail konkrétního listingu"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    *\# Latest data*  
    cur.execute("""  
        SELECT data, quality\_score, extracted\_at, content\_language  
        FROM parsed\_data  
        WHERE unit\_listing\_id \= %s  
        ORDER BY extracted\_at DESC  
        LIMIT 1  
    """, (unit\_listing\_id,))  
      
    row \= cur.fetchone()  
    if not row:  
        click.echo(f"No data for listing {unit\_listing\_id}")  
        return  
      
    import json  
    data, quality, extracted, lang \= row  
      
    click.echo(f"=== Listing {unit\_listing\_id} \===")  
    click.echo(f"Language: {lang}")  
    click.echo(f"Quality: {quality}/100")  
    click.echo(f"Last scraped: {extracted}")  
    click.echo("\\nData:")  
    click.echo(json.dumps(data, indent\=2, ensure\_ascii\=False))  
      
    *\# Recent changes*  
    click.echo("\\n=== Recent Changes \===")  
    cur.execute("""  
        SELECT field\_name, old\_value, new\_value, detected\_at  
        FROM change\_history  
        WHERE unit\_listing\_id \= %s  
        ORDER BY detected\_at DESC  
        LIMIT 10  
    """, (unit\_listing\_id,))  
      
    for row in cur.fetchall():  
        click.echo(f"\\n{row\[3\]} \- {row\[0\]}:")  
        click.echo(f"  Old: {row\[1\]}")  
        click.echo(f"  New: {row\[2\]}")

if \_\_name\_\_ \== '\_\_main\_\_':

    cli()

### **10.4 Logging setup**

python  
*\# src/utils/logging\_config.py*  
import logging  
import sys  
from datetime import datetime

def setup\_logging(name, log\_file\=None):  
    """Setup logging pro workers"""  
    logger \= logging.getLogger(name)  
    logger.setLevel(logging.INFO)  
      
    *\# Format*  
    formatter \= logging.Formatter(  
        '%(asctime)s \- %(name)s \- %(levelname)s \- %(message)s'  
    )  
      
    *\# Console handler*  
    console \= logging.StreamHandler(sys.stdout)  
    console.setFormatter(formatter)  
    logger.addHandler(console)  
      
    *\# File handler (optional)*  
    if log\_file:  
        file\_handler \= logging.FileHandler(log\_file)  
        file\_handler.setFormatter(formatter)  
        logger.addHandler(file\_handler)  
    

    return logger

python  
*\# Update workers to use logging*  
*\# src/workers/scraper.py*  
from src.utils.logging\_config import setup\_logging

class Scraper:  
    def \_\_init\_\_(self):  
        self.conn \= get\_db\_connection()  
        self.last\_domain\_access \= {}  
        self.logger \= setup\_logging('scraper', 'logs/scraper.log')  
      
    def process\_one(self):  
        *\# ...*  
        self.logger.info(f"Scraping: {url}")

        *\# ...*

---

## **Fáze 11: Admin utilities (1-2 hodiny)**

### **11.1 Queue management CLI**

python  
*\# scripts/queue\_admin.py*  
import click  
from src.utils.db import get\_db\_connection  
from src.utils.urls import normalize\_url

@click.group()  
def cli():  
    """Queue management"""  
    pass

@cli.command()  
@click.argument('url')  
@click.option('--unit-id', type\=int, help\='Unit listing ID')  
@click.option('--priority', default\=0, help\='Priority (higher \= sooner)')  
def add(url, unit\_id, priority):  
    """Přidej URL do fronty"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    normalized \= normalize\_url(url)  
      
    cur.execute("""  
        INSERT INTO scrape\_queue (url, unit\_listing\_id, priority)  
        VALUES (%s, %s, %s)  
        ON CONFLICT (url, unit\_listing\_id) DO UPDATE  
        SET priority \= EXCLUDED.priority,  
            status \= 'pending',  
            next\_scrape\_at \= NOW()  
        RETURNING id  
    """, (normalized, unit\_id, priority))  
      
    queue\_id \= cur.fetchone()\[0\]  
    conn.commit()  
      
    click.echo(f"✓ Added to queue (ID: {queue\_id})")

@cli.command()  
@click.argument('file', type\=click.File('r'))  
@click.option('--unit-id', type\=int, help\='Default unit listing ID')  
def bulk\_add(file, unit\_id):  
    """Bulk import URLs ze souboru (jeden per řádek)"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    urls \= \[line.strip() for line in file if line.strip()\]  
      
    added \= 0  
    for url in urls:  
        try:  
            normalized \= normalize\_url(url)  
            cur.execute("""  
                INSERT INTO scrape\_queue (url, unit\_listing\_id)  
                VALUES (%s, %s)  
                ON CONFLICT DO NOTHING  
            """, (normalized, unit\_id))  
            added \+= 1  
        except Exception as e:  
            click.echo(f"Error adding {url}: {e}")  
      
    conn.commit()  
    click.echo(f"✓ Added {added}/{len(urls)} URLs")

@cli.command()  
@click.argument('url')  
def remove(url):  
    """Odstraň URL z fronty"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    normalized \= normalize\_url(url)  
      
    cur.execute("""  
        DELETE FROM scrape\_queue   
        WHERE url \= %s  
        RETURNING id  
    """, (normalized,))  
      
    if cur.fetchone():  
        conn.commit()  
        click.echo("✓ Removed")  
    else:  
        click.echo("URL not found in queue")

@cli.command()  
@click.option('--status', help\='Filter by status')  
def clear(status):  
    """Vyčisti frontu"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    if status:  
        cur.execute("DELETE FROM scrape\_queue WHERE status \= %s", (status,))  
    else:  
        if not click.confirm("Clear entire queue?"):  
            return  
        cur.execute("DELETE FROM scrape\_queue")  
      
    count \= cur.rowcount  
    conn.commit()  
      
    click.echo(f"✓ Removed {count} items")

@cli.command()  
def reset\_failed():  
    """Reset failed items zpět na pending"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    cur.execute("""  
        UPDATE scrape\_queue   
        SET status \= 'pending',   
            retry\_count \= 0,  
            next\_scrape\_at \= NOW()  
        WHERE status \= 'failed'  
    """)  
      
    count \= cur.rowcount  
    conn.commit()  
      
    click.echo(f"✓ Reset {count} failed items")

@cli.command()  
@click.argument('domain')  
@click.option('--reason', default\='manual', help\='Reason for blacklist')  
def blacklist(domain, reason):  
    """Přidej doménu do blacklistu"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    cur.execute("""  
        INSERT INTO domain\_blacklist   
        (domain, reason, auto\_added, notes)  
        VALUES (%s, %s, FALSE, 'Added manually')  
        ON CONFLICT (domain) DO UPDATE  
        SET reason \= EXCLUDED.reason  
    """, (domain, reason))  
      
    conn.commit()  
    click.echo(f"✓ Blacklisted {domain}")

@cli.command()  
@click.argument('domain')  
def whitelist(domain):  
    """Odstraň doménu z blacklistu"""  
    conn \= get\_db\_connection()  
    cur \= conn.cursor()  
      
    cur.execute("DELETE FROM domain\_blacklist WHERE domain \= %s", (domain,))  
      
    if cur.rowcount:  
        conn.commit()  
        click.echo(f"✓ Removed {domain} from blacklist")  
    else:  
        click.echo(f"Domain {domain} not in blacklist")

if \_\_name\_\_ \== '\_\_main\_\_':

    cli()

---

## **Testing Plán**

### **Test checklist**

**Unit testy (per modul):**

bash  
*\# 1\. Utils*  
pytest tests/test\_db.py \-v  
pytest tests/test\_language.py \-v  
pytest tests/test\_urls.py \-v  
pytest tests/test\_patterns.py \-v

*\# 2\. Workers*  
pytest tests/test\_scraper.py \-v  
pytest tests/test\_parser.py \-v  
pytest tests/test\_change\_detector.py \-v

*\# 3\. Bloom & LLM*  
pytest tests/test\_bloom.py \-v  
pytest tests/test\_prompts.py \-v

*\# 4\. Integration*  
pytest tests/test\_integration.py \-v

*\# Celkem*

pytest tests/ \--cov\=src \--cov-report\=html

**Manuální testy:**

bash  
*\# 1\. Database connection*  
python \-c "from src.utils.db import get\_db\_connection; print('DB OK' if get\_db\_connection() else 'FAIL')"

*\# 2\. Add test URL*  
python scripts/queue\_admin.py add "https://example.com" \--unit-id 1

*\# 3\. Run scraper (1 item)*  
python \-c "from src.workers.scraper import Scraper; s \= Scraper(); s.process\_one()"

*\# 4\. Check results*  
psql \-d web\_scraper \-c "SELECT url, status\_code, detected\_language FROM scrape\_results ORDER BY id DESC LIMIT 1;"

*\# 5\. Run parser (1 item)*  
python \-c "from src.workers.parser import Parser; p \= Parser(); p.process\_one()"

*\# 6\. Check parsed data*  
psql \-d web\_scraper \-c "SELECT data-\>\>'company\_name', quality\_score FROM parsed\_data ORDER BY id DESC LIMIT 1;"

*\# 7\. Monitoring*  
python scripts/monitor.py health  
python scripts/monitor.py stats \--days 1

*\# 8\. Bloom filters*  
python scripts/bloom\_admin.py create test\_emails  
python scripts/bloom\_admin.py stats test\_emails

*\# 9\. Prompts*  
python scripts/prompt\_admin.py list-all

python scripts/prompt\_admin.py show opening\_hours cs

**Performance test:**

python  
*\# tests/test\_performance.py*  
import time  
from src.workers.scraper import Scraper  
from src.workers.parser import Parser

def test\_scrape\_performance():  
    """Test scraping rychlosti"""  
    scraper \= Scraper()  
      
    *\# Add 10 test URLs*  
    conn \= scraper.conn  
    cur \= conn.cursor()  
      
    test\_urls \= \[  
        'https://example.com',  
        'https://example.org',  
        *\# ... add more*  
    \]  
      
    for url in test\_urls:  
        cur.execute("""  
            INSERT INTO scrape\_queue (url, unit\_listing\_id)  
            VALUES (%s, %s)  
            ON CONFLICT DO NOTHING  
        """, (url, 1))  
    conn.commit()  
      
    *\# Time it*  
    start \= time.time()  
    scraper.run(max\_items\=10)  
    elapsed \= time.time() \- start  
      
    print(f"Scraped 10 URLs in {elapsed:.2f}s ({elapsed/10:.2f}s per URL)")  
      
    assert elapsed \< 60  *\# Should be \< 60s for 10 URLs*

def test\_parser\_performance():  
    """Test parsing rychlosti"""  
    parser \= Parser()  
      
    start \= time.time()  
    count \= 0  
    while count \< 10 and parser.process\_one():  
        count \+= 1  
    elapsed \= time.time() \- start  
      
    print(f"Parsed {count} results in {elapsed:.2f}s ({elapsed/count:.2f}s per result)")  
    

    assert elapsed \< 30  *\# Should be fast*

---

## **Production Deployment Checklist**

### **Pre-deployment**

* Všechny testy projdou (`pytest tests/ -v`)  
* Coverage \> 70% (`pytest --cov=src`)  
* Database migrations aplikovány  
* Config soubor (.env) připraven  
* Seed data (prompts, config) vložena  
* Bloom filtry inicializovány  
* Logs adresář existuje

### **Deployment kroky**

bash  
*\# 1\. Clone repo na server*  
git clone \<repo\> /opt/web-scraper  
cd /opt/web-scraper

*\# 2\. Setup virtual environment*  
uv venv  
source .venv/bin/activate  
uv sync

*\# 3\. Setup database*  
createdb web\_scraper  
psql \-d web\_scraper \< migrations/001\_initial\_schema.sql  
psql \-d web\_scraper \< migrations/002\_seed\_prompts.sql  
psql \-d web\_scraper \< migrations/003\_monitoring\_views.sql

*\# 4\. Create .env*  
cp .env.example .env  
nano .env  *\# edit values*

*\# 5\. Initialize bloom filters*  
python scripts/bloom\_admin.py create emails \--capacity 5000000  
python scripts/bloom\_admin.py create phones \--capacity 5000000  
python scripts/bloom\_admin.py create ico \--capacity 500000

*\# 6\. Test run (manual)*  
python src/workers/scraper.py  *\# Ctrl+C after 1-2 items*  
python src/workers/parser.py   *\# Ctrl+C after 1-2 items*

*\# 7\. Setup systemd services*  
sudo cp deploy/systemd/\*.service /etc/systemd/system/  
sudo systemctl daemon-reload  
sudo systemctl enable scraper-worker parser-worker change-detector requeue-worker  
sudo systemctl start scraper-worker parser-worker

*\# 8\. Check status*  
sudo systemctl status scraper-worker  
sudo journalctl \-u scraper-worker \-f

*\# 9\. Monitor*

python scripts/monitor.py health

### **Post-deployment monitoring**

bash  
*\# Denně*  
python scripts/monitor.py health  
python scripts/monitor.py stats \--days 1

*\# Týdně*  
python scripts/monitor.py quality  
python scripts/monitor.py blacklist

*\# Log check*  
tail \-f logs/scraper.log

tail \-f logs/parser.log

---

## **Troubleshooting Guide**

### **Problém: Queue se neplní**

bash  
*\# Check queue*  
psql \-d web\_scraper \-c "SELECT COUNT(\*), status FROM scrape\_queue GROUP BY status;"

*\# Manuálně přidej test URL*

python scripts/queue\_admin.py add "https://example.com" \--unit-id 1

### **Problém: Scraper nejede**

bash  
*\# Check service*  
sudo systemctl status scraper-worker

*\# Check logs*  
sudo journalctl \-u scraper-worker \-n 50

*\# Manual run pro debugging*

python src/workers/scraper.py

### **Problém: Parsing selhává**

bash  
*\# Check parsing backlog*  
psql \-d web\_scraper \-c "SELECT COUNT(\*) FROM scrape\_results WHERE processing\_status \= 'new';"

*\# Check parser logs*  
tail \-f logs/parser.log

*\# Manual test*

python \-c "from src.workers.parser import Parser; p \= Parser(); p.process\_one()"

### **Problém: Database plná**

bash  
*\# Check sizes*  
psql \-d web\_scraper \-c "  
SELECT   
    schemaname,  
    tablename,  
    pg\_size\_pretty(pg\_total\_relation\_size(schemaname||'.'||tablename)) AS size  
FROM pg\_tables  
WHERE schemaname \= 'public'  
ORDER BY pg\_total\_relation\_size(schemaname||'.'||tablename) DESC;  
"

*\# Clean old data (\>6 months)*  
psql \-d web\_scraper \-c "  
DELETE FROM scrape\_results   
WHERE scraped\_at \< NOW() \- INTERVAL '6 months'  
  AND processing\_status \= 'processed';

"

---

## **Shrnutí \- Quick Start**

bash  
*\# Setup (jednou)*  
git clone \<repo\> && cd web-scraper  
uv venv && source .venv/bin/activate  
uv sync  
createdb web\_scraper  
psql \-d web\_scraper \< migrations/\*.sql  
cp .env.example .env && nano .env

*\# Run workers*  
python src/workers/scraper.py &  
python src/workers/parser.py &  
python src/workers/change\_detector.py &  
python src/workers/requeue.py &

*\# Add URLs*  
python scripts/queue\_admin.py bulk-add urls.txt

*\# Monitor*

python scripts/monitor.py health

**Hotovo\! Máš kompletní implementační plán s testováním. Agenti můžou postupovat fázi po fázi, každá je jasně definovaná s testy.**

Ještě potřebuji manuál pro správce aplikace. Instalace , konfigurace, spuštění, kontrola stavu systému...

6:55 PM

# **Web Scraper \- Administrátorský manuál**

## **Obsah**

1. [Požadavky na systém](https://claude.ai/chat/ea125e04-8d80-467b-b004-900305a54edf#po%C5%BEadavky-na-syst%C3%A9m)  
2. [Instalace](https://claude.ai/chat/ea125e04-8d80-467b-b004-900305a54edf#instalace)  
3. [Konfigurace](https://claude.ai/chat/ea125e04-8d80-467b-b004-900305a54edf#konfigurace)  
4. [První spuštění](https://claude.ai/chat/ea125e04-8d80-467b-b004-900305a54edf#prvn%C3%AD-spu%C5%A1t%C4%9Bn%C3%AD)  
5. [Provoz aplikace](https://claude.ai/chat/ea125e04-8d80-467b-b004-900305a54edf#provoz-aplikace)  
6. [Monitoring a diagnostika](https://claude.ai/chat/ea125e04-8d80-467b-b004-900305a54edf#monitoring-a-diagnostika)  
7. [Údržba](https://claude.ai/chat/ea125e04-8d80-467b-b004-900305a54edf#%C3%BAdr%C5%BEba)  
8. [Řešení problémů](https://claude.ai/chat/ea125e04-8d80-467b-b004-900305a54edf#%C5%99e%C5%A1en%C3%AD-probl%C3%A9m%C5%AF)  
9. [Backup a obnova](https://claude.ai/chat/ea125e04-8d80-467b-b004-900305a54edf#backup-a-obnova)  
10. [Bezpečnost](https://claude.ai/chat/ea125e04-8d80-467b-b004-900305a54edf#bezpe%C4%8Dnost)

---

## **Požadavky na systém**

### **Hardware minimální konfigurace**

* **CPU:** 2 cores  
* **RAM:** 4 GB (doporučeno 8 GB)  
* **Disk:** 50 GB volného místa (SSD doporučeno)  
* **Síť:** Stabilní připojení k internetu

### **Software**

* **OS:** Linux (Ubuntu 22.04 LTS nebo Debian 11+) nebo macOS  
* **Python:** 3.10+  
* **PostgreSQL:** 14+  
* **Git:** pro instalaci z repository

### **Volitelné**

* **Ollama:** pro lokální LLM modely (šetří náklady na API)  
* **Systemd:** pro automatický běh workerů (Linux)

---

## **Instalace**

### **1\. Příprava systému**

bash  
*\# Update systému*  
sudo apt update && sudo apt upgrade \-y

*\# Instalace závislostí*  
sudo apt install \-y python3 python3-pip python3-venv postgresql postgresql-contrib git curl

*\# Instalace UV (moderní Python package manager)*  
curl \-LsSf https://astral.sh/uv/install.sh | sh

source $HOME/.cargo/env  *\# nebo restartuj shell*

### **2\. PostgreSQL setup**

bash  
*\# Zapni PostgreSQL*  
sudo systemctl enable postgresql  
sudo systemctl start postgresql

*\# Vytvoř databázi a uživatele*  
sudo \-u postgres psql \<\<EOF  
CREATE USER scraper\_user WITH PASSWORD 'your\_secure\_password';  
CREATE DATABASE web\_scraper OWNER scraper\_user;  
GRANT ALL PRIVILEGES ON DATABASE web\_scraper TO scraper\_user;  
\\q  
EOF

*\# Test připojení*  
psql \-U scraper\_user \-d web\_scraper \-h localhost

*\# (zadej heslo, pokud funguje, ukonči pomocí \\q)*

### **3\. Stažení aplikace**

bash  
*\# Vytvoř adresář pro aplikaci*  
sudo mkdir \-p /opt/web-scraper  
sudo chown $USER:$USER /opt/web-scraper  
cd /opt/web-scraper

*\# Clone repository*  
git clone https://github.com/your-repo/web-scraper.git .

*\# Nebo rozbal ZIP*  
*\# unzip web-scraper.zip*

*\# cd web-scraper*

### **4\. Python prostředí**

bash  
*\# Vytvoř virtual environment pomocí UV*  
uv venv  
source .venv/bin/activate

*\# Instaluj dependencies*  
uv sync

*\# Nebo pokud nemáš pyproject.toml s UV*  
uv pip install psycopg2-binary playwright beautifulsoup4 lxml langdetect \\  
              spacy click pyyaml python-dotenv phonenumbers pybloom-live

*\# Stáhni spaCy jazykové modely (jen co potřebuješ)*  
uv run python \-m spacy download cs\_core\_news\_lg  *\# čeština*  
uv run python \-m spacy download en\_core\_web\_lg   *\# angličtina*  
uv run python \-m spacy download de\_core\_news\_lg  *\# němčina (volitelně)*

*\# Instaluj Playwright prohlížeče*

uv run playwright install chromium

### **5\. Databázové migrace**

bash  
*\# Aplikuj schema*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \< migrations/001\_initial\_schema.sql

*\# Seed data (prompty, config)*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \< migrations/002\_seed\_prompts.sql

*\# Monitoring views*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \< migrations/003\_monitoring\_views.sql

*\# Ověř že tabulky existují*

psql \-U scraper\_user \-d web\_scraper \-h localhost \-c "\\dt"

---

## **Konfigurace**

### **1\. Hlavní konfigurační soubor (.env)**

bash  
*\# Zkopíruj template*  
cp .env.example .env

*\# Edituj konfigurace*

nano .env

**Obsah .env:**

bash  
*\# \=== Database \===*  
DATABASE\_URL=postgresql://scraper\_user:your\_secure\_password@localhost:5432/web\_scraper

*\# \=== Scraping nastavení \===*  
SCRAPE\_DELAY\_SECONDS=2          *\# Delay mezi requesty na stejnou doménu*  
MAX\_RETRIES=3                    *\# Počet opakování při selhání*  
PLAYWRIGHT\_HEADLESS=true         *\# Headless browser mode*  
USER\_AGENT=Mozilla/5.0 (compatible; YourBot/1.0; \+https://yoursite.com/bot)

*\# \=== API klíče (volitelné) \===*  
*\# Pro LLM \- pokud nepoužíváš Ollama*  
ANTHROPIC\_API\_KEY=sk-ant-...    *\# Claude API*  
OPENAI\_API\_KEY=sk-...            *\# OpenAI GPT API*

*\# \=== Logging \===*  
LOG\_LEVEL=INFO                   *\# DEBUG, INFO, WARNING, ERROR*  
LOG\_DIR=/opt/web-scraper/logs

*\# \=== Workers \===*  
SCRAPER\_WORKERS=1                *\# Počet paralelních scraper workerů*  
PARSER\_WORKERS=1                 *\# Počet paralelních parser workerů*

*\# \=== Re-queue nastavení \===*  
REQUEUE\_INTERVAL\_DAYS=90         *\# Jak často re-scrapovat kvalitní stránky*

*\# \=== Blacklist \===*

BLACKLIST\_THRESHOLD=3            *\# Počet failů před auto-blacklistem*

**Poznámky:**

* `DATABASE_URL`: Změň heslo na bezpečné\!  
* `USER_AGENT`: Doporučuji uvést kontaktní URL/email pro případné dotazy administrátorů webů  
* `API_KEY`: Nech prázdné pokud používáš Ollama

### **2\. Inicializace Bloom filtrů**

bash  
*\# Aktivuj virtual environment*  
source /opt/web-scraper/.venv/bin/activate

*\# Vytvoř základní filtry*  
python scripts/bloom\_admin.py create emails \--capacity 5000000  
python scripts/bloom\_admin.py create phones \--capacity 5000000  
python scripts/bloom\_admin.py create ico \--capacity 500000

*\# Ověř*

python scripts/bloom\_admin.py list-filters

### **3\. Konfigurace multi-page rules (volitelné)**

Pokud chceš povolit crawlování více stránek na specifických doménách:

sql  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
INSERT INTO domain\_multipage\_rules (domain, max\_depth, enabled)  
VALUES   
    ('example.com', 3, true),  
    ('trusteddomain.cz', 2, true);

EOF

### **4\. Vytvoř log adresář**

bash  
mkdir \-p /opt/web-scraper/logs

chmod 755 /opt/web-scraper/logs

---

## **První spuštění**

### **1\. Manuální test**

bash  
cd /opt/web-scraper  
source .venv/bin/activate

*\# Test databázového připojení*  
python \-c "from src.utils.db import get\_db\_connection; conn \= get\_db\_connection(); print('DB OK' if conn else 'FAIL')"

*\# Přidej testovací URL*  
python scripts/queue\_admin.py add "https://example.com" \--unit-id 1 \--priority 10

*\# Spusť scraper (zpracuje 1 URL a skončí)*  
python \-c "from src.workers.scraper import Scraper; s \= Scraper(); s.process\_one()"

*\# Zkontroluj výsledek*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \-c \\  
  "SELECT url, status\_code, detected\_language FROM scrape\_results ORDER BY id DESC LIMIT 1;"

*\# Spusť parser (zpracuje 1 výsledek)*  
python \-c "from src.workers.parser import Parser; p \= Parser(); p.process\_one()"

*\# Zkontroluj parsovaná data*

python scripts/monitor.py listing 1

**Očekávaný výsledek:**

* Scraper stáhne HTML z example.com  
* Status code: 200  
* Parser extrahuje dostupná data  
* Quality score \> 0

### **2\. Bulk import URLs**

bash  
*\# Připrav soubor s URL (jeden per řádek)*  
cat \> /tmp/urls.txt \<\<EOF  
https://example.com  
https://example.org  
https://wikipedia.org  
EOF

*\# Import*  
python scripts/queue\_admin.py bulk-add /tmp/urls.txt \--unit-id 1

*\# Ověř frontu*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \-c \\

  "SELECT COUNT(\*), status FROM scrape\_queue GROUP BY status;"

---

## **Provoz aplikace**

### **Spuštění workerů**

#### **Varianta A: Manuální spuštění (testování)**

bash  
cd /opt/web-scraper  
source .venv/bin/activate

*\# Spusť workers v samostatných terminálech nebo s &*  
python src/workers/scraper.py &  
python src/workers/parser.py &  
python src/workers/change\_detector.py &  
python src/workers/requeue.py &

*\# Nebo všechny najednou s nohup*  
nohup python src/workers/scraper.py \> logs/scraper.log 2\>&1 &  
nohup python src/workers/parser.py \> logs/parser.log 2\>&1 &  
nohup python src/workers/change\_detector.py \> logs/change\_detector.log 2\>&1 &  
nohup python src/workers/requeue.py \> logs/requeue.log 2\>&1 &

*\# Seznam běžících procesů*  
ps aux | grep "python.\*workers"

*\# Zastavení*

pkill \-f "python.\*workers"

#### **Varianta B: Systemd (production, doporučeno)**

**1\. Vytvoř systemd service files:**

bash  
*\# Scraper worker*  
sudo tee /etc/systemd/system/scraper-worker.service \> /dev/null \<\<EOF  
\[Unit\]  
Description=Web Scraper Worker  
After=network.target postgresql.service  
Requires=postgresql.service

\[Service\]  
Type=simple  
User=$(whoami)  
WorkingDirectory=/opt/web-scraper  
Environment="PATH=/opt/web-scraper/.venv/bin"  
ExecStart=/opt/web-scraper/.venv/bin/python src/workers/scraper.py  
Restart=always  
RestartSec=10  
StandardOutput=append:/opt/web-scraper/logs/scraper.log  
StandardError=append:/opt/web-scraper/logs/scraper.log

\[Install\]  
WantedBy=multi-user.target  
EOF

*\# Parser worker*  
sudo tee /etc/systemd/system/parser-worker.service \> /dev/null \<\<EOF  
\[Unit\]  
Description=Parser Worker  
After=network.target postgresql.service  
Requires=postgresql.service

\[Service\]  
Type=simple  
User=$(whoami)  
WorkingDirectory=/opt/web-scraper  
Environment="PATH=/opt/web-scraper/.venv/bin"  
ExecStart=/opt/web-scraper/.venv/bin/python src/workers/parser.py  
Restart=always  
RestartSec=10  
StandardOutput=append:/opt/web-scraper/logs/parser.log  
StandardError=append:/opt/web-scraper/logs/parser.log

\[Install\]  
WantedBy=multi-user.target  
EOF

*\# Change detector*  
sudo tee /etc/systemd/system/change-detector.service \> /dev/null \<\<EOF  
\[Unit\]  
Description=Change Detection Worker  
After=network.target postgresql.service  
Requires=postgresql.service

\[Service\]  
Type=simple  
User=$(whoami)  
WorkingDirectory=/opt/web-scraper  
Environment="PATH=/opt/web-scraper/.venv/bin"  
ExecStart=/opt/web-scraper/.venv/bin/python src/workers/change\_detector.py  
Restart=always  
RestartSec=10  
StandardOutput=append:/opt/web-scraper/logs/change\_detector.log  
StandardError=append:/opt/web-scraper/logs/change\_detector.log

\[Install\]  
WantedBy=multi-user.target  
EOF

*\# Requeue worker*  
sudo tee /etc/systemd/system/requeue-worker.service \> /dev/null \<\<EOF  
\[Unit\]  
Description=Requeue Worker  
After=network.target postgresql.service  
Requires=postgresql.service

\[Service\]  
Type=simple  
User=$(whoami)  
WorkingDirectory=/opt/web-scraper  
Environment="PATH=/opt/web-scraper/.venv/bin"  
ExecStart=/opt/web-scraper/.venv/bin/python src/workers/requeue.py  
Restart=always  
RestartSec=10  
StandardOutput=append:/opt/web-scraper/logs/requeue.log  
StandardError=append:/opt/web-scraper/logs/requeue.log

\[Install\]  
WantedBy=multi-user.target

EOF

**2\. Aktivuj a spusť services:**

bash  
*\# Reload systemd*  
sudo systemctl daemon-reload

*\# Povol automatický start po reboot*  
sudo systemctl enable scraper-worker parser-worker change-detector requeue-worker

*\# Spusť services*  
sudo systemctl start scraper-worker  
sudo systemctl start parser-worker  
sudo systemctl start change-detector  
sudo systemctl start requeue-worker

*\# Zkontroluj status*  
sudo systemctl status scraper-worker  
sudo systemctl status parser-worker  
sudo systemctl status change-detector

sudo systemctl status requeue-worker

**3\. Běžné operace:**

bash  
*\# Restart konkrétního workera*  
sudo systemctl restart scraper-worker

*\# Stop workera*  
sudo systemctl stop scraper-worker

*\# Restart všech*  
sudo systemctl restart scraper-worker parser-worker change-detector requeue-worker

*\# Sledování logů (live)*  
sudo journalctl \-u scraper-worker \-f  
sudo journalctl \-u parser-worker \-f

*\# Poslední chyby*

sudo journalctl \-u scraper-worker \-n 50 \--no-pager

---

## **Monitoring a diagnostika**

### **Základní health check**

bash  
cd /opt/web-scraper  
source .venv/bin/activate

*\# Kompletní health check*  
python scripts/monitor.py health  
\`\`\`

\*\*Výstup:\*\*  
\`\`\`  
\=== Queue Status \===  
pending         245 (avg retries: 0.3)  
processing        3 (avg retries: 0.0)  
completed     1,847 (avg retries: 0.1)  
failed           12 (avg retries: 3.0)

\=== Last 24h Activity \===  
Scrapes: 324  
Languages: 4

Parsing backlog: 15

### **Statistiky**

bash  
*\# Statistiky za posledních 7 dní*  
python scripts/monitor.py stats \--days 7

*\# Quality score distribuce*  
python scripts/monitor.py quality

*\# Recent změny*  
python scripts/monitor.py changes

*\# Blacklist přehled*

python scripts/monitor.py blacklist

### **Kontrola konkrétního listingu**

bash  
*\# Detail listingu včetně změn*

python scripts/monitor.py listing 123

### **Kontrola workerů**

bash  
*\# Systemd status*  
sudo systemctl status scraper-worker parser-worker

*\# CPU a paměť usage*  
ps aux | grep "python.\*workers"

*\# Počet aktivních procesů*

pgrep \-fc "python.\*workers"

### **Log monitoring**

bash  
*\# Live sledování*  
tail \-f logs/scraper.log  
tail \-f logs/parser.log

*\# Poslední chyby (last 100 lines)*  
grep \-i error logs/scraper.log | tail \-100

*\# Dnes zpracované URL*

grep "Scraping:" logs/scraper.log | grep "$(date \+%Y-%m-%d)" | wc \-l

### **Database statistiky**

bash  
*\# Velikost tabulek*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
SELECT   
    tablename,  
    pg\_size\_pretty(pg\_total\_relation\_size('public.'||tablename)) AS size  
FROM pg\_tables  
WHERE schemaname \= 'public'  
ORDER BY pg\_total\_relation\_size('public.'||tablename) DESC;  
EOF

*\# Počet záznamů v klíčových tabulkách*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
SELECT   
    'scrape\_queue' as table, COUNT(\*) as count FROM scrape\_queue  
UNION ALL  
SELECT 'scrape\_results', COUNT(\*) FROM scrape\_results  
UNION ALL  
SELECT 'parsed\_data', COUNT(\*) FROM parsed\_data  
UNION ALL  
SELECT 'change\_history', COUNT(\*) FROM change\_history;  
EOF

*\# Connection pool*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \-c \\

  "SELECT count(\*) FROM pg\_stat\_activity WHERE datname \= 'web\_scraper';"

### **Alert setup (volitelné)**

Pro automatické alertování můžeš nastavit cron job:

bash  
*\# Vytvoř monitoring script*  
cat \> /opt/web-scraper/scripts/alert\_check.sh \<\<'EOF'  
\#\!/bin/bash  
cd /opt/web-scraper  
source .venv/bin/activate

\# Check failed items \> threshold  
FAILED=$(psql \-U scraper\_user \-d web\_scraper \-h localhost \-tAc \\  
  "SELECT COUNT(\*) FROM scrape\_queue WHERE status='failed'")

if \[ "$FAILED" \-gt 100 \]; then  
    echo "ALERT: $FAILED failed items in queue" | \\  
      mail \-s "Web Scraper Alert" admin@yoursite.com  
fi

\# Check parser backlog  
BACKLOG=$(psql \-U scraper\_user \-d web\_scraper \-h localhost \-tAc \\  
  "SELECT COUNT(\*) FROM scrape\_results WHERE processing\_status='new'")

if \[ "$BACKLOG" \-gt 500 \]; then  
    echo "ALERT: Parser backlog is $BACKLOG" | \\  
      mail \-s "Web Scraper Alert" admin@yoursite.com  
fi  
EOF

chmod \+x /opt/web-scraper/scripts/alert\_check.sh

*\# Přidej do crontab (každou hodinu)*  
crontab \-e  
*\# Přidej řádek:*

*\# 0 \* \* \* \* /opt/web-scraper/scripts/alert\_check.sh*

---

## **Údržba**

### **Denní úkoly**

bash  
*\# Health check*  
python scripts/monitor.py health

*\# Kontrola logů na errory*  
grep \-i error logs/\*.log | tail \-20

*\# Kontrola diskového místa*

df \-h /opt/web-scraper

### **Týdenní úkoly**

bash  
*\# Statistiky*  
python scripts/monitor.py stats \--days 7  
python scripts/monitor.py quality

*\# Review blacklistu*  
python scripts/monitor.py blacklist

*\# Kontrola failed items*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \-c \\  
  "SELECT url, retry\_count, error\_message FROM scrape\_queue sq  
   JOIN scrape\_results sr ON sr.queue\_id \= sq.id  
   WHERE sq.status \= 'failed' LIMIT 20;"

*\# Případně reset failed items*

python scripts/queue\_admin.py reset-failed

### **Měsíční úkoly**

bash  
*\# Clean old data (\>6 měsíců)*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
DELETE FROM scrape\_results   
WHERE scraped\_at \< NOW() \- INTERVAL '6 months'  
  AND processing\_status \= 'processed';

\-- Vacuum pro uvolnění místa  
VACUUM ANALYZE scrape\_results;  
VACUUM ANALYZE parsed\_data;  
EOF

*\# Rebuild bloom filters (pokud hodně narostly)*  
python scripts/bloom\_admin.py stats emails  
*\# Pokud item\_count je blízko capacity, zvětši:*  
*\# 1\. Backup items*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \-c \\  
  "COPY (SELECT item FROM bloom\_filter\_items WHERE filter\_name='emails') TO '/tmp/emails\_backup.txt';"

*\# 2\. Delete & recreate*  
python \-c "  
from src.utils.bloom import BloomFilterManager  
bfm \= BloomFilterManager()  
\# Delete old  
bfm.conn.cursor().execute(\\"DELETE FROM bloom\_filters WHERE name='emails'\\")  
bfm.conn.commit()  
\# Create larger  
bfm.create\_filter('emails', capacity=10000000)  
"

*\# 3\. Re-import*  
python scripts/bloom\_admin.py import-items emails /tmp/emails\_backup.txt

*\# Update prompts (pokud bylo třeba)*

python scripts/prompt\_admin.py stats

### **Log rotation**

bash  
*\# Nastavení logrotate*  
sudo tee /etc/logrotate.d/web-scraper \> /dev/null \<\<EOF  
/opt/web-scraper/logs/\*.log {  
    daily  
    missingok  
    rotate 14  
    compress  
    delaycompress  
    notifempty  
    create 0644 $(whoami) $(whoami)  
    sharedscripts  
    postrotate  
        systemctl reload scraper-worker parser-worker change-detector requeue-worker \> /dev/null 2\>&1 || true  
    endscript  
}  
EOF

*\# Test logrotate*

sudo logrotate \-d /etc/logrotate.d/web-scraper

---

## **Řešení problémů**

### **Problém: Workers nejdou spustit**

**Symptomy:** `systemctl start` selže nebo process okamžitě umírá

**Diagnostika:**

bash  
*\# Zkontroluj systemd logs*  
sudo journalctl \-u scraper-worker \-n 50

*\# Zkontroluj permissions*  
ls \-la /opt/web-scraper/src/workers/

*\# Zkontroluj Python*  
/opt/web-scraper/.venv/bin/python \--version

*\# Test manuálního spuštění*  
cd /opt/web-scraper  
source .venv/bin/activate  
python src/workers/scraper.py

*\# Sleduj output*

**Řešení:**

* Pokud `ModuleNotFoundError`: `uv sync` znovu  
* Pokud `Permission denied`: `chmod +x src/workers/*.py`  
* Pokud DB error: zkontroluj `.env` a DB connection

### **Problém: Queue se neplní**

**Symptomy:** scrape\_queue je prázdná, nic se neděje

**Diagnostika:**

bash  
*\# Zkontroluj queue*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \-c \\  
  "SELECT COUNT(\*), status FROM scrape\_queue GROUP BY status;"

*\# Zkontroluj requeue worker*  
sudo systemctl status requeue-worker

tail \-f logs/requeue.log

**Řešení:**

bash  
*\# Manuálně přidej URLs*  
python scripts/queue\_admin.py add "https://example.com" \--unit-id 1

*\# Nebo bulk*

python scripts/queue\_admin.py bulk-add /path/to/urls.txt

### **Problém: Vysoká fail rate**

**Symptomy:** Hodně URL ve stavu `failed`

**Diagnostika:**

bash  
*\# Podívej se na důvody*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
SELECT   
    SUBSTRING(error\_message, 1, 50\) as error,  
    COUNT(\*) as count  
FROM scrape\_results sr  
JOIN scrape\_queue sq ON sq.id \= sr.queue\_id  
WHERE sq.status \= 'failed'  
GROUP BY SUBSTRING(error\_message, 1, 50\)  
ORDER BY count DESC  
LIMIT 10;

EOF

**Řešení:**

* Pokud `timeout`: zvyš timeout v `scraper.py` nebo snižte `SCRAPE_DELAY`  
* Pokud `DNS error`: možná problém s internetem  
* Pokud `blocked`: domény blokují bota → změň `USER_AGENT` nebo přidej proxy  
* Pokud specifické domény: přidej do blacklistu

bash

python scripts/queue\_admin.py blacklist problematic-domain.com \--reason "blocks\_bot"

### **Problém: Parser backlog roste**

**Symptomy:** `scrape_results` s `processing_status='new'` narůstá

**Diagnostika:**

bash  
*\# Kolik čeká*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \-c \\  
  "SELECT COUNT(\*) FROM scrape\_results WHERE processing\_status='new';"

*\# Je parser worker alive?*

sudo systemctl status parser-worker

**Řešení:**

bash  
*\# Restart parser*  
sudo systemctl restart parser-worker

*\# Nebo spusť další instance (paralelně)*  
cd /opt/web-scraper  
source .venv/bin/activate

nohup python src/workers/parser.py \> logs/parser2.log 2\>&1 &

### **Problém: Database plná**

**Symptomy:** Disk plný, queries pomalé

**Diagnostika:**

bash  
*\# Velikost DB*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \-c \\  
  "SELECT pg\_size\_pretty(pg\_database\_size('web\_scraper'));"

*\# Největší tabulky*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
SELECT   
    tablename,  
    pg\_size\_pretty(pg\_total\_relation\_size('public.'||tablename))  
FROM pg\_tables  
WHERE schemaname \= 'public'  
ORDER BY pg\_total\_relation\_size('public.'||tablename) DESC;

EOF

**Řešení:**

bash  
*\# Vyčisti stará data*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
\-- Stará scrape\_results (\>6 měsíců, už zparsované)  
DELETE FROM scrape\_results   
WHERE scraped\_at \< NOW() \- INTERVAL '6 months'  
  AND processing\_status \= 'processed';

\-- Stará změnová historie (\>1 rok)  
DELETE FROM change\_history  
WHERE detected\_at \< NOW() \- INTERVAL '1 year';

\-- Vacuum  
VACUUM FULL ANALYZE;

EOF

### **Problém: LLM API costs vysoké**

**Symptomy:** Účty za API jsou vysoké

**Diagnostika:**

bash  
*\# Kolikrát se volá LLM*

python scripts/prompt\_admin.py stats

**Řešení:**

bash  
*\# 1\. Přepni na lokální Ollama model*

*\# Instalace Ollama*  
curl \-fsSL https://ollama.com/install.sh | sh

*\# Stáhni model*  
ollama pull llama3.2:3b

*\# Update prompts na Ollama*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
UPDATE llm\_prompts   
SET model \= 'llama3.2:3b'  
WHERE use\_case \= 'opening\_hours';  
EOF

*\# 2\. Nebo omez použití LLM jen na vysokoprioritní jazyky*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
UPDATE llm\_prompts   
SET is\_active \= FALSE  
WHERE language NOT IN ('cs', 'sk');

EOF

### **Problém: Memory leak**

**Symptomy:** Workers žerou stále více RAM

**Diagnostika:**

bash  
*\# Sleduj paměť*

watch \-n 5 "ps aux | grep 'python.\*workers' | awk '{print \\$6, \\$11}'"

**Řešení:**

bash  
*\# Restart workerů jednou denně (cron)*  
crontab \-e  
*\# Přidej:*

*\# 0 3 \* \* \* /usr/bin/systemctl restart scraper-worker parser-worker*

---

## **Backup a obnova**

### **Backup databáze**

bash  
*\# Denní automatický backup*  
cat \> /opt/web-scraper/scripts/backup\_db.sh \<\<'EOF'  
\#\!/bin/bash  
BACKUP\_DIR=/opt/web-scraper/backups  
DATE=$(date \+%Y%m%d\_%H%M%S)

mkdir \-p $BACKUP\_DIR

\# Dump databáze  
pg\_dump \-U scraper\_user \-h localhost web\_scraper | \\  
  gzip \> $BACKUP\_DIR/web\_scraper\_$DATE.sql.gz

\# Keep only last 7 days  
find $BACKUP\_DIR \-name "web\_scraper\_\*.sql.gz" \-mtime \+7 \-delete

echo "Backup completed: web\_scraper\_$DATE.sql.gz"  
EOF

chmod \+x /opt/web-scraper/scripts/backup\_db.sh

*\# Test*  
/opt/web-scraper/scripts/backup\_db.sh

*\# Automatizace (crontab každý den ve 2:00)*  
crontab \-e  
*\# Přidej:*

*\# 0 2 \* \* \* /opt/web-scraper/scripts/backup\_db.sh*

### **Restore z backupu**

bash  
*\# Stop workery*  
sudo systemctl stop scraper-worker parser-worker change-detector requeue-worker

*\# Restore*  
gunzip \< /opt/web-scraper/backups/web\_scraper\_20260118\_020000.sql.gz | \\  
  psql \-U scraper\_user \-d web\_scraper \-h localhost

*\# Restart workery*

sudo systemctl start scraper-worker parser-worker change-detector requeue-worker

### **Backup konfigurace**

bash  
*\# Backup config files*  
tar \-czf /opt/web-scraper/backups/config\_$(date \+%Y%m%d).tar.gz \\  
  /opt/web-scraper/.env \\  
  /opt/web-scraper/config/ \\  
  /etc/systemd/system/\*-worker.service

*\# Restore*

tar \-xzf /opt/web-scraper/backups/config\_20260118.tar.gz \-C /

---

## **Bezpečnost**

### **Database security**

bash  
*\# Změň default heslo*  
sudo \-u postgres psql \<\<EOF  
ALTER USER scraper\_user WITH PASSWORD 'new\_strong\_password\_here';  
EOF

*\# Update .env*  
nano /opt/web-scraper/.env  
*\# Změň DATABASE\_URL*

*\# Omezte DB přístup jen na localhost*  
sudo nano /etc/postgresql/\*/main/pg\_hba.conf  
*\# Ujisti se že je:*  
*\# local   web\_scraper     scraper\_user                            md5*  
*\# host    web\_scraper     scraper\_user     127.0.0.1/32           md5*

sudo systemctl restart postgresql

### **Filesystem permissions**

bash  
*\# Omezte přístup k .env*  
chmod 600 /opt/web-scraper/.env

*\# Logs readable jen pro ownera*  
chmod 700 /opt/web-scraper/logs  
chmod 600 /opt/web-scraper/logs/\*.log

*\# Workers executable jen pro ownera*

chmod 700 /opt/web-scraper/src/workers/\*.py

### **API Keys security**

bash  
*\# Nikdy necommituj .env do gitu*  
echo ".env" \>\> /opt/web-scraper/.gitignore

*\# Rotuj API keys pravidelně (3-6 měsíců)*

*\# Anthropic*

Continue

6:58 PM  
bash  
*\# Rotuj API keys pravidelně (3-6 měsíců)*  
*\# Anthropic: https://console.anthropic.com/settings/keys*  
*\# OpenAI: https://platform.openai.com/api-keys*

*\# Po rotaci keys:*  
nano /opt/web-scraper/.env  *\# Update keys*

sudo systemctl restart scraper-worker parser-worker  *\# Restart pro reload*

### **Network security**

bash  
*\# Firewall \- povolit jen nutné porty*  
sudo ufw enable  
sudo ufw allow 22/tcp    *\# SSH*  
sudo ufw allow 5432/tcp  *\# PostgreSQL (jen pokud remote přístup)*

*\# Rate limiting pro bot (respektuj robots.txt)*  
*\# Už implementováno v SCRAPE\_DELAY\_SECONDS*

*\# User-agent transparency*  
*\# V .env nastav USER\_AGENT s kontaktem:*

*\# USER\_AGENT=Mozilla/5.0 (compatible; YourCompanyBot/1.0; \+https://yoursite.com/bot-info; contact@yoursite.com)*

### **Monitoring neoprávněného přístupu**

bash  
*\# PostgreSQL connection monitoring*  
cat \> /opt/web-scraper/scripts/check\_db\_access.sh \<\<'EOF'  
\#\!/bin/bash  
\# Check for suspicious DB connections  
psql \-U scraper\_user \-d web\_scraper \-h localhost \-tAc "  
SELECT client\_addr, count(\*)   
FROM pg\_stat\_activity   
WHERE datname \= 'web\_scraper'   
  AND client\_addr IS NOT NULL   
  AND client\_addr::text \!= '127.0.0.1'  
GROUP BY client\_addr;  
" | while read ip count; do  
    echo "WARNING: External DB connection from $ip ($count connections)"  
done  
EOF

chmod \+x /opt/web-scraper/scripts/check\_db\_access.sh

*\# Run hourly*  
crontab \-e

*\# 0 \* \* \* \* /opt/web-scraper/scripts/check\_db\_access.sh*

### **Update dependencies (security patches)**

bash  
*\# Pravidelně (měsíčně) aktualizuj dependencies*  
cd /opt/web-scraper  
source .venv/bin/activate

*\# Zkontroluj outdated packages*  
uv pip list \--outdated

*\# Update všech (opatrně\!)*  
uv sync \--upgrade

*\# Nebo jen security patches*  
uv pip install \--upgrade psycopg2-binary playwright beautifulsoup4

*\# Test po update*  
pytest tests/ \-v

*\# Pokud OK, restart*

sudo systemctl restart scraper-worker parser-worker change-detector requeue-worker

---

## **Optimalizace výkonu**

### **Database tuning**

bash  
*\# Pro lepší výkon PostgreSQL (upravit podle HW)*

sudo nano /etc/postgresql/\*/main/postgresql.conf

**Doporučené změny pro 8GB RAM server:**

ini  
*\# Memory*  
shared\_buffers \= 2GB                \# 25% of RAM  
effective\_cache\_size \= 6GB          \# 75% of RAM  
work\_mem \= 16MB                     \# Per operation  
maintenance\_work\_mem \= 512MB        \# For VACUUM, CREATE INDEX

*\# Connections*  
max\_connections \= 100

*\# WAL*  
wal\_buffers \= 16MB  
checkpoint\_completion\_target \= 0.9

*\# Query planner*  
random\_page\_cost \= 1.1              \# For SSD (default is 4.0 for HDD)

effective\_io\_concurrency \= 200      \# For SSD

bash  
*\# Restart PostgreSQL*  
sudo systemctl restart postgresql

*\# Verify*

psql \-U scraper\_user \-d web\_scraper \-h localhost \-c "SHOW shared\_buffers;"

### **Indexy (pokud queries pomalé)**

sql  
*\-- Přidej indexy podle usage patterns*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF

*\-- Pokud často hledáš podle domény*  
CREATE INDEX IF NOT EXISTS idx\_scrape\_queue\_domain   
ON scrape\_queue (substring(url from '://(\[^/\]+)'));

*\-- Pokud často filtruješ podle quality score*  
CREATE INDEX IF NOT EXISTS idx\_parsed\_data\_quality\_listing   
ON parsed\_data (unit\_listing\_id, quality\_score);

*\-- Pokud často hledáš změny podle času*  
CREATE INDEX IF NOT EXISTS idx\_change\_history\_date\_unit   
ON change\_history (detected\_at DESC, unit\_listing\_id);

*\-- Analyze po přidání indexů*  
ANALYZE;

EOF

### **Worker scaling**

Pokud máš dostatek CPU/RAM a queue se zpracovává pomalu:

bash  
*\# Více scraper workerů (max 2-3, jinak rate-limiting problémy)*  
sudo cp /etc/systemd/system/scraper-worker.service \\  
        /etc/systemd/system/scraper-worker-2.service

sudo nano /etc/systemd/system/scraper-worker-2.service  
*\# Změň:*  
*\# Description=Web Scraper Worker 2*  
*\# StandardOutput/Error logs \-\> scraper2.log*

sudo systemctl daemon-reload  
sudo systemctl enable scraper-worker-2  
sudo systemctl start scraper-worker-2

*\# Více parser workerů (bezpečnější, může jich být víc)*  
for i in {2..4}; do  
    sudo cp /etc/systemd/system/parser-worker.service \\  
            /etc/systemd/system/parser-worker-$i.service  
      
    sudo sed \-i "s/Description=Parser Worker/Description=Parser Worker $i/" \\  
        /etc/systemd/system/parser-worker-$i.service  
      
    sudo sed \-i "s/parser.log/parser$i.log/" \\  
        /etc/systemd/system/parser-worker-$i.service  
      
    sudo systemctl enable parser-worker-$i  
    sudo systemctl start parser-worker-$i  
done

*\# Check all running*

systemctl list-units "\*-worker\*" \--no-pager

### **Playwright optimization**

Pro rychlejší scraping:

python  
*\# V src/workers/scraper.py můžeš optimalizovat:*

*\# 1\. Reuse browser context (místo nového pro každý URL)*  
*\# 2\. Disable images/CSS pro statické stránky*  
*\# 3\. Use httpx/requests pro non-JS pages*

*\# Příklad v scraper.py:*  
*\# if not requires\_javascript(url):  \# detect static page*  
*\#     import httpx*  
*\#     response \= httpx.get(url, timeout=30, headers={'User-Agent': USER\_AGENT})*  
*\#     result\['html'\] \= response.text*  
*\#     result\['status\_code'\] \= response.status\_code*  
*\# else:*

*\#     \# Use Playwright for JS-heavy pages*

---

## **Přidání nových jazyků**

### **Přidání podpory pro nový jazyk (např. italština)**

bash  
cd /opt/web-scraper  
source .venv/bin/activate

*\# 1\. Stáhni spaCy model*  
uv run python \-m spacy download it\_core\_news\_lg

*\# 2\. Přidej do kódu*  
nano src/utils/language.py  
*\# Přidej 'it' do MODELS dict*

*\# 3\. Přidej regex patterns*  
nano src/utils/patterns.py  
*\# Přidej 'it': {...} do PATTERNS*

*\# 4\. Přidej multipage patterns*  
nano src/utils/multipage.py  
*\# Přidej 'it': {...} do MULTIPAGE\_PATTERNS*

*\# 5\. Přidej LLM prompts*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
INSERT INTO llm\_prompts (use\_case, language, prompt\_template, system\_prompt, model)  
VALUES ('opening\_hours', 'it',   
'Converti i seguenti orari in formato JSON.  
Solo JSON, nessuna spiegazione.

Formato: {"days": \[{"day": "monday", "open": "09:00", "close": "17:00"}\]}

Testo: {text}',  
'Sei un parser. Solo JSON.',  
'claude-3-5-haiku-20241022');  
EOF

*\# 6\. Restart workerů*

sudo systemctl restart scraper-worker parser-worker

---

## **Migrace na nový server**

### **Export ze starého serveru**

bash  
*\# 1\. Backup databáze*  
pg\_dump \-U scraper\_user \-h localhost web\_scraper | gzip \> /tmp/web\_scraper\_export.sql.gz

*\# 2\. Backup konfigurace*  
tar \-czf /tmp/web\_scraper\_config.tar.gz \\  
  /opt/web-scraper/.env \\  
  /opt/web-scraper/config/ \\  
  /etc/systemd/system/\*-worker.service

*\# 3\. Backup bloom filters (pokud velké)*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
COPY (SELECT filter\_name, item FROM bloom\_filter\_items)   
TO '/tmp/bloom\_items.csv' CSV HEADER;  
EOF

*\# 4\. Přenes soubory na nový server*  
scp /tmp/web\_scraper\_export.sql.gz new-server:/tmp/  
scp /tmp/web\_scraper\_config.tar.gz new-server:/tmp/

scp /tmp/bloom\_items.csv new-server:/tmp/

### **Import na novém serveru**

bash  
*\# 1\. Instaluj aplikaci (viz sekce Instalace)*  
*\# ... následuj instalační kroky ...*

*\# 2\. Restore databáze*  
gunzip \< /tmp/web\_scraper\_export.sql.gz | \\  
  psql \-U scraper\_user \-d web\_scraper \-h localhost

*\# 3\. Restore konfigurace*  
tar \-xzf /tmp/web\_scraper\_config.tar.gz \-C /

*\# 4\. Restore bloom filters*  
*\# Pozor: items v CSV, filtry musí být znovu vytvořené*  
python scripts/bloom\_admin.py create emails \--capacity 5000000  
python scripts/bloom\_admin.py create phones \--capacity 5000000  
python scripts/bloom\_admin.py create ico \--capacity 500000

*\# Import items (může trvat)*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
COPY bloom\_filter\_items (filter\_name, item)   
FROM '/tmp/bloom\_items.csv' CSV HEADER;  
EOF

*\# Rebuild bloom filters z items*  
python \-c "  
from src.utils.bloom import BloomFilterManager  
bfm \= BloomFilterManager()  
for name in \['emails', 'phones', 'ico'\]:  
    bfm.rebuild\_from\_db(name)  
"

*\# 5\. Start služeb*  
sudo systemctl daemon-reload  
sudo systemctl enable scraper-worker parser-worker change-detector requeue-worker  
sudo systemctl start scraper-worker parser-worker change-detector requeue-worker

*\# 6\. Verify*

python scripts/monitor.py health

---

## **Časté dotazy (FAQ)**

### **Q: Jak rychle scraper zpracovává URL?**

**A:** Záleží na `SCRAPE_DELAY_SECONDS` (default 2s) a rychlosti webů. Přibližně:

* 1 worker: \~1800 URLs/hodina (při 2s delay)  
* 2 workers: \~3600 URLs/hodina  
* 3+ workers: diminishing returns kvůli rate-limiting

### **Q: Kolik místa zabere databáze?**

**A:** Závisí na velikosti HTML. Průměrně:

* 1 scrape\_result: \~50-200 KB (HTML \+ metadata)  
* 1 parsed\_data: \~2-5 KB (JSON)  
* 1M URL \= \~50-200 GB databáze

**Řešení:** Pravidelně mazat stará scrape\_results (keep jen parsed\_data).

### **Q: Můžu scraper zastavit a pak pokračovat?**

**A:** Ano\! Queue persistuje v databázi.

bash  
*\# Stop*  
sudo systemctl stop scraper-worker

*\# Start znovu (pokračuje kde skončil)*

sudo systemctl start scraper-worker

### **Q: Jak přidat nové URL do fronty?**

**A:**

bash  
*\# Jednotlivě*  
python scripts/queue\_admin.py add "https://newsite.com" \--unit-id 123

*\# Bulk*

python scripts/queue\_admin.py bulk-add urls.txt \--unit-id 123

### **Q: Co dělat když web blokuje bota?**

**A:**

1. Změň `USER_AGENT` v `.env` na více "human-like"  
2. Zvyš `SCRAPE_DELAY_SECONDS` (např. na 5\)  
3. Přidej doménu do blacklistu pokud trvale blokuje:

bash

  python scripts/queue\_admin.py blacklist blocked-site.com \--reason "blocks\_bot"

4. Použij proxy (pokročilé, není implementováno)

### **Q: Jak často se stránky re-scrapují?**

**A:** Podle nastavení `REQUEUE_INTERVAL_DAYS` (default 90 dní). Requeue worker automaticky přidá kvalitní stránky zpět do fronty po této době.

Manuální re-queue:

bash  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
INSERT INTO scrape\_queue (url, unit\_listing\_id, next\_scrape\_at)  
SELECT url, unit\_listing\_id, NOW()  
FROM scrape\_results sr  
JOIN parsed\_data pd ON pd.scrape\_result\_id \= sr.id  
WHERE pd.quality\_score \> 60  
  AND sr.scraped\_at \< NOW() \- INTERVAL '90 days'  
ON CONFLICT (url, unit\_listing\_id) DO UPDATE  
SET next\_scrape\_at \= NOW(), status \= 'pending';

EOF

### **Q: Jak zjistím proč konkrétní URL selhalo?**

**A:**

bash  
*\# Najdi error message*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
SELECT sq.url, sq.retry\_count, sr.status\_code, sr.error\_message  
FROM scrape\_queue sq  
LEFT JOIN scrape\_results sr ON sr.queue\_id \= sq.id  
WHERE sq.url \= 'https://problematic-site.com';

EOF

### **Q: Můžu používat aplikaci bez LLM API?**

**A:** Ano\! Použij Ollama (lokální, zdarma):

bash  
*\# Instalace Ollama*  
curl \-fsSL https://ollama.com/install.sh | sh

*\# Stáhni model*  
ollama pull llama3.2:3b

*\# Update prompts*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
UPDATE llm\_prompts SET model \= 'llama3.2:3b';

EOF

Nebo úplně vypni LLM:

bash  
*\# Deaktivuj všechny LLM prompts*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
UPDATE llm\_prompts SET is\_active \= FALSE;

EOF

Parser pak použije jen regex a structured data extraction.

### **Q: Jak změním prompt pro parsing?**

**A:**

bash  
*\# Zobraz současný prompt*  
python scripts/prompt\_admin.py show opening\_hours cs

*\# Edituj v $EDITOR*  
python scripts/prompt\_admin.py edit opening\_hours cs

*\# Nebo přímo v databázi*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
UPDATE llm\_prompts   
SET prompt\_template \= 'Nový prompt text zde...'  
WHERE use\_case \= 'opening\_hours' AND language \= 'cs';  
EOF

*\# Restart není potřeba, načte se při příštím použití*

### **Q: Co dělat když parser backlog roste?**

**A:**

bash  
*\# Spusť další parser worker*  
cd /opt/web-scraper  
source .venv/bin/activate  
nohup python src/workers/parser.py \> logs/parser-extra.log 2\>&1 &

*\# Nebo permanent (systemd)*  
sudo cp /etc/systemd/system/parser-worker.service \\  
        /etc/systemd/system/parser-worker-2.service  
sudo systemctl enable parser-worker-2

sudo systemctl start parser-worker-2

### **Q: Jak exportovat data?**

**A:**

bash  
*\# Export parsed data pro konkrétní unit\_listing\_ids*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \<\<EOF  
COPY (  
    SELECT   
        unit\_listing\_id,  
        content\_language,  
        data,  
        quality\_score,  
        extracted\_at  
    FROM parsed\_data  
    WHERE unit\_listing\_id IN (1, 2, 3, 4, 5\)  
    ORDER BY unit\_listing\_id, extracted\_at DESC  
) TO '/tmp/export.csv' CSV HEADER;  
EOF

*\# Nebo jako JSON*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \-tAc "  
SELECT json\_agg(row\_to\_json(t))  
FROM (  
    SELECT unit\_listing\_id, data, quality\_score, extracted\_at  
    FROM parsed\_data  
    WHERE unit\_listing\_id IN (1, 2, 3\)  
) t

" \> /tmp/export.json

---

## **Pokročilá konfigurace**

### **Proxy support (pro velké objemy)**

Pokud potřebuješ scraper s proxy rotation:

python  
*\# src/workers/scraper.py \- rozšíření*

PROXIES \= \[  
    'http://proxy1.example.com:8080',  
    'http://proxy2.example.com:8080',  
    *\# ...*  
\]

def scrape\_url(self, url):  
    import random  
    proxy \= random.choice(PROXIES)  
      
    with sync\_playwright() as p:  
        browser \= p.chromium.launch(  
            headless\=True,  
            proxy\={'server': proxy}  
        )

        *\# ... rest of code*

### **Custom extraction rules per domain**

sql  
*\-- Vytvoř tabulku pro domain-specific rules*  
CREATE TABLE domain\_extraction\_rules (  
    domain TEXT PRIMARY KEY,  
    rules JSONB,  
    enabled BOOLEAN DEFAULT TRUE  
);

*\-- Příklad: specifické selektory pro známou doménu*  
INSERT INTO domain\_extraction\_rules (domain, rules) VALUES  
('example.com', '{  
    "company\_name": {"selector": "h1.company-title"},  
    "phone": {"selector": ".contact-phone"},  
    "email": {"selector": "a\[href^=mailto\]", "attr": "href"}

}'::jsonb);

Pak v parser.py:

python  
def parse\_with\_custom\_rules(self, soup, domain):  
    *\# Zkontroluj zda existují custom rules*  
    cur \= self.conn.cursor()  
    cur.execute("SELECT rules FROM domain\_extraction\_rules WHERE domain \= %s", (domain,))  
    row \= cur.fetchone()  
      
    if row and row\['rules'\]:  
        rules \= row\['rules'\]  
        *\# Apply custom selectors*  
        if 'company\_name' in rules:  
            elem \= soup.select\_one(rules\['company\_name'\]\['selector'\])  
            if elem:  
                return elem.text.strip()  
      
    *\# Fallback na běžnou extraction*

    return self.extract\_text\_content(soup)

### **Webhook notifications (pro změny)**

python  
*\# src/workers/change\_detector.py \- rozšíření*

import requests

WEBHOOK\_URL \= os.getenv('WEBHOOK\_URL')

def notify\_change(self, unit\_listing\_id, changes):  
    """Pošli webhook notification při změně"""  
    if not WEBHOOK\_URL:  
        return  
      
    payload \= {  
        'unit\_listing\_id': unit\_listing\_id,  
        'changes': \[  
            {  
                'field': field,  
                'old\_value': old\_val,  
                'new\_value': new\_val  
            }  
            for field, old\_val, new\_val in changes  
        \],  
        'timestamp': datetime.now().isoformat()  
    }  
      
    try:  
        requests.post(WEBHOOK\_URL, json\=payload, timeout\=10)  
    except Exception as e:

        self.logger.error(f"Webhook failed: {e}")

---

## **Kontakt a podpora**

### **Logy pro bug reporting**

Při reportování problémů, připoj:

bash  
*\# System info*  
uname \-a  
python \--version  
psql \--version

*\# Konfigurace (BEZ citlivých dat\!)*  
cat .env | grep \-v "PASSWORD\\|API\_KEY"

*\# Recent logs (last 100 lines)*  
tail \-100 logs/scraper.log  
tail \-100 logs/parser.log

*\# Database stats*  
python scripts/monitor.py health

*\# Queue status*  
psql \-U scraper\_user \-d web\_scraper \-h localhost \-c \\

  "SELECT status, COUNT(\*) FROM scrape\_queue GROUP BY status;"

### **Update dokumentace**

Tato dokumentace je v `/opt/web-scraper/docs/admin_manual.md`

Po změnách v kódu/konfiguraci, aktualizuj dokumentaci:

bash  
nano /opt/web-scraper/docs/admin\_manual.md

git commit \-m "Update admin manual"

---

## **Appendix: Příkazy v kostce**

### **Denní operace**

bash  
*\# Status check*  
python scripts/monitor.py health

*\# Přidat URL*  
python scripts/queue\_admin.py add "https://site.com" \--unit-id 1

*\# Restart workerů*  
sudo systemctl restart scraper-worker parser-worker

*\# Sledování logů*

tail \-f logs/scraper.log

### **Troubleshooting**

bash  
*\# Check services*  
sudo systemctl status scraper-worker parser-worker

*\# Check queue*  
psql \-d web\_scraper \-c "SELECT status, COUNT(\*) FROM scrape\_queue GROUP BY status;"

*\# Reset failed*  
python scripts/queue\_admin.py reset-failed

*\# Clear queue*

python scripts/queue\_admin.py clear \--status failed

### **Maintenance**

bash  
*\# Backup*  
pg\_dump \-U scraper\_user web\_scraper | gzip \> backup\_$(date \+%Y%m%d).sql.gz

*\# Clean old data*  
psql \-d web\_scraper \-c "DELETE FROM scrape\_results WHERE scraped\_at \< NOW() \- INTERVAL '6 months';"

*\# Vacuum*

psql \-d web\_scraper \-c "VACUUM ANALYZE;"

### **Monitoring**

bash  
*\# Stats*  
python scripts/monitor.py stats \--days 7  
python scripts/monitor.py quality  
python scripts/monitor.py changes

*\# Listing detail*  
python scripts/monitor.py listing 123

*\# Prompts*  
python scripts/prompt\_admin.py stats

python scripts/prompt\_admin.py list-all

---

**Konec administrátorského manuálu**

Máš kompletní dokumentaci pro správce\! Pokud budeš potřebovat doplnit další sekce nebo specifické use-cases, dej vědět.

[Claude is AI and can make mistakes. Please double-check responses.](https://support.anthropic.com/en/articles/8525154-claude-is-providing-incorrect-or-misleading-responses-what-s-going-on)  
Claude

