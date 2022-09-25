import logging

_logger = logging.getLogger("compiler")


def debug(*args, **kwargs):
    _logger.debug(*args, **kwargs)


def info(*args, **kwargs):
    _logger.info(*args, **kwargs)


def warning(*args, **kwargs):
    _logger.warning(*args, **kwargs)


def error(*args, **kwargs):
    _logger.error(*args, **kwargs)


def exception(*args, **kwargs):
    _logger.exception(*args, **kwargs)
