-- Drop views that depend on uni_listing_id
DROP VIEW IF EXISTS scr_recent_changes;
DROP VIEW IF EXISTS scr_queue_stats;
DROP VIEW IF EXISTS scr_daily_scrapes;
-- Also drop any other views from 003 that might exist
DROP VIEW IF EXISTS queue_stats;
DROP VIEW IF EXISTS daily_scrapes;
DROP VIEW IF EXISTS scraping_health;
DROP VIEW IF EXISTS daily_stats;
DROP VIEW IF EXISTS quality_distribution;
DROP VIEW IF EXISTS blacklist_summary;
DROP VIEW IF EXISTS recent_changes;

-- Alter types
ALTER TABLE scr_scrape_queue ALTER COLUMN uni_listing_id TYPE VARCHAR(50);
ALTER TABLE scr_parsed_data ALTER COLUMN uni_listing_id TYPE VARCHAR(50);
ALTER TABLE scr_change_history ALTER COLUMN uni_listing_id TYPE VARCHAR(50);

-- Re-create basic views
CREATE VIEW scr_queue_stats AS
SELECT status, count(*) as count, avg(retry_count) as avg_retries
FROM scr_scrape_queue
GROUP BY status;

CREATE VIEW scr_daily_scrapes AS
SELECT date_trunc('day', scraped_at) as day, count(*) as count,
       sum(case when status_code = 200 then 1 else 0 end) as success_count
FROM scr_scrape_results
GROUP BY 1
ORDER BY 1 DESC;
