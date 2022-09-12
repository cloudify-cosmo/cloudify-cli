########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############


import os
import copy
import json
import uuid
import click
import logging
import logging.config
from datetime import datetime
from contextlib import contextmanager

import colorama

from cloudify import logs

from cloudify_cli import env
from cloudify_cli.config.config import CloudifyConfig, is_use_colors
from cloudify_cli.colorful_event import ColorfulEvent, ColorfulGroupEvent

DEFAULT_LOG_FILE = os.path.join(env.CLOUDIFY_WORKDIR, 'logs', 'cli.log')

HIGH_VERBOSE = 3
MEDIUM_VERBOSE = 2
LOW_VERBOSE = 1
NO_VERBOSE = 0
QUIET = -1

verbosity_level = NO_VERBOSE
json_output = False
extended_view = False

_lgr = None


LOGGER = {
    "version": 1,
    "formatters": {
        "file": {
            "format": "%(asctime)s [%(levelname)s] %(message)s"
        },
        "console": {
            "format": "%(message)s"
        }
    },
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "file",
            "maxBytes": 5000000,
            "backupCount": 20
        },
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "console"
        }
    },
    "loggers": {
        "cloudify.cli.main": {
            "handlers": ["console", "file"],
            "level": "INFO"
        }
    }
}
# logger that goes only to the file, for use when logging table data
logfile_logger = logging.getLogger('logfile')


def get_logger():
    if not _lgr:
        configure_loggers()
    return _lgr


def configure_loggers():
    # first off, configure defaults
    # to enable the use of the logger
    # even before the init was executed.
    logger_config = copy.deepcopy(LOGGER)
    _configure_defaults(logger_config)

    if env.is_initialized():
        # init was already called
        # use the configuration file.
        _configure_from_file(logger_config)
    _set_loggers_verbosity(logger_config)
    logging.config.dictConfig(logger_config)

    global _lgr
    _lgr = logging.getLogger('cloudify.cli.main')

    # configuring events/logs loggers
    # (this will also affect local workflow loggers, which don't use
    # the get_events_logger method of this module)
    if is_use_colors():
        logs.EVENT_CLASS = ColorfulEvent
        # refactor this elsewhere if colorama is further used in CLI
        colorama.init(autoreset=True)


def _set_loggers_verbosity(logger_config):
    if get_global_json_output():
        logger_config['loggers']['cloudify.cli.main']['level'] = 'ERROR'
    for logger in logger_config['loggers'].values():
        if verbosity_level >= HIGH_VERBOSE:
            logger['level'] = logging.DEBUG
        elif verbosity_level == LOW_VERBOSE:
            logger['level'] = logging.INFO
        elif verbosity_level <= QUIET:
            logger['level'] = logging.ERROR


def _configure_defaults(logger_config):
    if get_global_json_output():
        logger_config['loggers']['logfile'] = {
            "level": "DEBUG",
            "propagate": False,
            "handlers": ["file"]
        }
        logger_config['handlers']['console']['stream'] = 'ext://sys.stderr'

    logger_config['handlers']['file']['filename'] = DEFAULT_LOG_FILE
    logfile_dir = os.path.dirname(DEFAULT_LOG_FILE)
    if not os.path.exists(logfile_dir):
        os.makedirs(logfile_dir, mode=0o700)


def _configure_from_file(loggers_config):
    config = CloudifyConfig()

    # set filename on file handler
    logger_dict = copy.deepcopy(LOGGER)
    loggers_config['handlers']['file']['filename'] = config.logging.filename
    logfile_dir = os.path.dirname(config.logging.filename)
    if not os.path.exists(logfile_dir):
        os.makedirs(logfile_dir, mode=0o700)

    # add handlers to every logger specified in the file
    for logger_name, logging_level in config.logging.loggers.items():
        loggers_config['loggers'][logger_name] = {
            'handlers': list(logger_dict['handlers'].keys()),
            'level': logging_level.upper()
        }


def get_events_logger(json_output=False, with_names=False):
    json_output = json_output or get_global_json_output()

    def json_events_logger(events):
        """The json events logger prints events as consumable JSON formatted
        entries. Each event appears in its own line.

        :param events: The events to print.
        :return:
        """
        for event in events:
            click.echo(json.dumps(event))

    def text_events_logger(events):
        """The default events logger prints events as short messages.

        :param events: The events to print.
        :return:
        """
        for event in events:
            event_class = None
            if event.get('execution_group_id') is not None:
                event_class = ColorfulGroupEvent
            with _nest_event_class(event_class):
                output = logs.create_event_message_prefix(event, with_names)
            if output:
                click.echo(output)

    return json_events_logger if json_output else text_events_logger


def set_global_verbosity_level(verbose):
    """Set the global verbosity level.
    """
    global verbosity_level
    verbosity_level = verbose
    logs.EVENT_VERBOSITY_LEVEL = verbosity_level


def get_global_verbosity():
    """Return the globally set verbosity
    """
    return verbosity_level


def set_global_json_output(enabled=False):
    global json_output
    json_output = enabled


def get_global_json_output():
    return json_output


def set_global_extended_view(enabled=False):
    global extended_view
    extended_view = enabled


def get_global_extended_view():
    return extended_view


def output(line):
    logfile_logger.info(line)
    click.echo(line)


class CloudifyJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return obj.hex
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super(CloudifyJSONEncoder, self).default(obj)


@contextmanager
def _nest_event_class(event_class):
    prev_event_class = logs.EVENT_CLASS
    if event_class:
        logs.EVENT_CLASS = event_class
    yield
    logs.EVENT_CLASS = prev_event_class
