# load_data_to_openai_to_formating.py
import argparse
import json
from typing import Dict, List, Optional
from urllib.request import urlopen, Request
from sqlalchemy import create_engine, text
from myutils import load_properties
import time

CONNECT_TIMEOUT_SEC = 30
READ_TIMEOUT_SEC = 60

OPENAI_API_BASE = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-5-mini"
OPENAI_BATCH_MAX_ITEMS = 2000  # OpenAI limit safety cap
OPENAI_BATCH_POLL_SEC = 10
CONFIG = {}

# -------- OpenAI Batch: Submit and Fetch data --------


def get_db_engine():
    global CONFIG
    return create_engine(
        f"postgresql+psycopg2://{CONFIG['username']}:{CONFIG['password']}@{CONFIG['hostname']}:5432/{CONFIG['dbname']}"
    )


def fetch_candidate_rows(engine, limit: int) -> List[Dict]:
    """
    Select rows that need processing: formated_md_nl is NULL and ext_id is NULL.
    """
    sql = text("""
               select id, unstructured_text
               from rag_solr_data
               where formated_md_nl is null and ext_id is null order by id limit :lim
               """)
    with engine.begin() as conn:
        rows = conn.execute(sql, {"lim": limit}).mappings().all()
    out = []
    for r in rows:
        try:
            out.append({
                "id": int(r["id"]),
                "unstructured_text": r["unstructured_text"],
            })
        except Exception:
            continue
    return out


def http_openai_request(method: str, path: str, body: Optional[dict] = None, stream: bool = False):
    """
    Minimal HTTP helper for OpenAI REST API. Returns dict for JSON, or raw bytes for file content.
    """
    global CONFIG
    api_key = CONFIG['openai_api_key'] # os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required")

    url = f"{OPENAI_API_BASE}{path}"
    data_bytes = None
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    if body is not None:
        data_bytes = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=data_bytes, method=method, headers=headers)
    with urlopen(req, timeout=READ_TIMEOUT_SEC) as resp:
        raw = resp.read()
        if stream:
            return raw
        if raw:
            return json.loads(raw.decode("utf-8"))
        return {}


def http_openai_upload_bytes_jsonl(content_bytes: bytes, purpose: str) -> str:
    global CONFIG
    """
    Upload a JSONL file via multipart/form-data to OpenAI Files API.
    Returns file_id.
    """
    api_key = CONFIG['openai_api_key'] # os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required")

    boundary = f"----WebKitFormBoundary{int(time.time()*1000)}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }

    # Build multipart body
    parts: List[bytes] = []
    def add_field(name: str, value: str):
        parts.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode(), b"\r\n",
        ])
    def add_file(name: str, filename: str, content_type: str, data: bytes):
        parts.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            data, b"\r\n",
        ])

    add_field("purpose", purpose)
    add_file("file", "requests.jsonl", "application/jsonl", content_bytes)
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    req = Request(f"{OPENAI_API_BASE}/files", data=body, method="POST", headers=headers)
    with urlopen(req, timeout=READ_TIMEOUT_SEC) as resp:
        raw = resp.read()
    data = json.loads(raw.decode("utf-8"))
    return data["id"]


def build_batch_jsonl(rows: List[Dict], model: str, prompt_prefix: str) -> bytes:
    """
    Build JSONL for OpenAI Batch API using /v1/responses endpoint.
    Each line contains: custom_id, method, url, body
    custom_id is set to id for mapping back.
    """
    lines: List[bytes] = []
    for r in rows:
        id = r["id"]
        try:
            src = r["unstructured_text"]
            # Accept both JSON strings or raw text in the column
            if isinstance(src, str):
                # When column stores filtered JSON: keep as-is text
                body_text = src
            else:
                body_text = json.dumps(src, ensure_ascii=False)
        except Exception:
            body_text = ""

        full_input = f"{prompt_prefix}\n\n{body_text}".strip()

        body = {
            "model": model,
            "input": full_input,
            # Ensure we get text output
            "max_output_tokens": 4000, # 4x 1000
        }
        line = {
            "custom_id": id,
            "method": "POST",
            "url": "/v1/responses",
            "body": body,
        }
        lines.append((json.dumps(line, ensure_ascii=False) + "\n").encode("utf-8"))
    return b"".join(lines)


def create_openai_batch(input_file_id: str, endpoint: str = "/v1/responses") -> Dict:
    """
    Create a batch job referencing the uploaded file.
    Returns batch object with id, status.
    """
    payload = {
        "input_file_id": input_file_id,
        "endpoint": endpoint,
        "completion_window": "24h",
    }
    return http_openai_request("POST", "/batches", body=payload)


def update_rows_ext_id(engine, ids: List[str], batch_id: str):
    """
    Mark rows as submitted by storing the batch_id into ext_id.
    """
    if not ids:
        return
    sql = text("""
               update rag_solr_data set ext_id = :batch_id
               where id = ANY(:ids) and ext_id is null and formated_md_nl is null
               """)
    with engine.begin() as conn:
        conn.execute(sql, {"batch_id": batch_id, "ids": ids})


def fetch_rows_with_batch(engine, batch_id: Optional[str], limit: Optional[int] = None) -> List[str]:
    """
    Return distinct id (or just list of ids) that are linked to a batch (ext_id).
    If batch_id is None, returns distinct ext_id values that still need results.
    """
    if batch_id:
        sql = text("""
                   select distinct ext_id
                   from rag_solr_data where ext_id = :bid and formated_md_nl is null
                   order by id
                   """)
        with engine.begin() as conn:
            return [r[0] for r in conn.execute(sql, {"bid": batch_id}).fetchall()]
    else:
        sql = text("""
                   select distinct ext_id
                   from rag_solr_data
                   where ext_id is not null and formated_md_nl is null
                   order by ext_id {limit_clause} """.replace("{limit_clause}", f"limit {int(limit)}" if limit else ""))
        with engine.begin() as conn:
            return [r[0] for r in conn.execute(sql).fetchall()]


def download_batch_output_file(output_file_id: str) -> List[Dict]:
    """
    Download and parse the JSONL content of the batch output file.
    Returns list of parsed JSON dicts per line.
    """
    # First get file content
    raw = http_openai_request("GET", f"/files/{output_file_id}/content", stream=True)
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            lines.append(json.loads(line))
        except Exception:
            continue
    return lines


def extract_text_from_response_object(resp: Dict) -> str:
    """
    Extract textual output from a Responses API result body.
    Tries 'output_text' then falls back to concatenating text parts.
    """
    body = resp.get("response", {}).get("body") or {}
    # Prefer 'output_text' if present
    if "output_text" in body and isinstance(body["output_text"], str):
        return body["output_text"]
    # Fallback: collect text from output array
    out = []
    for item in body.get("output", []) or []:
        if isinstance(item, dict):
            content = item.get("content")
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "output_text":
                        txt = c.get("text", "")
                        if txt:
                            out.append(txt)
    return "\n".join(out).strip()


def apply_batch_results_to_db(engine, batch_output_lines: List[Dict], batch_id: str):
    """
    Update rag_solr_data.formated_md_nl for each custom_id in output lines.
    """
    updates: List[Dict] = []
    for line in batch_output_lines:
        custom_id = line.get("custom_id")
        if not custom_id:
            continue
        text_out = extract_text_from_response_object(line)
        if not text_out:
            continue
        updates.append({"id": custom_id, "formated_md_nl": text_out})

    if not updates:
        return

    sql = text("""
               update rag_solr_data
               set formated_md_nl = :formated_md_nl
               where id = :id and ext_id = :batch_id
               """)
    with engine.begin() as conn:
        for u in updates:
            conn.execute(sql, {
                "formated_md_nl": u["formated_md_nl"],
                "id": u["id"],
                "batch_id": batch_id,
            })


def clear_ext_id_where_done(engine, batch_id: str):
    """
    Optional: clear ext_id for rows where formated_md_nl is now filled.
    """
    sql = text("""
               update rag_solr_data
               set ext_id = null
               where ext_id = :batch_id and formated_md_nl is not null
               """)
    with engine.begin() as conn:
        conn.execute(sql, {"batch_id": batch_id})


def do_submit(args):
    engine = get_db_engine()
    limit = min(args.limit, OPENAI_BATCH_MAX_ITEMS)
    rows = fetch_candidate_rows(engine, limit=limit)
    if not rows:
        print("Nothing to submit. All rows processed or already submitted.")
        return

    prompt_prefix = args.prompt or ""
    if args.prompt_file:
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            prompt_prefix = f.read().strip()

    json_bytes = build_batch_jsonl(rows, model=args.model or DEFAULT_OPENAI_MODEL, prompt_prefix=prompt_prefix)
    file_id = http_openai_upload_bytes_jsonl(json_bytes, purpose="batch")
    batch = create_openai_batch(file_id)
    batch_id = batch.get("id")
    if not batch_id:
        raise RuntimeError(f"Failed to create batch: {batch}")

    print(f"Created OpenAI batch: {batch_id}, status: {batch.get('status')}")
    update_rows_ext_id(engine, [r["id"] for r in rows], batch_id)
    print(f"Marked {len(rows)} rows with ext_id={batch_id}")


def do_fetch(args):
    engine = get_db_engine()

    # Determine batches to fetch
    batch_ids: List[str]
    if args.batch_id:
        batch_ids = [args.batch_id]
    else:
        # Fetch distinct batch ids from DB that are still pending results
        batch_ids = fetch_rows_with_batch(engine, batch_id=None, limit=args.limit or 50)
        if not batch_ids:
            print("No pending batches found in DB (ext_id).")
            return

    for bid in batch_ids:
        batch_info = http_openai_request("GET", f"/batches/{bid}")
        status = batch_info.get("status")
        print(f"Batch {bid} status: {status}")
        if status != "completed":
            # Optionally display error states or in-progress
            continue
        output_file_id = batch_info.get("output_file_id")
        if not output_file_id:
            print(f"Batch {bid} has no output_file_id")
            continue
        lines = download_batch_output_file(output_file_id)
        if not lines:
            print(f"No results in batch output for {bid}")
            continue
        apply_batch_results_to_db(engine, lines, bid)
        clear_ext_id_where_done(engine, bid)
        print(f"Applied results for batch {bid}.")


def main():
    global CONFIG
    CONFIG = load_properties("config.properties")

    parser = argparse.ArgumentParser(description="OpenAI batch processor for rag_solr_data.")
    sub = parser.add_subparsers(dest="mode")

    # -- Mode: submit (OpenAI batch submit) --
    p_submit = sub.add_parser("submit", help="Submit rows to OpenAI Batch API; store batch id in ext_id.")
    p_submit.add_argument("--limit", type=int, default=20, help="Max rows to include in a single batch.")
    p_submit.add_argument("--model", type=str, default=DEFAULT_OPENAI_MODEL, help="OpenAI model for responses.")
    p_submit.add_argument("--prompt", type=str, default=None, help="Constant prompt prefix.")
    p_submit.add_argument("--prompt-file", type=str, default=None, help="Path to file containing prompt prefix.")

    # -- Mode: fetch (OpenAI batch fetch results) --
    p_fetch = sub.add_parser("fetch", help="Fetch results for completed batches and write formated_md_nl.")
    p_fetch.add_argument("--batch-id", type=str, default=None, help="Specific batch id to fetch; if omitted, fetch all pending ext_id batches found in DB.")
    p_fetch.add_argument("--limit", type=int, default=20, help="Max number of distinct batches to fetch when --batch-id not provided.")

    args = parser.parse_args()

    if args.mode == "submit":
        do_submit(args)
        return
    if args.mode == "fetch":
        do_fetch(args)
        return

    print("Done.")

if __name__ == "__main__":
    main()