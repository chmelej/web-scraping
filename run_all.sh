#!/bin/bash

echo "Starting all workers..."

./run_scraper.sh &
./run_parser.sh &
./run_detector.sh &
./run_requeue.sh &

echo "All workers are running in background. Press Ctrl+C to stop (though you might need to kill them manually)."
wait
