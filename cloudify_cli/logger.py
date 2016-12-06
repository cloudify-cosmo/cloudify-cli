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
import sys
import copy
import json
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

verbosity_level = NO_VERBOSE


_lgr = None

_all_loggers = set()


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
    }
}


def get_logger():
    if not _lgr:
        configure_loggers()
    return _lgr


def all_loggers():
    return _all_loggers


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

    # add handlers to the main logger
    logger_dict = copy.deepcopy(LOGGER)
    logger_dict['loggers'] = {
        'cloudify.cli.main': {
            'handlers': list(logger_dict['handlers'].keys())
        }
    }
    logger_dict['handlers']['file']['filename'] = DEFAULT_LOG_FILE
    logfile_dir = os.path.dirname(DEFAULT_LOG_FILE)
    if not os.path.exists(logfile_dir):
        os.makedirs(logfile_dir)

    logging.config.dictConfig(logger_dict)
    logging.getLogger('cloudify.cli.main').setLevel(logging.INFO)
    _all_loggers.add('cloudify.cli.main')


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

    # add handlers to every logger
    # specified in the file
    loggers = {}
    for logger_name in loggers_config:
        loggers[logger_name] = {
            'handlers': list(logger_dict['handlers'].keys())
        }
    logger_dict['loggers'] = loggers

    # set level for each logger
    for logger_name, logging_level in loggers_config.iteritems():
        log = logging.getLogger(logger_name)
        level = logging._levelNames[logging_level.upper()]
        log.setLevel(level)
        _all_loggers.add(logger_name)

    logging.config.dictConfig(logger_dict)


def get_events_logger(json_output):

    def json_events_logger(events):
        """The json events logger prints events as consumable JSON formatted
        entries. Each event appears in its own line.

        :param events: The events to print.
        :return:
        """
        # TODO: Why we're writing directly to stdout here
        # but use the logger when the --json-output flag isn't passed.
        for event in events:
            sys.stdout.write('{}\n'.format(json.dumps(event)))
            sys.stdout.flush()

    def text_events_logger(events):
        """The default events logger prints events as short messages.

        :param events: The events to print.
        :return:
        """
        for event in events:
            output = logs.create_event_message_prefix(event)
            if output:
                _lgr.info(output)

    return json_events_logger if json_output else text_events_logger


def set_global_verbosity_level(verbose):
    """Set the global verbosity level.
    """
    global verbosity_level
    verbosity_level = verbose
    logs.EVENT_VERBOSITY_LEVEL = verbosity_level
    if verbosity_level >= HIGH_VERBOSE:
        for logger_name in all_loggers():
            logging.getLogger(logger_name).setLevel(logging.DEBUG)


def get_global_verbosity():
    """Return the globally set verbosity
    """
    return verbosity_level
