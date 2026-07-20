-- Migration to add cascade delete functions for scr_scrape_queue

CREATE OR REPLACE FUNCTION delete_cascade_scr_scrape_queue(queue_ids bigint[])
RETURNS void AS $$
DECLARE
    target_result_ids int[];
BEGIN
    -- 1. Get result IDs that will be deleted
    SELECT array_agg(result_id) INTO target_result_ids
    FROM scr_scrape_results
    WHERE queue_id = ANY(queue_ids);

    -- 2. Handle parent_scrape_id references in queue (set to NULL)
    IF target_result_ids IS NOT NULL THEN
        UPDATE scr_scrape_queue
        SET parent_scrape_id = NULL
        WHERE parent_scrape_id = ANY(target_result_ids);
        
        -- 3. Delete parsed data
        DELETE FROM scr_parsed_data
        WHERE result_id = ANY(target_result_ids);
    END IF;

    -- 4. Delete scrape results
    DELETE FROM scr_scrape_results
    WHERE queue_id = ANY(queue_ids);

    -- 5. Delete queue items
    DELETE FROM scr_scrape_queue
    WHERE queue_id = ANY(queue_ids);
END;
$$ LANGUAGE plpgsql;

-- Alias to handle potential typo in invocation
CREATE OR REPLACE FUNCTION delete_cescade_scr_scrape_queue(queue_ids bigint[])
RETURNS void AS $$
BEGIN
    PERFORM delete_cascade_scr_scrape_queue(queue_ids);
END;
$$ LANGUAGE plpgsql;
