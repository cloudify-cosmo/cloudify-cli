import json
import logging
import logging.config
import os
import sys

from cloudify_cli.config import logger_config


def _init_logger():

    """
    initializes a logger to be used throughout the cli
    can be used by provider codes.

    :rtype: `tupel` with 2 loggers, one for users (writes to console and file),
     and the other for archiving (writes to file only).
    """
    if os.path.isfile(logger_config.LOG_DIR):
        sys.exit('file {0} exists - cloudify log directory cannot be created '
                 'there. please remove the file and try again.'
                 .format(logger_config.LOG_DIR))
    logfile = None
    try:

        # http://stackoverflow.com/questions/8144545/turning-off-logging-in-paramiko
        logging.getLogger('paramiko').setLevel(logging.WARNING)
        logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.ERROR)

        logfile = logger_config.LOGGER['handlers']['file']['filename']
        d = os.path.dirname(logfile)
        if not os.path.exists(d):
            os.makedirs(d)

        logging.config.dictConfig(logger_config.LOGGER)

        logger = logging.getLogger('main')
        logger.setLevel(logging.INFO)
        file_logger = logging.getLogger('file')
        file_logger.setLevel(logging.DEBUG)
        return logger, file_logger
    except ValueError:
        sys.exit('could not initialize logger.'
                 ' verify your logger config'
                 ' and permissions to write to {0}'
                 .format(logfile))


def _create_event_message(event):
    context = event['context']
    deployment_id = context['deployment_id']
    node_info = ''
    operation = ''
    if 'node_id' in context and context['node_id'] is not None:
        node_id = context['node_id']
        if 'operation' in context and context['operation'] is not None:
            operation = '.{0}'.format(context['operation'].split('.')[-1])
        node_info = '[{0}{1}] '.format(node_id, operation)
    level = 'CFY'
    message = event['message']['text'].encode('utf-8')
    if 'cloudify_log' in event['type']:
        level = 'LOG'
        message = '{0}: {1}'.format(event['level'].upper(), message)
    timestamp = event['@timestamp'].split('.')[0]

    return '{0} {1} <{2}> {3}{4}'.format(timestamp,
                                         level,
                                         deployment_id,
                                         node_info,
                                         message)


def get_events_logger():

    def verbose_events_logger(events):

        """
        The verbose events logger prints the entire event as json.
        :param events: The events to print.
        :return:
        """
        for event in events:
            lgr.info(json.dumps(event, indent=4))

    def default_events_logger(events):

        """
        The default events logger prints events as short messages.
        :param events: The events to print.
        :return:
        """
        for event in events:
            lgr.info(_create_event_message(event))

    # Currently needs to be imported dynamically since
    # otherwise it creates a circular import.
    from cloudify_cli.cli import get_global_verbosity
    if get_global_verbosity():
        return verbose_events_logger
    else:
        return default_events_logger

lgr, flgr = _init_logger()
