-- Add normalized_url column to scr_scrape_queue for URL deduplication

ALTER TABLE scr_scrape_queue
ADD COLUMN IF NOT EXISTS normalized_url TEXT;

CREATE INDEX IF NOT EXISTS idx_scr_queue_normalized_url ON scr_scrape_queue(normalized_url);
