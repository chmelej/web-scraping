-- Rename Primary Keys to match table suffix for better clarity in joins
ALTER TABLE scr_scrape_queue RENAME COLUMN id TO queue_id;
ALTER TABLE scr_scrape_results RENAME COLUMN id TO result_id;
ALTER TABLE scr_parsed_data RENAME COLUMN id TO parsed_id;
ALTER TABLE scr_change_history RENAME COLUMN id TO change_id;
ALTER TABLE scr_domain_blacklist RENAME COLUMN id TO blacklist_id;
ALTER TABLE scr_domain_multipage_rules RENAME COLUMN id TO rule_id;
ALTER TABLE scr_llm_prompts RENAME COLUMN id TO prompt_id;
ALTER TABLE scr_prompt_stats RENAME COLUMN id TO stat_id;
ALTER TABLE scr_bloom_filters RENAME COLUMN id TO filter_id;
ALTER TABLE scr_bloom_filter_items RENAME COLUMN id TO item_id;
ALTER TABLE scr_config RENAME COLUMN id TO config_id;

-- Add 'opco' column (Operating Company / Country Code)
-- Default to NULL or maybe 'unknown' initially.
ALTER TABLE scr_scrape_queue ADD COLUMN opco VARCHAR(10);
ALTER TABLE scr_parsed_data ADD COLUMN opco VARCHAR(10);
ALTER TABLE scr_change_history ADD COLUMN opco VARCHAR(10);

-- Re-create Views because renaming columns usually invalidates or subtly breaks views depending on how they were defined (SELECT * vs named columns)
DROP VIEW IF EXISTS scr_queue_stats;
CREATE VIEW scr_queue_stats AS
SELECT status, count(*) as count, avg(retry_count) as avg_retries
FROM scr_scrape_queue
GROUP BY status;

DROP VIEW IF EXISTS scr_daily_scrapes;
CREATE VIEW scr_daily_scrapes AS
SELECT date_trunc('day', scraped_at) as day, count(*) as count,
       sum(case when status_code = 200 then 1 else 0 end) as success_count
FROM scr_scrape_results
GROUP BY 1
ORDER BY 1 DESC;
