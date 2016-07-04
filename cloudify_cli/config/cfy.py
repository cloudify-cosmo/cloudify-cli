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

import click
from click_didyoumean import DYMGroup

from StringIO import StringIO

from .. import utils
from . import helptexts
from .. import constants
from ..constants import DEFAULT_REST_PORT
from ..exceptions import CloudifyCliError


CLICK_CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help'],
    token_normalize_func=lambda param: param.lower(),
    ignore_unknown_options=True)


def _format_version_data(version_data,
                         prefix=None,
                         suffix=None,
                         infix=None):
    all_data = version_data.copy()
    all_data['prefix'] = prefix or ''
    all_data['suffix'] = suffix or ''
    all_data['infix'] = infix or ''
    output = StringIO()
    output.write('{prefix}{version}'.format(**all_data))
    output.write('{suffix}'.format(**all_data))
    return output.getvalue()


def show_version(ctx, param, value):
    # The callback in the `main` group is called regardless of whether
    # the --version flag was set or not so we need to return to main
    # in case it wasn't called.
    if not value or ctx.resilient_parsing:
        return

    cli_version_data = utils.get_version_data()
    rest_version_data = utils.get_manager_version_data()

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


def show_active_manager(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return

    print_solution = False
    current_management_ip = utils.get_management_server_ip()
    try:
        current_management_user = utils.get_management_user()
    except CloudifyCliError as ex:
        print_solution = True
        current_management_user = str(ex)
    try:
        current_management_key = utils.get_management_key()
    except CloudifyCliError as ex:
        print_solution = True
        current_management_key = str(ex)
    click.echo('Management IP: {0}'.format(current_management_ip))
    click.echo('Management User: {0}'.format(current_management_user))
    click.echo('Management Key: {0}'.format(current_management_key))
    if print_solution:
        click.echo(helptexts.SET_MANAGEMENT_CREDS)
    ctx.exit()


def group(name):
    return click.group(
        name=name,
        context_settings=CLICK_CONTEXT_SETTINGS,
        cls=DYMGroup)


def command(name, with_context=True):
    context_settings = CLICK_CONTEXT_SETTINGS if with_context else None
    return click.command(name=name, context_settings=context_settings)


class Options(object):
    def __init__(self):

        # TODO: Ideally, both verbose and debug should have callbacks
        # which set the global verbosity level accordingly once a command
        # is decorated without having to call a function explicitly from each
        # command. The problem currently is, that setting the global verbosity
        # level depends on both `verbose` and `debug` and to make them affect
        # one another we need to pass one result of the decorator to the other
        # (probably using click's `get_current_state` impelmeneted in Click 6).
        # For now, we're just calling `logger.set_global_verbosity_level`
        # from each command.

        self.verbose = click.option(
            '-v',
            '--verbose',
            count=True,
            is_eager=True,
            help=helptexts.VERBOSE)

        self.debug = click.option(
            '--debug',
            default=False,
            is_flag=True,
            is_eager=True,
            help=helptexts.DEBUG)

        self.version = click.option(
            '--version',
            is_flag=True,
            callback=show_version,
            expose_value=False,
            is_eager=True)

        self.inputs = click.option(
            '-i',
            '--inputs',
            multiple=True,
            help=helptexts.INPUTS)

        self.parameters = click.option(
            '-p',
            '--parameters',
            multiple=True,
            help=helptexts.PARAMETERS)

        self.output_path = click.option(
            '-o',
            '--output-path',
            default=utils.get_cwd(),
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

        self.management_user = click.option(
            '-u',
            '--management-user',
            required=False,
            help="The username on the host "
            "machine with which you bootstrapped")

        self.management_key = click.option(
            '-k',
            '--management-key',
            required=False,
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['management-password'],
            help="The path to the ssh key-file to use when "
            "connecting to the manager")

        self.management_password = click.option(
            '-p',
            '--management-password',
            required=False,
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['management-key'],
            help="The password to use when connecting to the manager")

        self.management_port = click.option(
            '--ssh-port',
            required=False,
            default=22,
            help="The port to use when connecting to the manager")

        self.rest_port = click.option(
            '--rest-port',
            required=False,
            default=DEFAULT_REST_PORT,
            help="The REST server's port")

        self.show_active = click.option(
            '--show-active',
            is_flag=True,
            is_eager=True,
            expose_value=False,
            callback=show_active_manager,
            help="Show connection information for the active manager")

        self.init_hard_reset = click.option(
            '--hard',
            is_flag=True,
            help='Hard reset the configuration, '
            'including coloring and loggers')

        self.reset_config = click.option(
            '-r',
            '--reset-config',
            # TODO: Change name. This is not true. It only resets the context
            is_flag=True,
            required=True,
            help=helptexts.RESET_CONFIG)

        self.skip_logging = click.option(
            '--skip-logging',
            is_flag=True,
            help=helptexts.SKIP_LOGGING)

        self.wait = click.option(
            '--wait',
            is_flag=True,
            help=helptexts.MAINTENANCE_MODE_WAIT)

        self.node_name = click.option(
            '-n',
            '--node-name',
            required=False,
            help=helptexts.NODE_NAME)

        self.without_deployments_envs = click.option(
            '--without-deployments-envs',
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

    @staticmethod
    def force(help):
        return click.option(
            '-f',
            '--force',
            is_flag=True,
            help=help)

    @staticmethod
    def blueprint_filename(default=constants.DEFAULT_BLUEPRINT_FILE_NAME):
        return click.option(
            '-n',
            '--blueprint-filename',
            default=default,
            help=helptexts.BLUEPRINT_FILENAME.format(default))

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


class MutuallyExclusiveOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop('mutually_exclusive', []))
        self.mutuality_error_message = \
            kwargs.pop('mutuality_error_message', [])
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
                "Illegal usage: `{0}` is mutually exclusive with "
                "arguments `{1}` ({2}).".format(
                    self.name,
                    self.mutuality_string,
                    self.mutuality_error_message))
        return super(MutuallyExclusiveOption, self).handle_parse_result(
            ctx, opts, args)
