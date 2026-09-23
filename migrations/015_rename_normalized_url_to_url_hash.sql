-- Rename normalized_url column to url_hash in scr_scrape_queue
ALTER TABLE scr_scrape_queue RENAME COLUMN normalized_url TO url_hash;

-- Rename index
ALTER INDEX IF EXISTS idx_scr_queue_normalized_url RENAME TO idx_scr_queue_url_hash;
