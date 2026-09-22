"""Centralized logging system for JARVIS."""
import logging
import logging.handlers
import sys
from pathlib import Path

# In a frozen PyInstaller onedir build, __file__ resolves inside _internal/
# (one level below the exe), so Path(__file__).parent.parent would land on
# _internal itself instead of the exe's own directory — writing per-module
# logs into a folder build.bat never creates or cleans, invisible next to
# Jarvis.exe, and (as observed) still open/locked when build_installer.bat
# tries to compress that same _internal tree right after a test run.
if getattr(sys, 'frozen', False):
    _LOGS_DIR = Path(sys.executable).parent / 'logs'
else:
    _LOGS_DIR = Path(__file__).parent.parent / 'logs'
_LOGS_DIR.mkdir(exist_ok=True)

# Configure logging levels
_LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}

class _ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return super().format(record)

def setup_logger(name: str, log_file: str = None, level: str = 'INFO') -> logging.Logger:
    """
    Setup a logger with both file and console handlers.

    Args:
        name: Logger name (usually __name__)
        log_file: Log file name (default: {name}.log)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(_LOG_LEVELS.get(level, logging.INFO))

    # File handler with rotation
    if log_file is None:
        log_file = f"{name.split('.')[-1]}.log"

    log_path = _LOGS_DIR / log_file
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '[%(asctime)s] %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console handler (optional, only for important messages)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_formatter = _ColoredFormatter(
        '%(levelname)s: %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger

def get_logger(name: str) -> logging.Logger:
    """Get or create a logger for a specific module."""
    return setup_logger(name)
