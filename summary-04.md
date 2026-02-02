# Session Summary - Scraper Robustness & Performance Fixes

## Problem Statement
The scraper was experiencing two major issues:
1. **Database Stagnation:** A massive number of items (over 100,000) remained in the `processing` state indefinitely.
2. **Framework Instability:** The scraper was accumulationg hundreds of thousands of JSON files in `storage/request_queues/`, leading to filesystem bottlenecks and eventual process stalls.
3. **Execution Crashes:** Neocmplatibility with certain `PlaywrightCrawler` arguments caused the scraper to crash or skip requests silently.

## Root Cause Analysis
- **Orphaned Records:** The scraper set the `processing` status before starting the crawl, but if the crawler crashed or "lost" a request (due to silent errors or browser crashes), the status never transitioned to `completed` or `failed`.
- **Disk Overhead:** Crawlee's default `FileSystemStorageClient` created a separate JSON file for every request. At scale, the overhead of managing these files caused the crawler to lag or fail to trigger callbacks.
- **Argument Conflict:** Passing `timeout` and `waitUntil` inside `goto_options` caused `TypeError` in recent versions of Crawlee/Playwright.
- **Batch Blocking:** A single hanging request could block the completion of an entire batch, effectively stopping the scraper.

## Implemented Solutions

### 1. Architectural Changes (`src/workers/scraper.py`)
- **Memory Storage:** Switched the crawler to `MemoryStorageClient()`. This eliminates all disk I/O for the request queue, preventing the accumulation of thousands of JSON files and significantly increasing throughput.
- **Batch Reconciliation (Cleanup):** Added `reconcile_batch_sync`. After every batch (100 URLs), the scraper checks the database for any items from that specific batch still in the `processing` state and moves them to `failed`. This ensures no item stays "stuck" for longer than one batch cycle.
- **Hard Execution Timeout:** Wrapped the batch execution in `asyncio.wait_for(..., timeout=300)`. If a batch takes longer than 5 minutes (due to a deadlock or hanging browser), it is forcibly terminated to allow the reconciliation logic to run and the next batch to start.

### 2. Bug Fixes
- **Playwright Configuration:** 
    - Removed `timeout` from `goto_options` and replaced it with `navigation_timeout` in the `PlaywrightCrawler` constructor.
    - Removed `waitUntil` from `goto_options` to avoid `TypeError`.
- **Logging:** Enabled `crawlee` logging during debugging to identify internal framework failures.

### 3. Database Maintenance
- Verified that `failed` items are now correctly tracked in `scr_scrape_queue` even when a network/DNS error (like `net::ERR_NAME_NOT_RESOLVED`) occurs.

## Resilience Improvements
The system is now "Self-Healing":
- If the **database** loses a connection, the batch will fail and be caught by the next run.
- If the **browser** crashes or hangs, the 300s timeout will kill it.
- If **Crawlee** drops a request, the `reconcile_batch_sync` will find it and mark it as failed.

## Recommendations for User
1. **Manual Cleanup:** Run `rm -rf storage/request_queues/default` one last time to clear the accumulated 100k+ files.
2. **Monitoring:** Monitor `logs/scraper.log`. You should see "Starting batch execution" followed by either success or "Reconciled X stuck items".
3. **Queue Health:** Periodically check `SELECT status, count(*) FROM scr_scrape_queue GROUP BY status;`. The `processing` count should never exceed your batch size (100) while the scraper is running normally.
