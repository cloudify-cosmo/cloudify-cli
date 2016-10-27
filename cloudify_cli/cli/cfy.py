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

import sys
import difflib
import StringIO
import traceback
from functools import wraps

import click

from cloudify_rest_client.exceptions import NotModifiedError
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.exceptions import MaintenanceModeActiveError
from cloudify_rest_client.exceptions import MaintenanceModeActivatingError

from .. import env
from .. import constants
from ..cli import helptexts
from ..inputs import inputs_to_dict
from ..constants import DEFAULT_BLUEPRINT_PATH
from ..exceptions import CloudifyBootstrapError
from ..exceptions import SuppressedCloudifyCliError
from ..logger import get_logger, set_global_verbosity_level, DEFAULT_LOG_FILE


CLICK_CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help'],
    token_normalize_func=lambda param: param.lower())


class MutuallyExclusiveOption(click.Option):
    """Makes options mutually exclusive. The option must pass a `cls` argument
    with this class name and a `mutually_exclusive` argument with a list of
    argument names it is mutually exclusive with.

    NOTE: All mutually exclusive options must use this. It's not enough to
    use it in just one of the options.
    """

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
    if not value or ctx.resilient_parsing:
        return

    cli_version_data = env.get_version_data()
    rest_version_data = env.get_manager_version_data() \
        if env.is_manager_active() else None

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

    get_logger().info('{0}{1}'.format(cli_version, rest_version))
    ctx.exit()


def inputs_callback(ctx, param, value):
    """Allows to pass any inputs we provide to a command as
    processed inputs instead of having to call `inputs_to_dict`
    inside the command.

    `@cfy.options.inputs` already calls this callback so that
    every time you use the option it returns the inputs as a
    dictionary.
    """
    if not value or ctx.resilient_parsing:
        return {}

    return inputs_to_dict(value)


def set_verbosity_level(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return

    set_global_verbosity_level(value)


def set_cli_except_hook(global_verbosity_level):

    def recommend(possible_solutions):
        logger = get_logger()

        logger.info('Possible solutions:')
        for solution in possible_solutions:
            logger.info('  - {0}'.format(solution))

    def new_excepthook(tpe, value, tb):
        with open(DEFAULT_LOG_FILE, 'a') as log_file:
            traceback.print_exception(
                etype=tpe,
                value=value,
                tb=tb,
                file=log_file)

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


def assert_manager_active(require_creds=True):
    """Wraps the command so that it can only run when a manager is active
    :param require_creds: If set to True, the wrapped method will fail if no
    admin password was set either in the profile, or in the env variable
    """
    def decorator(func):
        # Wraps here makes sure the original docstring propagates to click
        @wraps(func)
        def wrapper(*args, **kwargs):
            env.assert_manager_active()
            if require_creds:
                env.assert_credentials_set()
            return func(*args, **kwargs)

        return wrapper
    return decorator


def assert_local_active(func):
    """Wraps the command so that it can only run when in local context
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        env.assert_local_active()
        return func(*args, **kwargs)

    return wrapper


def pass_logger(func):
    """Simply passes the logger to a command.
    """
    # Wraps here makes sure the original docstring propagates to click
    @wraps(func)
    def wrapper(*args, **kwargs):
        new_logger = get_logger()
        return func(logger=new_logger, *args, **kwargs)

    return wrapper


def pass_client(*args, **kwargs):
    """Simply passes the rest client to a command.
    """
    def add_client_inner(func):
        # Wraps here makes sure the original docstring propagates to click
        @wraps(func)
        def wrapper(*wrapper_args, **wrapper_kwargs):
            client = env.get_rest_client(*args, **kwargs)
            return func(client=client, *wrapper_args, **wrapper_kwargs)

        return wrapper

    return add_client_inner


def pass_context(func):
    """This exists purely for aesthetic reasons, otherwise
    Some decorators are called `@click.something` instead of
    `@cfy.something`
    """
    return click.pass_context(func)


class AliasedGroup(click.Group):
    def __init__(self, *args, **kwargs):
        self.max_suggestions = kwargs.pop("max_suggestions", 3)
        self.cutoff = kwargs.pop("cutoff", 0.5)
        super(AliasedGroup, self).__init__(*args, **kwargs)

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = \
            [x for x in self.list_commands(ctx) if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: {0}'.format(', '.join(sorted(matches))))

    def resolve_command(self, ctx, args):
        """
        Overrides clicks ``resolve_command`` method
        and appends *Did you mean ...* suggestions
        to the raised exception message.
        """
        try:
            return super(AliasedGroup, self).resolve_command(ctx, args)
        except click.exceptions.UsageError as error:
            error_msg = str(error)
            original_cmd_name = click.utils.make_str(args[0])
            matches = difflib.get_close_matches(
                original_cmd_name,
                self.list_commands(ctx),
                self.max_suggestions,
                self.cutoff)
            if matches:
                error_msg += '\n\nDid you mean one of these?\n    {0}'.format(
                    '\n    '.join(matches))
            raise click.exceptions.UsageError(error_msg, error.ctx)


def group(name):
    """Allows to create a group with a default click context
    and a cls for click's `didyoueamn` without having to repeat
    it for every group.
    """
    return click.group(
        name=name,
        context_settings=CLICK_CONTEXT_SETTINGS,
        cls=AliasedGroup)


def command(*args, **kwargs):
    """This exists purely for aesthetical reasons, otherwise
    Some decorators are called `@click.something` instead of
    `@cfy.something`
    """
    return click.command(*args, **kwargs)


def argument(*args, **kwargs):
    """This exists purely for aesthetic reasons, otherwise
    Some decorators are called `@click.something` instead of
    `@cfy.something`
    """
    return click.argument(*args, **kwargs)


class Options(object):
    def __init__(self):
        """The options api is nicer when you use each option by calling
        `@cfy.options.some_option` instead of `@cfy.some_option`.

        Note that some options are attributes and some are static methods.
        The reason for that is that we want to be explicit regarding how
        a developer sees an option. It it can receive arguments, it's a
        method - if not, it's an attribute.
        """
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

        self.json_output = click.option(
            '--json-output',
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

        self.dont_save_password_in_profile = click.option(
            '--dont-save-password-in-profile',
            is_flag=True,
            default=False,
            help=helptexts.DONT_SAVE_PASSWORD_IN_PROFILE)

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

        self.manager_ip = click.option(
            '-t',
            '--manager-ip',
            required=False,
            help=helptexts.MANAGEMENT_IP)

        self.ssh_user = click.option(
            '-u',
            '--ssh-user',
            required=False,
            help=helptexts.MANAGEMENT_USER)

        self.ssh_key = click.option(
            '-k',
            '--ssh-key',
            required=False,
            cls=MutuallyExclusiveOption,
            help=helptexts.SSH_KEY)

        self.manager_username = click.option(
            '-m',
            '--manager-username',
            required=False,
            help=helptexts.MANAGER_USERNAME)

        self.manager_password = click.option(
            '-p',
            '--manager-password',
            required=False,
            help=helptexts.MANAGER_PASSWORD)

        self.ssh_port = click.option(
            '--ssh-port',
            required=False,
            default=constants.REMOTE_EXECUTION_PORT,
            help=helptexts.SSH_PORT)

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
            is_flag=True,
            help=helptexts.RESET_CONTEXT)

        self.enable_colors = click.option(
            '--enable-colors',
            is_flag=True,
            default=False,
            help=helptexts.ENABLE_COLORS)

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

        self.tenant_name = click.option(
            '-t',
            '--tenant-name',
            required=True,
            help=helptexts.TENANT)

        self.group_name = click.option(
            '-g',
            '--group-name',
            help=helptexts.GROUP)

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

        self.descending = click.option(
            '--descending',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.DESCENDING)

        self.install_script = click.option(
            '-s',
            '--install-script',
            help=helptexts.INSTALL_SCRIPT_LOCATION)

        self.security_role = click.option(
            '-r',
            '--security-role',
            required=False,
            type=click.Choice(['administrator', 'default',
                               'viewer', 'suspended']),
            default='default',
            help=helptexts.SECURITY_ROLE)

        self.password = click.option(
            '-p',
            '--password',
            required=True,
            help=helptexts.PASSWORD)

    @staticmethod
    def include_keys(help):
        return click.option(
            '--include-keys',
            is_flag=True,
            help=help)

    @staticmethod
    def verbose(expose_value=False):
        return click.option(
            '-v',
            '--verbose',
            count=True,
            callback=set_verbosity_level,
            expose_value=expose_value,
            is_eager=True,
            help=helptexts.VERBOSE)

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
    def execution_id(required=False):
        return click.option(
            '-e',
            '--execution-id',
            required=required,
            help=helptexts.EXECUTION_ID)

    @staticmethod
    def blueprint_id(required=False, multiple_blueprints=False):
        def pass_empty_blueprint_id(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                kwargs['blueprint_id'] = None
                return func(*args, **kwargs)

            return wrapper

        if multiple_blueprints and not env.MULTIPLE_LOCAL_BLUEPRINTS:
            return pass_empty_blueprint_id
        else:
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
