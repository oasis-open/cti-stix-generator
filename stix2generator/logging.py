import logging
import logging.config


# custom more-verbose-than-debug level, for extra verbosity.
EXTRA_VERBOSE = 5


def _detect_top_level_module_name():
    """
    Simple function to try to auto-detect the top-level module name, based
    on the name of this module.  This can be used to name a logger.  Hopefully
    this makes it adapt to module refactoring; we don't have to hard-code
    anything.  I anticipate that all logging in this library will be done via
    loggers named after the module hierarchy, so we can affect all of them
    as a group this way.

    :return: The top level module name
    """
    dot_idx = __name__.find(".")

    if dot_idx == -1:
        top_level_module = __name__
    else:
        top_level_module = __name__[:dot_idx]

    return top_level_module


def config_logging(verbosity_count):
    """
    Configure logging for commandline scripts.  Library code should not
    configure logging.

    :param verbosity_count: The count of "-v"s on the commandline, or None
    """

    if verbosity_count is None or verbosity_count == 0:
        log_level = logging.INFO
    elif verbosity_count == 1:
        log_level = logging.DEBUG
    else:
        log_level = EXTRA_VERBOSE

    config = {
        "version": 1,

        "formatters": {
            "message_only": {
                "format": "%(message)s"
            }
        },

        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "message_only"
            }
        },

        "disable_existing_loggers": False
    }

    logger_config = {
        "level": log_level,
        "handlers": ["console"]
    }

    # In addition to changing the log level, if extra verbosity is
    # selected, configure the root handler so that all libs will show
    # logging.  Otherwise, just configure a logger for this library.
    if log_level == EXTRA_VERBOSE:
        config["root"] = logger_config

    else:
        top_level_module = _detect_top_level_module_name()
        config["loggers"] = {
            top_level_module: logger_config
        }

    logging.config.dictConfig(config)
