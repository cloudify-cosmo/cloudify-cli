import click

# TODO: should all decorators be functions?
from StringIO import StringIO

from .. import utils
from . import helptexts
from .. import constants
from ..constants import DEFAULT_REST_PORT
from ..exceptions import CloudifyCliError


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


# TODO: ideally, both verbose and debug should have callbacks
# which set the global verbosity level accordingly once a command
# is decorated without having to call a function explicitly from each command.
# The problem currently is, that setting the global verbosity level depends
# on both `verbose` and `debug` and to make them affect one another we need
# to pass one result of the decorator to the other (probably through click's
# state). For now, we're just calling `logger.set_global_verbosity_level`
# from each command.
verbose = click.option(
    '-v',
    '--verbose',
    count=True,
    is_eager=True)
debug = click.option(
    '--debug',
    default=False,
    is_flag=True,
    is_eager=True)

version = click.option(
    '--version',
    is_flag=True,
    callback=show_version,
    expose_value=False,
    is_eager=True)


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

validate = click.option(
    '--validate',
    is_flag=True,
    help=helptexts.VALIDATE_BLUEPRINT)

skip_install = click.option(
    '--skip-install',
    is_flag=True,
    help=helptexts.SKIP_INSTALL)
skip_uninstall = click.option(
    '--skip-uninstall',
    is_flag=True,
    help=helptexts.SKIP_UNINSTALL)

backup_first = click.option(
    '--backup-first',
    is_flag=True,
    help=helptexts.BACKUP_LOGS_FIRST)


management_user = click.option(
    '-u',
    '--management-user',
    required=False,
    help="The username on the host "
    "machine with which you bootstrapped")
management_key = click.option(
    '-k',
    '--management-key',
    required=False,
    help="The path to the ssh key-file you used to bootstrap")
rest_port = click.option(
    '--rest-port',
    required=False,
    default=DEFAULT_REST_PORT,
    help="The REST server's port")
show_active = click.option(
    '--show-active',
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=show_active_manager,
    help="Show connection information for the active manager")

init_hard_reset = click.option(
    '--hard',
    is_flag=True,
    help='Hard reset the configuration, including coloring and loggers')

reset_config = click.option(
    '-r',
    '--reset-config',
    # TODO: Change name. This is not true. It only resets the context
    is_flag=True,
    help=helptexts.RESET_CONFIG)
skip_logging = click.option(
    '--skip-logging',
    is_flag=True,
    help=helptexts.SKIP_LOGGING)

wait = click.option(
    '--wait',
    is_flag=True,
    help=helptexts.MAINTENANCE_MODE_WAIT)

node_name = click.option(
    '-n',
    '--node-name',
    required=False,
    help=helptexts.NODE_NAME)

include_metrics = click.option(
    '--include-metrics',
    is_flag=True,
    help=helptexts.INCLUDE_METRICS_IN_SNAPSHOT)

exclude_credentials = click.option(
    '--exclude-credentials',
    is_flag=True,
    help=helptexts.EXCLUDE_CREDENTIALS_IN_SNAPSHOT)

ssh_command = click.option(
    '-c',
    '--command',
    type=basestring,
    help=helptexts.SSH_COMMAND)
host_session = click.option(
    '--host',
    is_flag=True,
    help=helptexts.SSH_HOST_SESSION)
session_id = click.option(
    '--sid',
    type=basestring,
    help=helptexts.SSH_CONNECT_TO_SESSION)
list_sessions = click.option(
    '-l',
    '--list-sessions',
    is_flag=True,
    help=helptexts.SSH_LIST_SESSIONS)

ignore_deployments = click.option(
    '--ignore-deployments',
    is_flag=True,
    help=helptexts.IGNORE_DEPLOYMENTS)


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


def blueprint_id(required=False):
    return click.option(
        '-b',
        '--blueprint-id',
        help=helptexts.BLUEPRINT_ID)


def blueprint_path(required=False):
    return click.option(
        '-p',
        '--blueprint-path',
        required=True,
        type=click.Path(exists=True))
