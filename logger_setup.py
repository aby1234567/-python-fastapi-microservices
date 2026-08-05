import logging
from logging.handlers import RotatingFileHandler


class LevelRangeFilter(logging.Filter):
    """Filter that only allows log records within a level range."""
    def __init__(self, min_level, max_level):
        super().__init__()
        self.min_level = min_level
        self.max_level = max_level

    def filter(self, record):
        return self.min_level <= record.levelno <= self.max_level


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Let all levels through


# --- Handlers ---
debug_handler = RotatingFileHandler(
    'logs/debug.log', maxBytes=1 * 1024 * 1024, backupCount=5
)
info_handler = RotatingFileHandler(
    'logs/info.log', maxBytes=1 * 1024 * 1024, backupCount=5
)
warning_handler = RotatingFileHandler(
    'logs/warning.log', maxBytes=1 * 1024 * 1024, backupCount=5
)
error_handler = RotatingFileHandler(
    'logs/error.log', maxBytes=1 * 1024 * 1024, backupCount=5
)
critical_handler = RotatingFileHandler(
    'logs/critical.log', maxBytes=1 * 1024 * 1024, backupCount=5
)

# All handlers set to DEBUG; filters enforce exclusivity
for h in (debug_handler, info_handler, warning_handler, error_handler, critical_handler):
    h.setLevel(logging.DEBUG)

# --- Filters (exclusive per level) ---
debug_handler.addFilter(LevelRangeFilter(logging.DEBUG, logging.DEBUG))
info_handler.addFilter(LevelRangeFilter(logging.INFO, logging.INFO))
warning_handler.addFilter(LevelRangeFilter(logging.WARNING, logging.WARNING))
error_handler.addFilter(LevelRangeFilter(logging.ERROR, logging.ERROR))
critical_handler.addFilter(LevelRangeFilter(logging.CRITICAL, logging.CRITICAL))

# --- Formatter ---
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
for h in (debug_handler, info_handler, warning_handler, error_handler, critical_handler):
    h.setFormatter(formatter)

# --- Add handlers ---
logger.addHandler(debug_handler)
logger.addHandler(info_handler)
logger.addHandler(warning_handler)
logger.addHandler(error_handler)
logger.addHandler(critical_handler)
