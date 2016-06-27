import click

from . import helptexts
from .. import constants
# from .. import logger

# TODO: should all decorators be functions?


# verbose = click.option(
#     '-v',
#     '--verbose',
#     is_flag=True,
#     callback=logger.set_global_verbosity_level,
#     help=helptexts.)
inputs = click.option(
    '-i',
    '--inputs',
    multiple=True,
    help=helptexts.INPUTS)
parameters = click.option(
    '-p',
    '--parameters',
    multiple=True,
    help=helptexts.PARAMETERS)
output_path = click.option(
    '-o',
    '--output-path',
    help=helptexts.OUTPUT_PATH)

allow_custom_parameters = click.option(
    '--allow-custom-parameters',
    is_flag=True,
    help=helptexts.ALLOW_CUSTOM_PARAMETERS)
install_plugins = click.option(
    '--install-plugins',
    is_flag=True,
    help=helptexts.INSTALL_PLUGINS)
include_logs = click.option(
    '-l',
    '--include-logs',
    is_flag=True,
    help=helptexts.INCLUDE_LOGS)
json = click.option(
    '--json',
    is_flag=True,
    help=helptexts.JSON_OUTPUT)


validate_only = click.option(
    '--validate-only',
    is_flag=True,
    help=helptexts.VALIDATE_ONLY)
skip_validations = click.option(
    '--skip-validations',
    is_flag=True,
    help=helptexts.SKIP_BOOTSTRAP_VALIDATIONS)


def force(help, required=False):
    return click.option(
        '-f',
        '--force',
        required=required,
        is_flag=True,
        help=help)


def blueprint_filename(default=constants.DEFAULT_BLUEPRINT_FILE_NAME):
    return click.option(
        '-n',
        '--blueprint-filename',
        default=default,
        help=helptexts.BLUEPRINT_FILENAME.format(default))


def workflow_id(default):
    return click.option(
        '-w',
        '--workflow-id',
        default=default,
        help=helptexts.WORKFLOW_TO_EXECUTE.format(default))


def task_thread_pool_size(default=1):
    return click.option(
        '--task-thread-pool-size',
        type=int,
        default=default,
        help=helptexts.TASK_THREAD_POOL_SIZE.format(default))


def task_retries(default=0):
    return click.option(
        '--task-retries',
        type=int,
        default=default,
        help=helptexts.TASK_RETRIES.format(default))


def task_retry_interval(default=1):
    return click.option(
        '--task-retry-interval',
        type=int,
        default=default,
        help=helptexts.TASK_RETRIES.format(default))


def timeout(default=900):
    return click.option(
        '--timeout',
        type=int,
        default=default,
        help=helptexts.OPERATION_TIMEOUT)


def deployment_id(required=False):
    return click.option(
        '-d',
        '--deployment-id',
        required=required,
        help=helptexts.DEPLOYMENT_ID)
