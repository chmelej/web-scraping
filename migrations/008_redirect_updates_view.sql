-- View to inspect and export redirected canonical URLs (e.g., http -> https, domain changes)

CREATE OR REPLACE VIEW scr_redirect_canonical_updates AS
SELECT 
    q.uni_listing_id,
    q.opco,
    r.redirected_from AS original_url,
    r.url AS canonical_url,
    r.status_code,
    r.scraped_at
FROM scr_scrape_results r
JOIN scr_scrape_queue q ON r.queue_id = q.queue_id
WHERE r.redirected_from IS NOT NULL 
  AND r.redirected_from != r.url;
