import logging
import sys
import os
from config.settings import LOG_LEVEL, LOG_DIR

def setup_logging(name, log_file=None):
    """Setup logging pro workers"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # Check if handlers already exist to avoid duplicates
    if logger.handlers:
        return logger

    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler (optional)
    if log_file:
        # Ensure log directory exists
        log_path = os.path.join(LOG_DIR, log_file)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
