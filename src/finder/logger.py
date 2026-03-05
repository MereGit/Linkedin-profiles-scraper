import logging

def setup_logger(level=logging.INFO):
    logger = logging.getLogger("finder")
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter(
            "[%(asctime)s] %(levelname)s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger
