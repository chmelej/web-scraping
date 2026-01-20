-- Initial Schema

CREATE TABLE scr_scrape_queue (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    unit_listing_id INTEGER,
    parent_scrape_id INTEGER,
    depth INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    next_scrape_at TIMESTAMP DEFAULT NOW(),
    added_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(url, unit_listing_id)
);

CREATE INDEX idx_queue_status ON scr_scrape_queue(status, next_scrape_at);
CREATE INDEX idx_queue_unit ON scr_scrape_queue(unit_listing_id);

CREATE TABLE scr_scrape_results (
    id SERIAL PRIMARY KEY,
    queue_id INTEGER REFERENCES scr_scrape_queue(id),
    url TEXT NOT NULL,
    html TEXT,
    status_code INTEGER,
    headers JSONB,
    ip_address INET,
    redirected_from TEXT,
    detected_language VARCHAR(5),
    language_confidence FLOAT,
    scraped_at TIMESTAMP DEFAULT NOW(),
    processing_status VARCHAR(20) DEFAULT 'new',
    error_message TEXT
);

CREATE INDEX idx_results_processing ON scr_scrape_results(processing_status);
CREATE INDEX idx_results_language ON scr_scrape_results(detected_language);

CREATE TABLE scr_parsed_data (
    id SERIAL PRIMARY KEY,
    scrape_result_id INTEGER REFERENCES scr_scrape_results(id),
    unit_listing_id INTEGER,
    content_language VARCHAR(5),
    data JSONB,
    quality_score INTEGER,
    extracted_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_parsed_unit ON scr_parsed_data(unit_listing_id);
CREATE INDEX idx_parsed_quality ON scr_parsed_data(quality_score);

CREATE TABLE scr_change_history (
    id SERIAL PRIMARY KEY,
    unit_listing_id INTEGER NOT NULL,
    field_name VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    detected_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_changes_unit ON scr_change_history(unit_listing_id);
CREATE INDEX idx_changes_date ON scr_change_history(detected_at);

CREATE TABLE scr_domain_blacklist (
    domain TEXT PRIMARY KEY,
    reason VARCHAR(50),
    fail_count INTEGER DEFAULT 0,
    first_failed_at TIMESTAMP,
    last_failed_at TIMESTAMP,
    auto_added BOOLEAN DEFAULT TRUE,
    notes TEXT
);

CREATE TABLE scr_domain_multipage_rules (
    domain TEXT PRIMARY KEY,
    url_patterns JSONB,
    max_depth INTEGER DEFAULT 2,
    enabled BOOLEAN DEFAULT TRUE
);

CREATE TABLE scr_bloom_filters (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE,
    filter_data BYTEA,
    item_count INTEGER DEFAULT 0,
    false_positive_rate FLOAT DEFAULT 0.001,
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP DEFAULT NOW()
);

CREATE TABLE scr_bloom_filter_items (
    filter_name VARCHAR(50),
    item TEXT,
    added_at TIMESTAMP DEFAULT NOW(),
    source VARCHAR(50),
    PRIMARY KEY (filter_name, item)
);

CREATE TABLE scr_llm_prompts (
    id SERIAL PRIMARY KEY,
    use_case VARCHAR(50) NOT NULL,
    language VARCHAR(5) NOT NULL,
    prompt_template TEXT NOT NULL,
    system_prompt TEXT,
    model VARCHAR(50) DEFAULT 'claude-3-5-haiku-20241022',
    max_tokens INTEGER DEFAULT 200,
    temperature FLOAT DEFAULT 0.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    notes TEXT,
    UNIQUE(use_case, language)
);

CREATE TABLE scr_prompt_stats (
    prompt_id INTEGER REFERENCES scr_llm_prompts(id),
    date DATE DEFAULT CURRENT_DATE,
    executions INTEGER DEFAULT 0,
    successes INTEGER DEFAULT 0,
    avg_tokens INTEGER,
    PRIMARY KEY (prompt_id, date)
);

CREATE TABLE scr_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    description TEXT
);
