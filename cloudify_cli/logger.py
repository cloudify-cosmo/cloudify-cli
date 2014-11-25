########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

import json
import logging
import logging.config
import os
import yaml
import copy

from cloudify.logs import create_event_message_prefix

from cloudify_cli.config import logger_config


_lgr = None

_all_loggers = set()


def get_logger():
    return _lgr


def all_loggers():
    return _all_loggers


def configure_loggers():

    # first off, configure defaults
    # to enable the use of the logger
    # even before the init was executed.
    _configure_defaults()

    from cloudify_cli import utils
    if utils.is_initialized():
        # init was already called
        # use the configuration file.
        _configure_from_file()

    global _lgr
    _lgr = logging.getLogger('cloudify.cli.main')


def _configure_defaults():

    # add handlers to the main logger
    logger_dict = copy.deepcopy(logger_config.LOGGER)
    logger_dict['loggers'] = {
        'cloudify.cli.main': {
            'handlers': list(logger_dict['handlers'].keys())
        }
    }
    from cloudify_cli import utils
    logger_dict['handlers']['file']['filename'] = utils.DEFAULT_LOG_FILE
    logfile_dir = os.path.dirname(utils.DEFAULT_LOG_FILE)
    if not os.path.exists(logfile_dir):
        os.makedirs(logfile_dir)

    logging.config.dictConfig(logger_dict)
    logging.getLogger('cloudify.cli.main').setLevel(logging.INFO)
    _all_loggers.add('cloudify.cli.main')


def _configure_from_file():

    from cloudify_cli import utils
    config_path = utils.get_configuration_path()
    logging_config = yaml.safe_load(file(config_path, 'r'))['logging']
    loggers_config = logging_config['loggers']
    logfile = logging_config['filename']

    # set filename on file handler
    logger_dict = copy.deepcopy(logger_config.LOGGER)
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


def get_events_logger():

    def verbose_events_logger(events):

        """
        The verbose events logger prints the entire event as json.
        :param events: The events to print.
        :return:
        """
        for event in events:
            _lgr.info(json.dumps(event, indent=4))

    def default_events_logger(events):

        """
        The default events logger prints events as short messages.
        :param events: The events to print.
        :return:
        """
        for event in events:
            _lgr.info(create_event_message_prefix(event))

    # currently needs to be imported dynamically since
    # otherwise it creates a circular import.
    from cloudify_cli.cli import verbose_output

    if verbose_output:
        return verbose_events_logger
    else:
        return default_events_logger
