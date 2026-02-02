find logs -type f -name *log -exec uv run scripts/update_errors_from_log.py {} \;
