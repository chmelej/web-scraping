ALTER TABLE parsed_data ADD COLUMN change_checked BOOLEAN DEFAULT FALSE;
CREATE INDEX idx_parsed_checked ON parsed_data(change_checked);
