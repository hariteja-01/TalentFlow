"""Structured logging setup for the pipeline.

Uses Python's standard logging with a consistent format.
Level is configurable via LOG_LEVEL environment variable.
"""

import logging
import os
import sys


def get_logger(name: str) -> logging.Logger:
    """Create a logger with consistent formatting.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers when called multiple times
    if not logger.handlers:
        level = os.environ.get("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, level, logging.INFO))

        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)

    return logger
