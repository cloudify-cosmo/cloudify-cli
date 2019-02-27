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
import urllib
import difflib
import StringIO
import warnings
import traceback
from functools import wraps

import click
from cloudify_rest_client.constants import VisibilityState
from cloudify_rest_client.exceptions import NotModifiedError
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.exceptions import MaintenanceModeActiveError
from cloudify_rest_client.exceptions import MaintenanceModeActivatingError

from .. import env, logger
from ..cli import helptexts
from ..inputs import inputs_to_dict
from ..utils import generate_random_string
from ..constants import DEFAULT_BLUEPRINT_PATH
from ..exceptions import SuppressedCloudifyCliError
from ..exceptions import CloudifyBootstrapError, CloudifyValidationError
from ..logger import (
    get_logger,
    set_global_verbosity_level,
    DEFAULT_LOG_FILE,
    set_global_json_output)


CLICK_CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help'],
    token_normalize_func=lambda param: param.lower())

AGENT_FILTER_NODE_IDS = 'node_ids'
AGENT_FILTER_NODE_INSTANCE_IDS = 'node_instance_ids'
AGENT_FILTER_DEPLOYMENT_ID = 'deployment_id'
AGENT_FILTER_INSTALL_METHODS = 'install_methods'


class MutuallyExclusiveOption(click.Option):
    """Makes options mutually exclusive. The option must pass a `cls` argument
    with this class name and a `mutually_exclusive` argument with a list of
    argument names it is mutually exclusive with.

    NOTE: All mutually exclusive options must use this. It's not enough to
    use it in just one of the options.
    """

    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop('mutually_exclusive', []))
        self.mutuality_string = ', '.join(self.mutually_exclusive)
        if self.mutually_exclusive:
            help = kwargs.get('help', '')
            kwargs['help'] = (
                '{0}. You cannot use this argument with arguments: [{1}]'
                .format(help, self.mutuality_string)
            )
        super(MutuallyExclusiveOption, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise click.UsageError(
                'Illegal usage: `{0}` is mutually exclusive with '
                'arguments: [{1}]'.format(self.name, self.mutuality_string)
            )
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


def _tenant_help_message(message, message_template, resource_name):
    if message is not None:
        return message
    if resource_name is not None:
        return message_template.format(resource_name)
    return helptexts.TENANT


def _get_validate_callback(validate):
    if validate:
        return validate_name
    return None


def show_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return

    cli_version_data = env.get_version_data()
    rest_version_data = env.get_manager_version_data() \
        if env.is_manager_active() else None
    output = ''
    if rest_version_data:
        edition = rest_version_data['edition'].title()
        output += '{0} edition\n\n'.format(edition)

    output += _format_version_data(
        cli_version_data,
        prefix='Cloudify CLI ',
        infix=' ' * 5,
        suffix='\n')
    if rest_version_data:
        output += _format_version_data(
            rest_version_data,
            prefix='Cloudify Manager ',
            infix=' ',
            suffix=' [ip={ip}]\n'.format(**rest_version_data))

    get_logger().info(output)
    ctx.exit()


def inputs_callback(ctx, param, value):
    """Allow to pass any inputs we provide to a command as
    processed inputs instead of having to call `inputs_to_dict`
    inside the command.

    `@cfy.options.inputs` already calls this callback so that
    every time you use the option it returns the inputs as a
    dictionary.
    """
    if not value or ctx.resilient_parsing:
        return {}

    return inputs_to_dict(value)


def validate_name(ctx, param, value):
    if value is None or ctx.resilient_parsing:
        return

    if not value:
        raise CloudifyValidationError(
            'ERROR: The `{0}` argument is empty'.format(param.name)
        )

    quoted_value = urllib.quote(value, safe='')
    if value != quoted_value:
        raise CloudifyValidationError(
            'ERROR: The `{0}` argument contains illegal characters. Only '
            'letters, digits and the characters "-", "." and "_" are '
            'allowed'.format(param.name)
        )

    return value


def validate_password(ctx, param, value):
    if value is None or ctx.resilient_parsing:
        return

    if not value:
        raise CloudifyValidationError('ERROR: The password is empty')

    return value


def validate_nonnegative_integer(ctx, param, value):
    if ctx.resilient_parsing:
        return

    try:
        assert int(value) >= 0
    except (ValueError, AssertionError):
        raise CloudifyValidationError('ERROR: {0} is expected to be a '
                                      'nonnegative integer'.format(param.name))
    return value


def set_json(ctx, param, value):
    if value is not None:
        set_global_json_output(value)
    return value


def set_format(ctx, param, value):
    if value == 'json':
        set_global_json_output(True)
    return value


def json_output_deprecate(ctx, param, value):
    if value:
        warnings.warn("Instead of --json-output, use the global "
                      "`cfy --json` flag")
    return value


def set_verbosity_level(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    if param.name == 'verbose':
        set_global_verbosity_level(value)
    elif value and param.name == 'quiet':
        set_global_verbosity_level(logger.QUIET)
    return value


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
    """Wrap the command so that it can only run when a manager is active
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
    """Wrap the command so that it can only run when in local context
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


def pass_client(use_tenant_in_header=True, *args, **kwargs):
    """Simply passes the rest client to a command.
    """
    def add_client_inner(func):
        # Wraps here makes sure the original docstring propagates to click
        @wraps(func)
        def wrapper(*wrapper_args, **wrapper_kwargs):
            tenant = wrapper_kwargs.get('tenant_name') \
                if use_tenant_in_header else None
            client = env.get_rest_client(tenant_name=tenant, *args, **kwargs)
            return func(client=client, *wrapper_args, **wrapper_kwargs)

        return wrapper

    return add_client_inner


def pass_context(func):
    """Make click context Cloudify specific

    This exists purely for aesthetic reasons, otherwise
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
        """Override clicks ``resolve_command`` method
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

    def command(self, *a, **kw):
        kw.setdefault('cls', CommandWithLoggers)
        return super(AliasedGroup, self).command(*a, **kw)


def group(name):
    """Allow to create a group with a default click context
    and a cls for click's `didyoueamn` without having to repeat
    it for every group.
    """
    return click.group(
        name=name,
        context_settings=CLICK_CONTEXT_SETTINGS,
        cls=AliasedGroup)


class CommandWithLoggers(click.Command):
    """Like a click Command, but configure loggers first.

    We want loggers to be configured after argument parsing has been
    performed (ie. verbose/quiet callbacks have fired), but before the
    command was actually run.
    """
    def invoke(self, *a, **kw):
        logger.configure_loggers()
        return super(CommandWithLoggers, self).invoke(*a, **kw)


def command(*args, **kwargs):
    """Make Click commands Cloudify specific

    This exists purely for aesthetical reasons, otherwise
    Some decorators are called `@click.something` instead of
    `@cfy.something`
    """
    kwargs.setdefault('cls', CommandWithLoggers)
    return click.command(*args, **kwargs)


def argument(*args, **kwargs):
    """Make Click arguments Cloudify specific

    This exists purely for aesthetic reasons, otherwise
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

        self.format = click.option(
            '--format',
            type=click.Choice(['plain', 'json']),
            expose_value=False,
            callback=set_format
        )

        self.json = click.option(
            '--json',
            is_flag=True,
            expose_value=False,
            default=None,
            callback=set_json)

        self.inputs = click.option(
            '-i',
            '--inputs',
            multiple=True,
            callback=inputs_callback,
            help=helptexts.INPUTS)

        self.reinstall_list = click.option(
            '-r',
            '--reinstall-list',
            multiple=True,
            help=helptexts.REINSTALL_LIST)

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

        self.all_nodes = click.option(
            '--all-nodes',
            is_flag=True,
            help=helptexts.ALL_NODES
        )

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

        self.all_tenants = click.option(
            '-a',
            '--all-tenants',
            is_flag=True,
            default=False,
            help=helptexts.ALL_TENANTS,
        )

        self.all_executions = click.option(
            '--all-executions',
            is_flag=True,
            default=False,
            help=helptexts.ALL_EXECUTIONS,
        )

        self.search = click.option(
            '--search',
            default=None,
            required=False,
            help=helptexts.SEARCH,
        )

        self.include_logs = click.option(
            '--include-logs/--no-logs',
            default=True,
            help=helptexts.INCLUDE_LOGS)

        self.dry_run = click.option(
            '--dry-run',
            is_flag=True,
            help=helptexts.DRY_RUN
        )

        self.json_output = click.option(
            '--json-output',
            is_flag=True,
            callback=json_output_deprecate,
            help=helptexts.JSON_OUTPUT)

        self.tail = click.option(
            '--tail',
            is_flag=True,
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['pagination_offset', 'pagination_size'],
            help=helptexts.TAIL_OUTPUT)

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

        self.skip_reinstall = click.option(
            '--skip-reinstall',
            is_flag=True,
            help=helptexts.SKIP_REINSTALL)

        self.ignore_failure = click.option(
            '--ignore-failure',
            is_flag=True,
            help=helptexts.IGNORE_FAILURE)

        self.install_first = click.option(
            '--install-first',
            is_flag=True,
            help=helptexts.INSTALL_FIRST)

        self.preview = click.option(
            '--preview',
            is_flag=True,
            help=helptexts.PREVIEW)

        self.backup_first = click.option(
            '--backup-first',
            is_flag=True,
            help=helptexts.BACKUP_LOGS_FIRST)

        self.ssh_user = click.option(
            '-s',
            '--ssh-user',
            required=False,
            help=helptexts.SSH_USER)

        self.ssh_user_flag = click.option(
            '-s',
            '--ssh-user',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.SSH_USER)

        self.ssh_key = click.option(
            '-k',
            '--ssh-key',
            required=False,
            cls=MutuallyExclusiveOption,
            help=helptexts.SSH_KEY)

        self.ssh_key_flag = click.option(
            '-k',
            '--ssh-key',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.SSH_KEY)

        self.profile_name = click.option(
            '--profile-name',
            required=False,
            help=helptexts.PROFILE_NAME)

        self.manager_username = click.option(
            '-u',
            '--manager-username',
            required=False,
            help=helptexts.MANAGER_USERNAME,
            callback=validate_name
        )

        self.manager_username_flag = click.option(
            '-u',
            '--manager-username',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.MANAGER_USERNAME)

        self.manager_password = click.option(
            '-p',
            '--manager-password',
            required=False,
            help=helptexts.MANAGER_PASSWORD,
            callback=validate_password)

        self.manager_password_flag = click.option(
            '-p',
            '--manager-password',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.MANAGER_PASSWORD)

        self.manager_tenant = click.option(
            '-t',
            '--manager-tenant',
            required=False,
            help=helptexts.MANAGER_TENANT,
            callback=validate_name
        )

        self.manager_tenant_flag = click.option(
            '-t',
            '--manager-tenant',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.MANAGER_TENANT)

        self.rest_certificate = click.option(
            '-c',
            '--rest-certificate',
            required=False,
            help=helptexts.REST_CERT
        )

        self.rest_certificate_flag = click.option(
            '-c',
            '--rest-certificate',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.REST_CERT)

        self.kerberos_env = click.option(
            '--kerberos-env',
            required=False,
            help=helptexts.KERBEROS_ENV
        )

        self.kerberos_env_flag = click.option(
            '--kerberos-env',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.KERBEROS_ENV)

        self.ssl_state = click.option(
            '--ssl',
            required=False,
            help=helptexts.SSL_STATE,
            callback=validate_name
        )

        self.ssh_port = click.option(
            '--ssh-port',
            required=False,
            help=helptexts.SSH_PORT)

        self.rest_port = click.option(
            '--rest-port',
            required=False,
            help=helptexts.REST_PORT)

        self.ssl_rest = click.option(
            '--ssl',
            is_flag=True,
            required=False,
            default=False,
            help=helptexts.SSL_REST)

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

        self.exclude_logs = click.option(
            '--exclude-logs',
            is_flag=True,
            help=helptexts.EXCLUDE_LOGS_IN_SNAPSHOT)

        self.exclude_events = click.option(
            '--exclude-events',
            is_flag=True,
            help=helptexts.EXCLUDE_EVENTS_IN_SNAPSHOT)

        self.ssh_command = click.option(
            '-c',
            '--command',
            help=helptexts.SSH_COMMAND)

        self.group_name = click.option(
            '-g',
            '--group-name',
            required=True,
            help=helptexts.GROUP,
            callback=validate_name
        )

        self.ldap_distinguished_name = click.option(
            '-l',
            '--ldap-distinguished-name',
            required=False,
            help=helptexts.GROUP_DN)

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

        self.restore_certificates = click.option(
            '--restore-certificates',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.RESTORE_CERTIFICATES)

        self.no_reboot = click.option(
            '--no-reboot',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.NO_REBOOT)

        self.security_role = click.option(
            '-r',
            '--security-role',
            required=False,
            default='default',
            help=helptexts.SECURITY_ROLE)

        self.password = click.option(
            '-p',
            '--password',
            required=True,
            help=helptexts.PASSWORD,
            callback=validate_password)

        self.skip_credentials_validation = click.option(
            '--skip-credentials-validation',
            is_flag=True,
            default=False,
            help=helptexts.SKIP_CREDENTIALS_VALIDATION
        )

        self.cluster_host_ip = click.option(
            '--cluster-host-ip',
            default=lambda: env.profile.manager_ip,
            help=helptexts.CLUSTER_HOST_IP)

        self.cluster_node_name = click.option(
            '--cluster-node-name',
            default=lambda: 'cloudify_manager_' + generate_random_string(),
            help=helptexts.CLUSTER_NODE_NAME)

        self.private_resource = click.option(
            '--private-resource',
            is_flag=True,
            default=False,
            help=helptexts.PRIVATE_RESOURCE
        )

        self.skip_plugins_validation = click.option(
            '--skip-plugins-validation',
            is_flag=True,
            default=False,
            help=helptexts.SKIP_PLUGINS_VALIDATION
        )

        self.users = click.option(
            '-u',
            '--users',
            required=True,
            multiple=True,
            help=helptexts.USER
        )

        self.get_data = click.option(
            '--get-data',
            is_flag=True,
            default=False,
            help=helptexts.GET_DATA
        )

        self.secret_string = click.option(
            '-s',
            '--secret-string',
            required=False,
            help=helptexts.SECRET_STRING)

        self.secret_update_if_exists = click.option(
            '-u',
            '--update-if-exists',
            is_flag=True,
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['hidden_value', 'visibility'],
            help=helptexts.SECRET_UPDATE_IF_EXISTS,
        )

        self.hidden_value = click.option(
            '--hidden-value',
            is_flag=True,
            default=False,
            help=helptexts.HIDDEN_VALUE,
        )

        self.update_hidden_value = click.option(
            '--hidden-value/--not-hidden-value',
            default=None,
            help=helptexts.HIDDEN_VALUE)

        self.update_visibility = click.option(
            '-l',
            '--visibility',
            help=helptexts.VISIBILITY.format(VisibilityState.STATES)
        )

        self.plugins_bundle_path = click.option(
            '-p',
            '--path',
            required=False,
            help=helptexts.PLUGINS_BUNDLE_PATH
        )

        # same as --inputs, name changed for consistency
        self.cluster_node_options = click.option(
            '-o',
            '--options',
            multiple=True,
            callback=inputs_callback,
            help=helptexts.CLUSTER_NODE_OPTIONS)

        self.pagination_offset = click.option(
            '-o',
            '--pagination-offset',
            required=False,
            default=0,
            callback=validate_nonnegative_integer,
            help=helptexts.PAGINATION_OFFSET)

        self.pagination_size = click.option(
            '-s',
            '--pagination-size',
            required=False,
            default=1000,
            callback=validate_nonnegative_integer,
            help=helptexts.PAGINATION_SIZE)

        self.manager_ip = click.option(
            '--manager-ip',
            required=False,
            help=helptexts.MANAGER_IP
        )

        self.manager_certificate = click.option(
            '--manager_certificate',
            required=False,
            help=helptexts.MANAGER_CERTIFICATE_PATH
        )

        self.stop_old_agent = click.option(
            '--stop-old-agent',
            is_flag=True,
            default=False,
            help=helptexts.STOP_OLD_AGENT
        )

        self.ignore_plugin_failure = click.option(
            '-i',
            '--ignore-plugin-failure',
            is_flag=True,
            default=False,
            help=helptexts.IGNORE_PLUGIN_FAILURE
        )

        self.queue = click.option(
            '--queue',
            is_flag=True,
            default=False,
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['dry_run', 'force'],
            help=helptexts.QUEUE_EXECUTIONS
        )

        self.reset_operations = click.option(
            '--reset-operations',
            is_flag=True,
            default=False,
            help=helptexts.RESET_OPERATIONS
        )

        self.schedule = click.option(
            '--schedule',
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['queue'],
            help=helptexts.SCHEDULE_EXECUTIONS
        )

        self.queue_snapshot = click.option(
            '--queue',
            is_flag=True,
            default=False,
            help=helptexts.QUEUE_SNAPSHOTS
        )

        self.wait_after_fail = click.option(
            '--wait-after-fail',
            default=600,
            type=int,
            help=helptexts.WAIT_AFTER_FAIL
        )

        self.agents_wait = click.option(
            '--wait/--no-wait',
            is_flag=True,
            default=True,
            help=helptexts.AGENTS_WAIT
        )

    def common_options(self, f):
        """A shorthand for applying commonly used arguments.

        To be used for arguments that are going to be applied for all or
        almost all commands.
        """
        for arg in [self.json, self.verbose(), self.format, self.quiet()]:
            f = arg(f)
        return f

    def parse_comma_separated(self, ctx, param, value):
        """Callback for parsing multiple comma-separated arguments.

        This is for use with `--opt a --opt b,c` -> ['a', 'b', 'c']
        """
        if not value:
            return []
        return sum((part.split(',') for part in value), [])

    def agent_filters(self, f):
        """Set of filter arguments for commands working with a list of agents

        Applies deployment id, node id and node instance id filters.
        """
        node_instance_id = click.option('--node-instance-id', multiple=True,
                                        help=helptexts.AGENT_NODE_INSTANCE_ID,
                                        callback=self.parse_comma_separated)
        node_id = click.option('--node-id', multiple=True,
                               help=helptexts.AGENT_NODE_ID,
                               callback=self.parse_comma_separated)
        install_method = click.option('--install-method', multiple=True,
                                      help=helptexts.AGENT_INSTALL_METHOD,
                                      callback=self.parse_comma_separated)
        deployment_id = click.option('--deployment-id', multiple=True,
                                     help=helptexts.AGENT_DEPLOYMENT_ID,
                                     callback=self.parse_comma_separated)

        # we add separate --node-instance-id, --node-id and --deployment-id
        # arguments, but only expose a agents_filter = {'node_id': ..} dict
        # to the decorated function
        def _filters_deco(f):
            @wraps(f)
            def _inner(*args, **kwargs):
                filters = {}
                for arg_name, filter_name in [
                        ('node_id', AGENT_FILTER_NODE_IDS),
                        ('node_instance_id', AGENT_FILTER_NODE_INSTANCE_IDS),
                        ('deployment_id', AGENT_FILTER_DEPLOYMENT_ID),
                        ('install_method', AGENT_FILTER_INSTALL_METHODS)]:
                    filters[filter_name] = kwargs.pop(arg_name, None)

                kwargs['agent_filters'] = filters
                return f(*args, **kwargs)
            return _inner

        for arg in [install_method, node_instance_id, node_id,
                    deployment_id, _filters_deco]:
            f = arg(f)
        return f

    @staticmethod
    def secret_file():
        return click.option(
            '-f',
            '--secret-file',
            required=False,
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['secret_string'],
            help=helptexts.SECRET_FILE
        )

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
    def quiet(expose_value=False):
        return click.option(
            '-q',
            '--quiet',
            is_flag=True,
            callback=set_verbosity_level,
            expose_value=expose_value,
            is_eager=True,
            help=helptexts.QUIET)

    @staticmethod
    def tenant_name(required=True,
                    mutually_exclusive_with=None,
                    help=None,
                    resource_name_for_help=None,
                    show_default_in_help=True):
        args = ['-t', '--tenant-name']
        kwargs = {
            'required': required,
            'multiple': False,
            'help': _tenant_help_message(
                help, helptexts.TENANT_TEMPLATE, resource_name_for_help),
            'callback': validate_name
        }
        if show_default_in_help:
            kwargs['help'] += \
                '. If not specified, the current tenant will be used'
        if mutually_exclusive_with:
            kwargs['cls'] = MutuallyExclusiveOption
            kwargs['mutually_exclusive'] = mutually_exclusive_with
        return click.option(*args, **kwargs)

    @staticmethod
    def tenant_name_for_list(*args, **kwargs):
        if 'mutually_exclusive_with' not in kwargs:
            kwargs['mutually_exclusive_with'] = ['all_tenants']
        kwargs['help'] = _tenant_help_message(
            kwargs.get('help'),
            helptexts.TENANT_LIST_TEMPLATE,
            kwargs.get('resource_name_for_help'))
        return Options.tenant_name(
            *args, **kwargs)

    @staticmethod
    def ldap_server():
        return click.option(
            '-s',
            '--ldap-server',
            required=True,
            help=helptexts.LDAP_SERVER)

    @staticmethod
    def ldap_username():
        return click.option(
            '-u',
            '--ldap-username',
            required=False,
            default=None,
            help=helptexts.LDAP_USERNAME)

    @staticmethod
    def ldap_password():
        return click.option(
            '-p',
            '--ldap-password',
            required=False,
            default=None,
            help=helptexts.LDAP_PASSWORD)

    @staticmethod
    def ldap_domain():
        return click.option(
            '-d',
            '--ldap-domain',
            required=False,
            help=helptexts.LDAP_DOMAIN)

    @staticmethod
    def ldap_is_active_directory():
        return click.option(
            '-a',
            '--ldap-is-active-directory',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.LDAP_IS_ACTIVE_DIRECTORY)

    @staticmethod
    def ldap_dn_extra():
        return click.option(
            '-e',
            '--ldap-dn-extra',
            required=False,
            help=helptexts.LDAP_DN_EXTRA)

    @staticmethod
    def force(help):
        return click.option(
            '-f',
            '--force',
            is_flag=True,
            help=help)

    @staticmethod
    def kill():
        return click.option(
            '-k',
            '--kill',
            is_flag=True,
            help=helptexts.KILL_EXECUTION)

    @staticmethod
    def blueprint_filename(extra_message=''):
        return click.option(
            '-n',
            '--blueprint-filename',
            default=DEFAULT_BLUEPRINT_PATH,
            help=helptexts.BLUEPRINT_FILENAME + extra_message)

    @staticmethod
    def workflow_id(default=None):
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
            help=helptexts.OPERATION_TIMEOUT.format(default))

    @staticmethod
    def deployment_id(required=False, validate=False):
        return click.option(
            '-d',
            '--deployment-id',
            required=required,
            help=helptexts.DEPLOYMENT_ID,
            callback=_get_validate_callback(validate))

    @staticmethod
    def snapshot_id(required=False, validate=False):
        return click.option(
            '-s',
            '--snapshot-id',
            required=required,
            help=helptexts.SNAPSHOT_ID,
            callback=_get_validate_callback(validate))

    @staticmethod
    def execution_id(required=False, dest=None):
        return click.option(
            '-e',
            '--execution-id',
            dest,
            required=required,
            help=helptexts.EXECUTION_ID)

    @staticmethod
    def blueprint_id(required=False, validate=False):
        return click.option(
            '-b',
            '--blueprint-id',
            required=required,
            help=helptexts.BLUEPRINT_ID,
            callback=_get_validate_callback(validate))

    @staticmethod
    def blueprint_path(required=False):
        return click.option(
            '-p',
            '--blueprint-path',
            required=required,
            type=click.Path(exists=True),
            help=helptexts.BLUEPRINT_PATH)

    @staticmethod
    def tenant_role(help_text, required, options_flags=None):
        args = options_flags or ['-r', '--role']

        kwargs = {
            'required': required,
            'help': help_text
        }
        return click.option(*args, **kwargs)

    @staticmethod
    def user_tenant_role(required=True, options_flags=None):
        return Options.tenant_role(
            helptexts.USER_TENANT_ROLE, required=required,
            options_flags=options_flags)

    @staticmethod
    def group_tenant_role():
        return Options.tenant_role(
            helptexts.GROUP_TENANT_ROLE, required=True)

    @staticmethod
    def visibility(required=False,
                   valid_values=VisibilityState.STATES,
                   mutually_exclusive_required=True):
        args = ['-l', '--visibility']
        kwargs = {
            'required': required,
            'help': helptexts.VISIBILITY.format(valid_values)
        }
        if not required:
            kwargs['default'] = VisibilityState.TENANT
            kwargs['help'] += ' [default: tenant]'
            if mutually_exclusive_required:
                kwargs['cls'] = MutuallyExclusiveOption
                kwargs['mutually_exclusive'] = ['private_resource']
        return click.option(*args, **kwargs)

    @staticmethod
    def plugin_yaml_path():
        return click.option(
            '-y',
            '--yaml-path',
            required=True,
            help=helptexts.PLUGIN_YAML_PATH)


options = Options()
