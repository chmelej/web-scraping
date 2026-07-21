-- Table to store legacy metadata imported from Ondrej's TSV files (temporary table)

CREATE TABLE IF NOT EXISTS tmp_ondrej_metadata (
    id SERIAL PRIMARY KEY,
    sourcefile_url TEXT,
    encoded_sourcefile TEXT,
    system_url TEXT,
    encoded_system_url TEXT,
    version TIMESTAMP,
    state VARCHAR(50),
    status_code INT,
    redirect_as TEXT,
    raw_data JSONB,
    imported_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ondrej_meta_enc_sf ON tmp_ondrej_metadata(encoded_sourcefile);
CREATE INDEX IF NOT EXISTS idx_ondrej_meta_enc_sys ON tmp_ondrej_metadata(encoded_system_url);
