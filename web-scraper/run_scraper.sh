#!/bin/bash
while true; do
    # Run scraper with a 5-minute timeout (300s).
    # If it hangs, send SIGTERM. If it ignores that for 10s, send SIGKILL.
    timeout --kill-after=10s 300s uv run python -m src.workers.scraper
    EXIT_CODE=$?
    
    # timeout command returns 124 if it timed out
    if [ $EXIT_CODE -eq 124 ]; then
        echo "Scraper timed out (hung) and was killed. Restarting..."
        sleep 5
    elif [ $EXIT_CODE -eq 10 ]; then
        echo "Queue empty, waiting 60s..."
        sleep 60
    elif [ $EXIT_CODE -ne 0 ]; then
        echo "Scraper exited with error (code $EXIT_CODE), restarting in 5s..."
        sleep 5
    else
        echo "Batch finished, starting next batch..."
        # Optional small sleep to let system breathe
        sleep 1
    fi
done

