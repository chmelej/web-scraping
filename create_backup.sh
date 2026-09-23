tar cfz ../web-scraper-`date +%F`.tgz --exclude='data' --exclude='.venv' --exclude='logs' --exclude='web/node_modules' --exclude='docs/crawlee-python' .
