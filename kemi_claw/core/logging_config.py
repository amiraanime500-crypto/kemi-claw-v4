"""Structured logging for Kemi-Claw."""
import logging
import sys


def setup_logging(level="INFO"):
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, stream=sys.stdout)
    return logging.getLogger("kemi_claw")


log = setup_logging()
