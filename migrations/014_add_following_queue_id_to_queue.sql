-- Add following_queue_id column to scr_scrape_queue as FK to scr_scrape_queue(queue_id)

ALTER TABLE scr_scrape_queue
ADD COLUMN IF NOT EXISTS following_queue_id INTEGER REFERENCES scr_scrape_queue(queue_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_scr_queue_following_queue_id ON scr_scrape_queue(following_queue_id);
