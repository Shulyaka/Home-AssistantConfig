"""Log Level."""

import logging
import logging.handlers

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "log_level"

LOGSEVERITY_NOTSET = "NOTSET"
LOGSEVERITY_DEBUG = "DEBUG"
LOGSEVERITY_INFO = "INFO"
LOGSEVERITY_WARNING = "WARNING"
LOGSEVERITY_ERROR = "ERROR"
LOGSEVERITY_CRITICAL = "CRITICAL"
LOGSEVERITY_WARN = "WARN"
LOGSEVERITY_FATAL = "FATAL"

LOGSEVERITY = {
    LOGSEVERITY_CRITICAL: logging.CRITICAL,
    LOGSEVERITY_FATAL: logging.FATAL,
    LOGSEVERITY_ERROR: logging.ERROR,
    LOGSEVERITY_WARNING: logging.WARNING,
    LOGSEVERITY_WARN: logging.WARNING,
    LOGSEVERITY_INFO: logging.INFO,
    LOGSEVERITY_DEBUG: logging.DEBUG,
    LOGSEVERITY_NOTSET: logging.NOTSET,
}

_VALID_LOG_LEVEL = vol.All(vol.Upper, vol.In(LOGSEVERITY), LOGSEVERITY.__getitem__)

FILE_LOG_LEVEL = "file_log_level"
CONSOLE_LOG_LEVEL = "console_log_level"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(FILE_LOG_LEVEL): _VALID_LOG_LEVEL,
                vol.Optional(CONSOLE_LOG_LEVEL): _VALID_LOG_LEVEL,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# Example configuration:
# log_level:
#   file_log_level: debug
#   console_log_level: info
#
# This will set the log level for file handlers to DEBUG and for console handlers to INFO.
# Setting the log level to 'notset' (default) will not change the existing log level of handlers,
# though they are already set to NOTSET by default at HA startup.
# The log_level component does not change the log level of the root logger, which is controlled by the `logger` component.

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the LLM Tools API with the HTTP interface."""
    file_log_level: logging.Level = config.get(DOMAIN, {}).get(
        FILE_LOG_LEVEL, logging.NOTSET
    )
    console_log_level: logging.Level = config.get(DOMAIN, {}).get(
        CONSOLE_LOG_LEVEL, logging.NOTSET
    )

    queue_handlers: list[logging.handlers.QueueHandler] = []
    console_handlers: list[logging.StreamHandler] = []
    file_handlers: list[logging.FileHandler] = []

    for handler in logging.root.handlers:
        if isinstance(handler, logging.FileHandler):
            file_handlers.append(handler)
        elif isinstance(handler, logging.StreamHandler):
            console_handlers.append(handler)
        elif isinstance(handler, logging.handlers.QueueHandler):
            queue_handlers.append(handler)
    for queue_handler in queue_handlers:
        if queue_handler.listener is not None:
            for handler in queue_handler.listener.handlers:
                if isinstance(handler, logging.FileHandler):
                    file_handlers.append(handler)
                    if file_log_level != logging.NOTSET:
                        queue_handler.listener.respect_handler_level = True
                elif isinstance(handler, logging.StreamHandler):
                    console_handlers.append(handler)
                    if console_log_level != logging.NOTSET:
                        queue_handler.listener.respect_handler_level = True

    _LOGGER.debug("Console handlers: %s", console_handlers)
    _LOGGER.debug("File handlers: %s", file_handlers)

    if console_log_level != logging.NOTSET:
        for handler in console_handlers:
            if handler.level == logging.NOTSET:
                handler.setLevel(console_log_level)
                _LOGGER.debug(
                    "Setting console handler level to %s for %s",
                    console_log_level,
                    handler,
                )

    if file_log_level != logging.NOTSET:
        for handler in file_handlers:
            if handler.level == logging.NOTSET:
                handler.setLevel(file_log_level)
                _LOGGER.debug(
                    "Setting file handler level to %s for %s",
                    file_log_level,
                    handler,
                )

    return True
