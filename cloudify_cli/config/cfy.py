########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import sys
import StringIO
import traceback

import click
from click_didyoumean import DYMGroup

from cloudify_rest_client.exceptions import NotModifiedError
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.exceptions import MaintenanceModeActiveError
from cloudify_rest_client.exceptions import MaintenanceModeActivatingError

from .. import env
from .. import logger
from . import helptexts
from .. import constants
from ..logger import get_logger
from ..inputs import inputs_to_dict
from ..constants import DEFAULT_BLUEPRINT_PATH
from ..exceptions import CloudifyBootstrapError
from ..exceptions import SuppressedCloudifyCliError


CLICK_CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help'],
    token_normalize_func=lambda param: param.lower(),
    ignore_unknown_options=True)


class MutuallyExclusiveOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop('mutually_exclusive', []))
        self.mutuality_error_message = \
            kwargs.pop('mutuality_error_message',
                       helptexts.DEFAULT_MUTUALITY_MESSAGE)
        self.mutuality_string = ', '.join(self.mutually_exclusive)
        if self.mutually_exclusive:
            help = kwargs.get('help', '')
            kwargs['help'] = (
                '{0}. This argument is mutually exclusive with '
                'arguments: [{1}] ({2})'.format(
                    help,
                    self.mutuality_string,
                    self.mutuality_error_message))
        super(MutuallyExclusiveOption, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise click.UsageError(
                'Illegal usage: `{0}` is mutually exclusive with '
                'arguments: [{1}] ({2}).'.format(
                    self.name,
                    self.mutuality_string,
                    self.mutuality_error_message))
        return super(MutuallyExclusiveOption, self).handle_parse_result(
            ctx, opts, args)


def _format_version_data(version_data,
                         prefix=None,
                         suffix=None,
                         infix=None):
    all_data = version_data.copy()
    all_data['prefix'] = prefix or ''
    all_data['suffix'] = suffix or ''
    all_data['infix'] = infix or ''
    output = StringIO.StringIO()
    output.write('{prefix}{version}'.format(**all_data))
    output.write('{suffix}'.format(**all_data))
    return output.getvalue()


def show_version(ctx, param, value):
    # The callback in the `main` group is called regardless of whether
    # the --version flag was set or not so we need to return to main
    # in case it wasn't called.
    if not value or ctx.resilient_parsing:
        return

    cli_version_data = env.get_version_data()
    rest_version_data = env.get_manager_version_data()

    cli_version = _format_version_data(
        cli_version_data,
        prefix='Cloudify CLI ',
        infix=' ' * 5,
        suffix='\n')
    rest_version = ''
    if rest_version_data:
        rest_version = _format_version_data(
            rest_version_data,
            prefix='Cloudify Manager ',
            infix=' ',
            suffix=' [ip={ip}]\n'.format(**rest_version_data))
    click.echo('{0}{1}'.format(cli_version, rest_version))
    ctx.exit()


def inputs_callback(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return

    return inputs_to_dict(value)


def set_verbosity_level(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return

    logger.set_global_verbosity_level(value)


def set_cli_except_hook(global_verbosity_level):

    def recommend(possible_solutions):
        logger = get_logger()

        logger.info('Possible solutions:')
        for solution in possible_solutions:
            logger.info('  - {0}'.format(solution))

    def new_excepthook(tpe, value, tb):
        logger = get_logger()

        prefix = None
        server_traceback = None
        output_message = True
        if issubclass(tpe, CloudifyClientError):
            server_traceback = value.server_traceback
            if not issubclass(
                    tpe,
                    (MaintenanceModeActiveError,
                     MaintenanceModeActivatingError,
                     NotModifiedError)):
                # this means we made a server call and it failed.
                # we should include this information in the error
                prefix = 'An error occurred on the server'
        if issubclass(tpe, SuppressedCloudifyCliError):
            output_message = False
        if issubclass(tpe, CloudifyBootstrapError):
            output_message = False
        if global_verbosity_level:
            # print traceback if verbose
            s_traceback = StringIO.StringIO()
            traceback.print_exception(
                etype=tpe,
                value=value,
                tb=tb,
                file=s_traceback)
            logger.error(s_traceback.getvalue())
            if server_traceback:
                logger.error('Server Traceback (most recent call last):')

                # No need for print_tb since this exception
                # is already formatted by the server
                logger.error(server_traceback)
        if output_message and not global_verbosity_level:

            # If we output the traceback
            # we output the message too.
            # print_exception does that.
            # here we just want the message (non verbose)
            if prefix:
                logger.error('{0}: {1}'.format(prefix, value))
            else:
                logger.error(value)
        if hasattr(value, 'possible_solutions'):
            recommend(getattr(value, 'possible_solutions'))

    sys.excepthook = new_excepthook


def group(name):
    return click.group(
        name=name,
        context_settings=CLICK_CONTEXT_SETTINGS,
        cls=DYMGroup)


def command(name):
    return click.command(name=name)


def assert_manager_active(func):
    """Decorator that asserts that a manager is active
    """
    def wrapper(*args, **kwargs):
        env.assert_manager_active()
        return func(*args, **kwargs)

    return wrapper


def assert_local_active(func):
    """Decorator that asserts that a local profile is active
    """
    def wrapper(*args, **kwargs):
        env.assert_local_active()
        return func(*args, **kwargs)

    return wrapper


def add_logger(func):
    def wrapper(*args, **kwargs):
        new_logger = get_logger()
        return func(logger=new_logger, *args, **kwargs)

    return wrapper


def add_client(*args, **kwargs):
    def add_client_inner(func):
        def wrapper(*wrapper_args, **wrapper_kwargs):
            client = env.get_rest_client(*args, **kwargs)
            return func(client=client, *wrapper_args, **wrapper_kwargs)

        return wrapper

    return add_client_inner


def argument(name, type=click.STRING, required=True):
    return click.argument(name, required=required, type=type)


class Options(object):
    def __init__(self):

        # TODO: Convert verbose to a function which allows to pass
        # whether the value is exposed or not as an argument.
        # Then, remove `verbose_exposed`.
        self.verbose = click.option(
            '-v',
            '--verbose',
            count=True,
            callback=set_verbosity_level,
            expose_value=False,
            is_eager=True,
            help=helptexts.VERBOSE)

        self.verbose_exposed = click.option(
            '-v',
            '--verbose',
            count=True,
            callback=set_verbosity_level,
            is_eager=True,
            help=helptexts.VERBOSE)

        self.version = click.option(
            '--version',
            is_flag=True,
            callback=show_version,
            expose_value=False,
            is_eager=True,
            help=helptexts.VERSION)

        self.inputs = click.option(
            '-i',
            '--inputs',
            multiple=True,
            callback=inputs_callback,
            help=helptexts.INPUTS)

        self.parameters = click.option(
            '-p',
            '--parameters',
            multiple=True,
            callback=inputs_callback,
            help=helptexts.PARAMETERS)

        self.output_path = click.option(
            '-o',
            '--output-path',
            help=helptexts.OUTPUT_PATH)

        self.optional_output_path = click.option(
            '-o',
            '--output-path',
            help=helptexts.OUTPUT_PATH)

        self.include_keys = click.option(
            '--include-keys',
            is_flag=True,
            help=helptexts.INCLUDE_SSH_KEYS)

        self.allow_custom_parameters = click.option(
            '--allow-custom-parameters',
            is_flag=True,
            help=helptexts.ALLOW_CUSTOM_PARAMETERS)

        self.install_plugins = click.option(
            '--install-plugins',
            is_flag=True,
            help=helptexts.INSTALL_PLUGINS)

        self.include_logs = click.option(
            '--include-logs/--no-logs',
            default=True,
            help=helptexts.INCLUDE_LOGS)

        self.json = click.option(
            '--json',
            is_flag=True,
            help=helptexts.JSON_OUTPUT)

        self.tail = click.option(
            '--tail',
            is_flag=True,
            help=helptexts.TAIL_OUTPUT)

        self.validate_only = click.option(
            '--validate-only',
            is_flag=True,
            help=helptexts.VALIDATE_ONLY)

        self.skip_validations = click.option(
            '--skip-validations',
            is_flag=True,
            help=helptexts.SKIP_BOOTSTRAP_VALIDATIONS)

        self.skip_sanity = click.option(
            '--skip-sanity',
            is_flag=True,
            default=False,
            help=helptexts.SKIP_BOOTSTRAP_SANITY)

        self.keep_up_on_failure = click.option(
            '--keep-up-on-failure',
            is_flag=True,
            help=helptexts.KEEP_UP_ON_FAILURE)

        self.validate = click.option(
            '--validate',
            is_flag=True,
            help=helptexts.VALIDATE_BLUEPRINT)

        self.skip_install = click.option(
            '--skip-install',
            is_flag=True,
            help=helptexts.SKIP_INSTALL)

        self.skip_uninstall = click.option(
            '--skip-uninstall',
            is_flag=True,
            help=helptexts.SKIP_UNINSTALL)

        self.backup_first = click.option(
            '--backup-first',
            is_flag=True,
            help=helptexts.BACKUP_LOGS_FIRST)

        self.management_ip = click.option(
            '-t',
            '--management-ip',
            required=False,
            help=helptexts.MANAGEMENT_IP)

        self.management_user = click.option(
            '-u',
            '--management-user',
            required=False,
            help=helptexts.MANAGEMENT_USER)

        self.management_key = click.option(
            '-k',
            '--management-key',
            required=False,
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['management_password'],
            mutuality_error_message=helptexts.MUTUAL_SSH_KEY_AND_PASSWORD,
            help=helptexts.MANAGEMENT_KEY)

        self.management_password = click.option(
            '-p',
            '--management-password',
            required=False,
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['management_key'],
            mutuality_error_message=helptexts.MUTUAL_SSH_KEY_AND_PASSWORD,
            help=helptexts.MANAGEMENT_PASSWORD)

        self.management_port = click.option(
            '--management-port',
            required=False,
            default=constants.REMOTE_EXECUTION_PORT,
            help=helptexts.MANAGEMENT_PORT)

        self.rest_port = click.option(
            '--rest-port',
            required=False,
            default=constants.DEFAULT_REST_PORT,
            help=helptexts.REST_PORT)

        self.init_hard_reset = click.option(
            '--hard',
            is_flag=True,
            help=helptexts.HARD_RESET)

        self.reset_context = click.option(
            '-r',
            '--reset-context',
            # TODO: Change name. This is not true. It only resets the context
            is_flag=True,
            help=helptexts.RESET_CONTEXT)

        self.wait = click.option(
            '--wait',
            is_flag=True,
            help=helptexts.MAINTENANCE_MODE_WAIT)

        self.node_name = click.option(
            '-n',
            '--node-name',
            required=False,
            help=helptexts.NODE_NAME)

        self.snapshot_id = click.option(
            '-s',
            '--snapshot-id',
            help=helptexts.SNAPSHOT_ID)

        self.without_deployment_envs = click.option(
            '--without-deployment-envs',
            is_flag=True,
            help=helptexts.RESTORE_SNAPSHOT_EXCLUDE_EXISTING_DEPLOYMENTS)

        self.include_metrics = click.option(
            '--include-metrics',
            is_flag=True,
            help=helptexts.INCLUDE_METRICS_IN_SNAPSHOT)

        self.exclude_credentials = click.option(
            '--exclude-credentials',
            is_flag=True,
            help=helptexts.EXCLUDE_CREDENTIALS_IN_SNAPSHOT)

        self.ssh_command = click.option(
            '-c',
            '--command',
            help=helptexts.SSH_COMMAND)

        self.host_session = click.option(
            '--host',
            is_flag=True,
            help=helptexts.SSH_HOST_SESSION)

        self.session_id = click.option(
            '--sid',
            help=helptexts.SSH_CONNECT_TO_SESSION)

        self.list_sessions = click.option(
            '-l',
            '--list-sessions',
            is_flag=True,
            help=helptexts.SSH_LIST_SESSIONS)

        self.ignore_deployments = click.option(
            '--ignore-deployments',
            is_flag=True,
            help=helptexts.IGNORE_DEPLOYMENTS)

        self.include_system_workflows = click.option(
            '--include-system-workflows',
            required=False,
            is_flag=True,
            help=helptexts.INCLUDE_SYSTEM_WORKFLOWS)

        self.profile_alias = click.option(
            '--alias',
            help=helptexts.PROFILE_ALIAS)

        self.descending = click.option(
            '--descending',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.DESCENDING)

    @staticmethod
    def force(help):
        return click.option(
            '-f',
            '--force',
            is_flag=True,
            help=help)

    @staticmethod
    def blueprint_filename():
        return click.option(
            '-n',
            '--blueprint-filename',
            default=DEFAULT_BLUEPRINT_PATH,
            help=helptexts.BLUEPRINT_FILENAME)

    @staticmethod
    def workflow_id(default):
        return click.option(
            '-w',
            '--workflow-id',
            default=default,
            help=helptexts.WORKFLOW_TO_EXECUTE.format(default))

    @staticmethod
    def task_thread_pool_size(default=1):
        return click.option(
            '--task-thread-pool-size',
            type=int,
            default=default,
            help=helptexts.TASK_THREAD_POOL_SIZE.format(default))

    @staticmethod
    def task_retries(default=0):
        return click.option(
            '--task-retries',
            type=int,
            default=default,
            help=helptexts.TASK_RETRIES.format(default))

    @staticmethod
    def sort_by(default='created_at'):
        return click.option(
            '--sort-by',
            required=False,
            default=default,
            help=helptexts.SORT_BY)

    @staticmethod
    def task_retry_interval(default=1):
        return click.option(
            '--task-retry-interval',
            type=int,
            default=default,
            help=helptexts.TASK_RETRIES.format(default))

    @staticmethod
    def timeout(default=900):
        return click.option(
            '--timeout',
            type=int,
            default=default,
            help=helptexts.OPERATION_TIMEOUT)

    @staticmethod
    def deployment_id(required=False):
        return click.option(
            '-d',
            '--deployment-id',
            required=required,
            help=helptexts.DEPLOYMENT_ID)

    @staticmethod
    def blueprint_id(required=False):
        return click.option(
            '-b',
            '--blueprint-id',
            required=required,
            help=helptexts.BLUEPRINT_ID)

    @staticmethod
    def blueprint_path(required=False):
        return click.option(
            '-p',
            '--blueprint-path',
            required=required,
            type=click.Path(exists=True))


options = Options()
