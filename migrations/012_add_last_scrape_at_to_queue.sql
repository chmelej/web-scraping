-- Add last_scrape_at column to scr_scrape_queue

ALTER TABLE scr_scrape_queue
ADD COLUMN IF NOT EXISTS last_scrape_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_scr_queue_last_scrape_at ON scr_scrape_queue(last_scrape_at);
