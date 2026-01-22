-- Rename tables with scr_ prefix
ALTER TABLE scrape_queue RENAME TO scr_scrape_queue;
ALTER TABLE scrape_results RENAME TO scr_scrape_results;
ALTER TABLE parsed_data RENAME TO scr_parsed_data;
ALTER TABLE change_history RENAME TO scr_change_history;
ALTER TABLE domain_blacklist RENAME TO scr_domain_blacklist;
ALTER TABLE domain_multipage_rules RENAME TO scr_domain_multipage_rules;
ALTER TABLE bloom_filters RENAME TO scr_bloom_filters;
ALTER TABLE bloom_filter_items RENAME TO scr_bloom_filter_items;
ALTER TABLE llm_prompts RENAME TO scr_llm_prompts;
ALTER TABLE prompt_stats RENAME TO scr_prompt_stats;
ALTER TABLE config RENAME TO scr_config;

-- Rename unit_listing_id to uni_listing_id in all tables
ALTER TABLE scr_scrape_queue RENAME COLUMN unit_listing_id TO uni_listing_id;
ALTER TABLE scr_parsed_data RENAME COLUMN unit_listing_id TO uni_listing_id;
ALTER TABLE scr_change_history RENAME COLUMN unit_listing_id TO uni_listing_id;

-- Rename indexes to match new table names (optional but good practice)
-- Postgres renames indexes automatically when table is renamed? 
-- Usually yes, but names might still be old. We can rename them explicitly if needed.
-- For now, relying on Postgres behavior is fine, but the column rename might need index rename if index name contains column name.

-- Re-create indexes if names are confusing or just let them be.
-- However, we must ensure constraints are valid.

-- Update unique constraints if they rely on the column name
-- (Postgres handles this automatically)

-- Create or update views if any exist (migrations/003_monitoring_views.sql might be broken)
-- We should probably drop and recreate views with new names.

DROP VIEW IF EXISTS queue_stats;
DROP VIEW IF EXISTS daily_scrapes;

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
