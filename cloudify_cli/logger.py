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

import colorama

from cloudify import logs

from . import env
from .config.config import is_use_colors
from .config.config import CloudifyConfig
from .colorful_event import ColorfulEvent

DEFAULT_LOG_FILE = os.path.join(env.CLOUDIFY_WORKDIR, 'logs', 'cli.log')

HIGH_VERBOSE = 3
MEDIUM_VERBOSE = 2
LOW_VERBOSE = 1
NO_VERBOSE = 0
QUIET = -1

verbosity_level = NO_VERBOSE
json_output = False

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
            "maxBytes": "5000000",
            "backupCount": "20"
        },
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "console"
        }
    },
    "loggers": {
        "cloudify.cli.main": {
            "handlers": ["console", "file"]
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
    _configure_defaults()

    if env.is_initialized():
        # init was already called
        # use the configuration file.
        _configure_from_file()

    global _lgr
    _lgr = logging.getLogger('cloudify.cli.main')

    # configuring events/logs loggers
    # (this will also affect local workflow loggers, which don't use
    # the get_events_logger method of this module)
    if is_use_colors():
        logs.EVENT_CLASS = ColorfulEvent
        # refactor this elsewhere if colorama is further used in CLI
        colorama.init(autoreset=True)


def _configure_defaults():
    if get_global_json_output():
        LOGGER['loggers']["logfile"] = {
            "level": "DEBUG",
            "propagate": False,
            "handlers": ["file"]
        }
        LOGGER['handlers']['console']['stream'] = 'ext://sys.stderr'
    # add handlers to the main logger
    logger_dict = copy.deepcopy(LOGGER)
    logger_dict['handlers']['file']['filename'] = DEFAULT_LOG_FILE
    logfile_dir = os.path.dirname(DEFAULT_LOG_FILE)
    if not os.path.exists(logfile_dir):
        os.makedirs(logfile_dir)

    logging.config.dictConfig(logger_dict)
    if verbosity_level >= HIGH_VERBOSE:
        level = logging.DEBUG
    elif verbosity_level <= QUIET:
        level = logging.CRITICAL
    else:
        level = logging.INFO
    logging.getLogger('cloudify.cli.main').setLevel(level)


def _configure_from_file():

    config = CloudifyConfig()
    logging_config = config.logging
    loggers_config = logging_config.loggers
    logfile = logging_config.filename

    # set filename on file handler
    logger_dict = copy.deepcopy(LOGGER)
    logger_dict['handlers']['file']['filename'] = logfile
    logfile_dir = os.path.dirname(logfile)
    if not os.path.exists(logfile_dir):
        os.makedirs(logfile_dir)

    # add handlers to every logger specified in the file
    for logger_name, logging_level in loggers_config.items():
        if verbosity_level >= HIGH_VERBOSE:
            level = logging.DEBUG
        elif verbosity_level <= QUIET:
            level = logging.CRITICAL
        elif isinstance(logging_level, basestring):
            level = logging._levelNames[logging_level.upper()]
        else:
            level = logging.INFO

        logger_dict['loggers'][logger_name] = {
            'handlers': list(logger_dict['handlers'].keys()),
            'level': level
        }

    logging.config.dictConfig(logger_dict)


def get_events_logger(json_output):
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
            output = logs.create_event_message_prefix(event)
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


def output(line):
    logfile_logger.info(line)
    click.echo(line)


class CloudifyJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return obj.hex
        return super(CloudifyJSONEncoder, self).default(obj)
