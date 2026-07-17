# run_scraper.sh po sobe nechava hodne logu. v logu jsou zajimave informace o
# chybach, takze tento skript je projde a prida do databaze. je to naivni
# prepisuje se posledni hodnota.

find logs -type f -name *log -exec uv run scripts/update_errors_from_log.py {} \;
