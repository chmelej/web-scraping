-- Add html_path and html_size columns to scr_scrape_results to offload raw HTML to disk/NFS

ALTER TABLE scr_scrape_results 
ADD COLUMN IF NOT EXISTS html_path TEXT,
ADD COLUMN IF NOT EXISTS html_size BIGINT;
