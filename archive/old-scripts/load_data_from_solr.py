# load_solr_to_rag.py
import argparse
import json
import sys
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from sqlalchemy import create_engine, text
from myutils import load_properties


DEFAULT_SOLR_URL = "http://prod-solr-be-w1.fcrtech.cz:8080/solr/yp-web-nl-be-v30/select"
BATCH_SIZE = 100  # per requirement: batches of 100 ids
DEFAULT_EXCLUDED_FIELDS = {
    "listing_status", "customer_id", "addr_path", "category_id", "folder_geopoints", "geo_location_rpt",
    "wijwerken_status", "sort_value", "old_id", "_version_", "az_index_l2", "az_index_l1",
    "traffic_image", "logo", "gallery","geo_zoning"
    # example field we don't want to store initially
}
CONNECT_TIMEOUT_SEC = 30
READ_TIMEOUT_SEC = 60


def solr_escape_term(term: str) -> str:
    """
    Escape a single SOLR term for use in a query.
    We'll wrap it in double quotes to be safe and escape inner quotes/backslashes.
    """
    if term is None:
        return '""'
    s = str(term).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def build_solr_query(ids: List[str]) -> str:
    """
    Build a SOLR q parameter querying documents by id: id:("id1" OR "id2" ...)
    """
    if not ids:
        return "*:*"
    escaped = " OR ".join(solr_escape_term(v) for v in ids)
    return f"id:({escaped})"


def call_solr(solr_url: str, ids: List[str], fl: Optional[str] = None) -> Dict:
    """
    Perform a SOLR select call for the given batch of ids.
    Returns parsed JSON dict.
    """
    params = {
        "q": build_solr_query(ids),
        "rows": len(ids),
        "wt": "json",
    }
    if fl:
        params["fl"] = fl

    query = f"{solr_url}?{urlencode(params)}"
    req = Request(query, headers={"Accept": "application/json"})
    with urlopen(req, timeout=CONNECT_TIMEOUT_SEC) as resp:
        # Note: urlopen has a single timeout for connect; set default global if needed
        data = resp.read()
    return json.loads(data)


def filter_document(doc: Dict, excluded_fields: Iterable[str]) -> Dict:
    """
    Remove fields we don't want to store. Extend excluded_fields as needed.
    """
    excluded = set(excluded_fields or [])
    return {k: v for k, v in doc.items() if k not in excluded}


def chunked(iterable: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def load_uni_listing_ids(engine) -> List[str]:
    """
    Load all uni_listing_id values from tmp_uni_listing_ai.
    """
    with engine.begin() as conn:
        rows = conn.execute(text("select uni_listing_id from tmp_uni_listing_ai")).fetchall()
    return [str(r[0]) for r in rows if r and r[0] is not None]


def upsert_rag_solr_data(engine, rows: List[Dict]):
    """
    Insert rows into rag_solr_data. Assumes table exists.
    Schema:
      uni_listing_id varchar(50),
      version_id int,
      meta_modified_when timestamp,
      unstructured_text text
    """
    if not rows:
        return
    # Use explicit SQL for performance and compatibility
    sql = text("""
        insert into rag_solr_data (uni_listing_id, version_id, meta_modified_when, unstructured_text)
        values (:uni_listing_id, :version_id, now(), :unstructured_text)
    """)
    with engine.begin() as conn:
        conn.execute(sql, rows)


def main():
    parser = argparse.ArgumentParser(description="Load filtered SOLR docs into rag_solr_data.")
    parser.add_argument("--version-id", type=int, required=True, help="Constant version_id to store in DB.")
    parser.add_argument("--solr-url", default=DEFAULT_SOLR_URL, help="SOLR select endpoint URL.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of ids to process (debug).")
    parser.add_argument(
        "--exclude-field",
        action="append",
        dest="exclude_fields",
        default=[],
        help="Field name to exclude from stored JSON. May be specified multiple times.",
    )
    parser.add_argument(
        "--fl",
        default=None,
        help="SOLR 'fl' parameter (fields list). If omitted, SOLR returns default stored fields.",
    )
    args = parser.parse_args()

    excluded_fields = set(DEFAULT_EXCLUDED_FIELDS) | set(args.exclude_fields or [])

    # Configure DB connection
    config = load_properties("config.properties")
    engine = create_engine(
        f"postgresql+psycopg2://{config['username']}:{config['password']}@{config['hostname']}:5432/{config['dbname']}"
    )

    # Load ids from DB
    all_ids = load_uni_listing_ids(engine)
    if args.limit is not None:
        all_ids = all_ids[: args.limit]

    total = len(all_ids)
    if total == 0:
        print("No uni_listing_id found in tmp_uni_listing_ai. Nothing to do.")
        sys.exit(0)

    print(f"Processing {total} uni_listing_id in batches of {BATCH_SIZE}...")
    processed = 0
    for batch_ids in chunked(all_ids, BATCH_SIZE):
        try:
            solr_json = call_solr(args.solr_url, batch_ids, fl=args.fl)
        except Exception as e:
            print(f"ERROR: SOLR request failed for batch starting with {batch_ids[0]}: {e}")
            continue

        docs = (solr_json or {}).get("response", {}).get("docs", []) or []
        rows = []
        # Index docs by id for quick lookup if needed
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            doc_id = doc.get("id")
            if not doc_id:
                continue

            filtered = filter_document(doc, excluded_fields)
            rows.append({
                "uni_listing_id": str(doc_id),
                "version_id": args.version_id,
                "unstructured_text": json.dumps(filtered, ensure_ascii=False),
            })

        if rows:
            try:
                upsert_rag_solr_data(engine, rows)
            except Exception as e:
                print(f"ERROR: DB insert failed for batch starting with {batch_ids[0]}: {e}")

        processed += len(batch_ids)
        pct = (processed / total) * 100.0
        print(f"Progress: {processed}/{total} ({pct:.1f}%)")

    print("Done.")


if __name__ == "__main__":
    main()

