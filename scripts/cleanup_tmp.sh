#!/bin/bash
# Script to clean up temporary files created by Playwright/Crawlee
# Run this periodically or when disk space is low.

echo "Cleaning up temporary Playwright/Crawlee files in /tmp..."

# Find and delete directories matching the pattern
# Warns before deletion
count=$(find /tmp -maxdepth 1 -name "apify-playwright-*" -type d | wc -l)

if [ "$count" -eq 0 ]; then
    echo "No matching temporary files found."
    exit 0
fi

echo "Found $count directories."
read -p "Do you want to delete them? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    find /tmp -maxdepth 1 -name "apify-playwright-*" -type d -exec rm -rf {} +
    echo "Cleanup complete."
else
    echo "Operation cancelled."
fi
