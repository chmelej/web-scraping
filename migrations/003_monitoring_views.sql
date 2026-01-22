CREATE VIEW scraping_health AS
SELECT
    status,
    COUNT(*) as count,
    AVG(retry_count) as avg_retries
FROM scrape_queue
GROUP BY status;

CREATE VIEW daily_stats AS
SELECT
    DATE(scraped_at) as date,
    COUNT(*) as total_scrapes,
    COUNT(*) FILTER (WHERE status_code = 200) as successful,
    COUNT(DISTINCT detected_language) as languages
FROM scrape_results
WHERE scraped_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(scraped_at)
ORDER BY date DESC;

CREATE VIEW quality_distribution AS
SELECT
    CASE
        WHEN quality_score >= 80 THEN 'excellent'
        WHEN quality_score >= 60 THEN 'good'
        WHEN quality_score >= 40 THEN 'fair'
        ELSE 'poor'
    END as quality,
    COUNT(*) as count
FROM parsed_data
GROUP BY
    CASE
        WHEN quality_score >= 80 THEN 'excellent'
        WHEN quality_score >= 60 THEN 'good'
        WHEN quality_score >= 40 THEN 'fair'
        ELSE 'poor'
    END
ORDER BY quality DESC;

CREATE VIEW recent_changes AS
SELECT
    unit_listing_id,
    field_name,
    COUNT(*) as change_count,
    MAX(detected_at) as last_change
FROM change_history
WHERE detected_at > NOW() - INTERVAL '30 days'
GROUP BY unit_listing_id, field_name
ORDER BY last_change DESC
LIMIT 100;

CREATE VIEW blacklist_summary AS
SELECT
    reason,
    COUNT(*) as domain_count,
    AVG(fail_count) as avg_fails
FROM domain_blacklist
GROUP BY reason
ORDER BY domain_count DESC;
