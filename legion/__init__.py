import logging.config

logging.config.dictConfig(
    {
        "version": 1,
        "formatters": {
            "console": {
                "class": "logging.Formatter",
                "format": (
                    'time="%(asctime)s" '
                    'level="%(levelname)s" '
                    'package="%(name)s" '
                    'process="%(processName)s" '
                    'message="%(message)s"'
                ),
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "console",
            }
        },
        "loggers": {
            "salt": {"handlers": ["console"], "propagate": True},
            "legion": {"handlers": ["console"], "propagate": True},
        },
    }
)
