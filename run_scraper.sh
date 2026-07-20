#!/bin/bash
while true; do
    date
    # Run scraper with a 10-minute timeout (600s).
    # If it hangs, send SIGTERM. If it ignores that for 10s, send SIGKILL.
    timeout --kill-after=10s 600s uv run python -m src.workers.scraper  &> "logs/scraper-`date +%s`.log"
    EXIT_CODE=$?
   
    if [ -e 'STOP' ] ; then echo STOP ; rm 'STOP' ; exit 0 ; fi

    # timeout command returns 124 if it timed out
    if [ $EXIT_CODE -eq 124 ]; then
        echo "Scraper timed out (hung) and was killed. Restarting..."
        sleep 5
    elif [ $EXIT_CODE -eq 10 ]; then
        #echo "Queue empty, waiting 60s..."
        #sleep 60
        exit 0
    elif [ $EXIT_CODE -ne 0 ]; then
        echo "Scraper exited with error (code $EXIT_CODE), restarting in 5s..."
        sleep 5
        #exit 1
    else
        echo "Batch finished, starting next batch..."
        # Optional small sleep to let system breathe
        sleep 1
    fi
done

