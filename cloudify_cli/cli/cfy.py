import sys
import os
import difflib
import warnings
import traceback
import pkg_resources
import datetime
import re
import subprocess
import locale
import codecs
import unicodedata
from functools import wraps
from io import StringIO
from urllib.parse import quote as urlquote

import click

from cloudify.models_states import AgentState
from cloudify_rest_client.constants import VisibilityState
from cloudify_rest_client.exceptions import NotModifiedError
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.exceptions import MaintenanceModeActiveError
from cloudify_rest_client.exceptions import MaintenanceModeActivatingError

from cloudify_cli import env, logger
from cloudify_cli.cli import helptexts
from cloudify_cli.constants import DEFAULT_BLUEPRINT_PATH
from cloudify_cli.exceptions import (
    LabelsValidationError,
    CloudifyBootstrapError,
    CloudifyValidationError,
    SuppressedCloudifyCliError)
from cloudify_cli.filters_utils import (
    get_filter_rules,
    create_labels_filter_rules_list,
    create_attributes_filter_rules_list)
from cloudify_cli.inputs import inputs_to_dict
from cloudify_cli.logger import (
    get_logger,
    set_global_verbosity_level,
    DEFAULT_LOG_FILE,
    set_global_json_output,
    set_global_extended_view)
from cloudify_cli.utils import generate_random_string


CLICK_CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help'],
)

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


def _parse_relative_datetime(ctx, param, rel_datetime):
    """Change relative time (ago) to a valid timestamp"""
    if not rel_datetime:
        return None
    parsed = re.findall(r"(\d+) (seconds?|minutes?|hours?|days?|weeks?"
                        "|months?|years?) ?(ago)?",
                        rel_datetime)
    if not parsed or len(parsed[0]) < 2:
        return None
    number = int(parsed[0][0])
    period = parsed[0][1]
    if period[-1] != u's':
        period += u's'
    now = datetime.datetime.utcnow()
    if period == u'years':
        result = now.replace(year=now.year - number)
    elif period == u'months':
        if now.month > number:
            result = now.replace(month=now.month - number)
        else:
            result = now.replace(month=now.month - number + 12,
                                 year=now.year - 1)
    else:
        delta = datetime.timedelta(**{period: number})
        result = now - delta
    return result


def _parse_unix_timestamp(unix_time):
    parsed = re.findall(r"^(\d+)(\.(\d{1,6}))?$", unix_time)
    if not parsed or len(parsed[0]) < 1:
        return None
    return datetime.datetime.utcfromtimestamp(float(unix_time))


class Timestamp(click.DateTime):
    """Timestamp is DateTime enhanced by the ability to parse Unix time"""

    def convert(self, value, param, ctx):
        parsed_unix_time = _parse_unix_timestamp(value)
        if parsed_unix_time:
            return parsed_unix_time
        return super(Timestamp, self).convert(value, param, ctx)

    def get_metavar(self, param):
        return '[{0}|UNIX TIME FORMAT]'.format('|'.join(self.formats))

    def __repr__(self):
        return "Timestamp"


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

    cli_version_output = _format_version_data(
        {'version': pkg_resources.require('cloudify')[0].version},
        prefix='Cloudify CLI ',
        infix=' ' * 5,
        suffix='\n')

    try:
        rest_version_data = env.get_manager_version_data() \
            if env.is_manager_active() else None
    except Exception as e:
        get_logger().info(cli_version_output)
        sys.stderr.write("Cannot get Cloudify Manager version. {}: "
                         "{}\n".format(type(e).__name__, str(e)))
        ctx.exit(1)

    output = ''
    if rest_version_data:
        edition = rest_version_data['edition'].title()
        output += '{0} edition\n\n'.format(edition)
    output += cli_version_output
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


def properties_callback(ctx, param, value):
    """Same as inputs_callback above,
    But also allows the user to pass inputs of the format key=value where
    key has a dot hierarchy - e.g. 'a.b.c=d', and parses such inputs
    into correct dict format: {a: {b: {c: d}}}.
    """
    if not value or ctx.resilient_parsing:
        return {}
    deleting = ctx.info_name == 'delete-runtime'
    return inputs_to_dict(value, dot_hierarchy=True, deleting=deleting)


def parse_on_off(ctx, param, value):
    if value is None or ctx.resilient_parsing:
        return
    if value.lower() == 'off':
        return False
    elif value.lower() == 'on':
        return True
    else:
        raise CloudifyValidationError(
            'Value must be on/off, but got: {0}'.format(value))


def parse_and_validate_labels(ctx, param, value):
    if value is None or ctx.resilient_parsing:
        return

    if not value:
        raise CloudifyValidationError(
            'ERROR: The `{0}` argument is empty'.format(param.name))

    return get_formatted_labels_list(value)


def parse_and_validate_label_to_delete(ctx, param, value):
    if value is None or ctx.resilient_parsing:
        return

    if not value:
        raise CloudifyValidationError(
            'ERROR: The `{0}` argument is empty'.format(param.name))

    return get_formatted_labels_list(value, allow_only_key=True)


def validate_value_not_empty(ctx, param, value):
    if value is None or ctx.resilient_parsing:
        return

    if not value:
        raise CloudifyValidationError(
            'ERROR: The `{0}` argument is empty'.format(param.name))

    return value


def get_formatted_labels_list(raw_labels_string, allow_only_key=False):
    labels_list = []
    if any(unicodedata.category(char)[0] == 'C' or char == '"'
           for char in raw_labels_string):
        raise CloudifyValidationError(
            'Error: labels cannot contain control characters or `"`')

    format_err_msg = 'Labels should be of the form <key>:<value>,<key>:<value>'
    raw_labels_string = raw_labels_string.replace('\\,', '\x00').split(',')
    for label in raw_labels_string:
        label = label.replace('\x00', ',')
        label = label.replace('\\:', '\x00')
        colons_count = label.count(':')
        if colons_count == 0:
            if not allow_only_key:
                raise LabelsValidationError(label, format_err_msg)
            label_key, label_value = label, None

        elif colons_count == 1:
            label_key, label_value = label.split(':')
            if not label_key or not label_value:
                raise LabelsValidationError(label, format_err_msg)
            label_value = label_value.replace('\x00', ':')

        else:
            if allow_only_key:
                raise CloudifyValidationError(
                    'LABEL should be a mixed list of labels and keys. I.e. '
                    '<key>:<value>,<key>,<key>:<value>')
            raise LabelsValidationError(label, format_err_msg)

        label_key = label_key.replace('\x00', ':').strip()
        try:
            validate_param_value('label_key', label_key)
        except CloudifyValidationError:
            raise LabelsValidationError(
                label, "The label's key contains illegal characters. "
                       "Only letters, digits and the characters `-`, `.` and "
                       "`_` are allowed")

        labels_list.append({label_key: label_value})

    return labels_list


def _validate_filter_rules_not_empty(ctx, param, value):
    if value is None or value == () or ctx.resilient_parsing:
        return

    if not value:
        raise CloudifyValidationError(
            'ERROR: The `{0}` argument is empty'.format(param.name))


def parse_labels_filter_rules(ctx, param, value):
    _validate_filter_rules_not_empty(ctx, param, value)
    return create_labels_filter_rules_list(value)


def parse_attributes_filter_rules(ctx, param, value):
    _validate_filter_rules_not_empty(ctx, param, value)
    return create_attributes_filter_rules_list(value)


def validate_name(ctx, param, value):
    if value is None or ctx.resilient_parsing:
        return

    return validate_param_value('The `{0}` argument'.format(param.name), value)


def validate_param_value(err_prefix, value):
    if not value:
        raise CloudifyValidationError('ERROR: {0} is empty'.format(err_prefix))

    quoted_value = urlquote(value, safe='')
    if value != quoted_value:
        raise CloudifyValidationError(
            'ERROR: {0} contains illegal characters. Only letters, digits and '
            'the characters "-", "." and "_" are allowed'.format(err_prefix))

    return value


def validate_password(ctx, param, value):
    if value is None or ctx.resilient_parsing:
        return

    if not value:
        raise CloudifyValidationError('ERROR: The password is empty')

    return value


def validate_encryption_passphrase(ctx, param, value):
    value = validate_password(ctx, param, value)
    if value and len(value) < 8:
        raise CloudifyValidationError('ERROR: Passphrase must contain at '
                                      'least 8 characters.')
    return value


def validate_nonnegative_integer(ctx, param, value):
    if ctx.resilient_parsing:
        return

    try:
        value = int(value)
        if value < 0:
            raise ValueError()
    except ValueError:
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
    elif value == 'extended':
        set_global_extended_view(True)
    return value


def set_extended_view(ctx, param, value):
    if value is not None:
        set_global_extended_view(value)
    return value


def set_manager(ctx, param, value):
    if value is None:
        return
    if env.is_cluster():
        env.set_target_manager(value)
    else:
        get_logger().warning(
            '--manager can only be used in a cluster topology and the '
            'current profile is an all-in-one Cloudify Manager'
        )


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
                tpe,
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
            s_traceback = StringIO()
            traceback.print_exception(
                tpe,
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
    """
    Wrap the command so that it can only run when a manager is active

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
    """
    Wrap the command so that it can only run when in local context
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


class CommandMixin(object):
    """
    This class mixin helps to set the right locale for system required
    by python 3 for click library where "LC_ALL" & "LANG" are not set and
    in order to avoid the RuntimeError raised by click library which
    prevents invoking cfy commands
    """
    def main(
        self,
        args=None,
        prog_name=None,
        complete_var=None,
        standalone_mode=True,
        **extra
    ):
        # Make sure to set the locale before calling the main method of
        # click command/group that validate if the environment is
        # good for unicode on Python 3 or not.
        self.set_locale_env()
        super(CommandMixin, self).main(
            args=args,
            prog_name=prog_name,
            complete_var=complete_var,
            standalone_mode=standalone_mode,
            **extra
        )

    @staticmethod
    def set_locale_env():
        # inspired by how click library handle unicode for python 3 environment
        # https://github.com/pallets/click/blob/7.1.2/src/click/_unicodefun.py
        try:
            encoding = codecs.lookup(locale.getpreferredencoding()).name
        except Exception:
            encoding = 'ascii'
        if encoding == 'ascii':
            if os.name == "posix":
                try:
                    locales = subprocess.Popen(
                        ["locale", "-a"], stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    ).communicate()[0]
                except OSError:
                    locales = b""

                if isinstance(locales, bytes):
                    locales = locales.decode("ascii", "replace")

                local_to_set = None
                for line in locales.splitlines():
                    locale_env = line.strip()
                    if locale_env.lower() in (
                            "en_us.utf8",
                            "en_us.utf-8",
                            "c.utf8",
                            "c.utf-8"
                    ):
                        local_to_set = locale_env
                    if local_to_set:
                        os.environ['LC_ALL'] = local_to_set
                        os.environ['LANG'] = local_to_set
                        break


class AliasedGroup(CommandMixin, click.Group):
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

    def group(self, *a, **kw):
        kw.setdefault('cls', self.__class__)
        return super(AliasedGroup, self).group(*a, **kw)


def group(name):
    """Allow to create a group with a default click context
    and a cls for click's `didyoueamn` without having to repeat
    it for every group.
    """
    return click.group(
        name=name,
        context_settings=CLICK_CONTEXT_SETTINGS,
        cls=AliasedGroup)


class CommandWithLoggers(CommandMixin, click.Command):
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

        self.runtime_properties = click.option(
            '-p',
            '--properties',
            required=True,
            multiple=True,
            callback=properties_callback,
            help=helptexts.RUNTIME_PROPERTIES)

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

        self.override_collisions = click.option(
            '--override-collisions',
            is_flag=True,
            help=helptexts.OVERRIDE_COLLISIONS
        )

        self.tenant_map = click.option(
            '-m',
            '--tenant-map',
            type=click.Path(exists=True),
            help=helptexts.TENANT_MAP
        )

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

        self.skip_drift_check = click.option(
            '--skip-drift-check',
            is_flag=True,
            help=helptexts.SKIP_DRIFT_CHECK)

        self.force_reinstall = click.option(
            '--force-reinstall',
            is_flag=True,
            help=helptexts.FORCE_REINSTALL)

        self.skip_heal = click.option(
            '--skip-heal',
            is_flag=True,
            help=helptexts.SKIP_HEAL)

        self.dont_skip_reinstall = click.option(
            '--dont-skip-reinstall',
            is_flag=True,
            help=helptexts.DONT_SKIP_REINSTALL)

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

        self.extended_view = click.option(
            '-x',
            '--extended-view',
            is_flag=True,
            expose_value=False,
            default=None,
            help=helptexts.EXTENDED_VIEW,
            callback=set_extended_view)

        self.dont_update_plugins = click.option(
            '--dont-update-plugins',
            is_flag=True,
            help=helptexts.DONT_UPDATE_PLUGINS)

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

        self.profile_manager_ip = click.option(
            '-m', '--manager-ip',
            help=helptexts.PROFILE_MANAGER_IP,
        )

        self.manager_token = click.option(
            '-T',
            '--manager-token',
            required=False,
            help=helptexts.MANAGER_TOKEN,
        )

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
            callback=parse_on_off,
        )

        self.ssh_port = click.option(
            '--ssh-port',
            required=False,
            help=helptexts.SSH_PORT)

        self.rest_port = click.option(
            '--rest-port',
            required=False,
            help=helptexts.REST_PORT,
            type=int)

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

        self.encryption_passphrase = click.option(
            '-p',
            '--passphrase',
            required=False,
            help=helptexts.ENCRYPTION_PASSPHRASE,
            callback=validate_encryption_passphrase
        )

        self.visibility_filter = click.option(
            '-l',
            '--visibility',
            required=False,
            help=helptexts.VISIBILITY_FILTER.format(VisibilityState.STATES)
        )

        self.filter_by = click.option(
            '--filter-by',
            required=False,
            help=helptexts.FILTER_BY_KEYWORD
        )

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

        self.secret_schema = click.option(
            '--schema',
            'secret_schema',
            required=False,
            default=None,
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['dict', 'list'],
            help=helptexts.SECRET_SCHEMA)

        self.secret_flag_dict = click.option(
            '--dict',
            'secret_flag_dict',
            is_flag=True,
            default=False,
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['schema', 'list'],
            help=helptexts.SECRET_FLAG_DICT)

        self.secret_flag_list = click.option(
            '--list',
            'secret_flag_list',
            is_flag=True,
            default=False,
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['schema', 'dict'],
            help=helptexts.SECRET_FLAG_LIST)

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

        self.tempdir_path = click.option(
            '--tempdir-path',
            help=helptexts.TEMPDIR_PATH
        )

        self.legacy = click.option(
            '--legacy/--no-legacy',
            is_flag=True,
            default=True,
            help=helptexts.LEGACY_SNAPSHOT
        )

        self.listener_timeout = click.option(
            '--listener-timeout',
            type=float,
            help=helptexts.SNAPSHOT_LISTENER_TIMEOUT,
        )

        self.wait_for_status = click.option(
            '-w',
            '--wait-for-status',
            is_flag=True,
            default=False,
            help=helptexts.WAIT_FOR_STATUS
        )

        self.queue_log_bundle = click.option(
            '--queue',
            is_flag=True,
            default=False,
            help=helptexts.QUEUE_LOG_BUNDLES,
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

        self.install_agent_timeout = click.option(
            '--install-agent-timeout',
            default=300,
            type=int,
            help=helptexts.INSTALL_AGENT_TIMEOUT
        )

        self.location = click.option(
            '--location',
            required=False,
            help=helptexts.LOCATION
        )

        self.site_name = click.option(
            '-s',
            '--site-name',
            required=False,
            callback=validate_name,
            help=helptexts.SITE_NAME
        )

        self.detach_site = click.option(
            '-d',
            '--detach-site',
            required=False,
            is_flag=True,
            default=False,
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['site_name'],
            help=helptexts.DETACH_SITE
        )

        self.with_logs = click.option(
            '-l',
            '--with-logs',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.WITH_LOGS
        )

        self.delete_deployments = click.option(
            '--delete-deployments',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.DELETE_GROUP_DEPLOYMENTS
        )

        self.port = click.option(
            '--port',
            required=False,
            type=click.IntRange(1, 65535),
            help=helptexts.PORT,
        )

        # Args for configuring ldap
        self.ldap_server = click.option(
            '-s',
            '--ldap-server',
            required=True,
            help=helptexts.LDAP_SERVER,
        )
        self.ldap_username = click.option(
            '-u',
            '--ldap-username',
            required=False,
            default=None,
            help=helptexts.LDAP_USERNAME,
        )
        self.ldap_password = click.option(
            '-p',
            '--ldap-password',
            required=False,
            default=None,
            help=helptexts.LDAP_PASSWORD,
        )
        self.ldap_domain = click.option(
            '-d',
            '--ldap-domain',
            required=False,
            help=helptexts.LDAP_DOMAIN,
        )
        self.ldap_is_active_directory = click.option(
            '-a',
            '--ldap-is-active-directory',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.LDAP_IS_ACTIVE_DIRECTORY,
        )
        self.ldap_dn_extra = click.option(
            '-e',
            '--ldap-dn-extra',
            required=False,
            help=helptexts.LDAP_DN_EXTRA,
        )
        self.ldap_ca_path = click.option(
            '-c',
            '--ldap-ca-path',
            required=False,
            help=helptexts.LDAP_CA_PATH,
        )
        self.ldap_base_dn = click.option(
            '--ldap-base-dn',
            required=False,
            help=helptexts.LDAP_BASE_DN,
        )
        self.ldap_group_dn = click.option(
            '--ldap-group-dn',
            required=False,
            help=helptexts.LDAP_GROUP_DN,
        )
        self.ldap_bind_format = click.option(
            '--ldap-bind-format',
            required=False,
            help=helptexts.LDAP_BIND_FORMAT,
        )
        self.ldap_user_filter = click.option(
            '--ldap-user-filter',
            required=False,
            help=helptexts.LDAP_USER_FILTER,
        )
        self.ldap_group_member_filter = click.option(
            '--ldap-group-member-filter',
            required=False,
            help=helptexts.LDAP_GROUP_MEMBER_FILTER,
        )
        self.ldap_attribute_email = click.option(
            '--ldap-attribute-email',
            required=False,
            help=helptexts.LDAP_ATTRIBUTE_EMAIL,
        )
        self.ldap_attribute_first_name = click.option(
            '--ldap-attribute-first-name',
            required=False,
            help=helptexts.LDAP_ATTRIBUTE_FIRST_NAME,
        )
        self.ldap_attribute_last_name = click.option(
            '--ldap-attribute-last-name',
            required=False,
            help=helptexts.LDAP_ATTRIBUTE_LAST_NAME,
        )
        self.ldap_attribute_uid = click.option(
            '--ldap-attribute-uid',
            required=False,
            help=helptexts.LDAP_ATTRIBUTE_UID,
        )
        self.ldap_attribute_group_membership = click.option(
            '--ldap-attribute-group-membership',
            required=False,
            help=helptexts.LDAP_ATTRIBUTE_GROUP_MEMBERSHIP,
        )
        self.ldap_nested_levels = click.option(
            '--ldap-nested-levels',
            required=False,
            help=helptexts.LDAP_NESTED_LEVELS,
        )

        self.node_id = click.option(
            '--node-id',
            required=False,
            help=helptexts.NODE_ID,
        )

        self.runtime_only_evaluation = click.option(
            '--runtime-only-evaluation',
            is_flag=True,
            default=False,
            required=False,
            help=helptexts.RUNTIME_ONLY_EVALUATION)

        self.auto_correct_types = click.option(
            '--auto-correct-types',
            is_flag=True,
            default=False,
            required=False,
            help=helptexts.AUTO_CORRECT_TYPES)

        self.manager = click.option(
            '--manager',
            required=False,
            expose_value=False,
            help=helptexts.MANAGER,
            callback=set_manager)

        self.all_blueprints = click.option(
            '--all-blueprints',
            'all_blueprints',
            is_flag=True,
            default=False,
            help=helptexts.PLUGINS_UPDATE_ALL)

        self.except_blueprints = click.option(
            '--except-blueprint',
            'except_blueprints',
            multiple=True,
            required=False,
            help=helptexts.PLUGINS_UPDATE_EXCEPT_BLUEPRINT,
            callback=self.parse_comma_separated)

        self.plugin_names = click.option(
            '--plugin-name',
            'plugin_names',
            multiple=True,
            required=False,
            help=helptexts.PLUGINS_UPDATE_NAME,
            callback=self.parse_comma_separated)

        self.plugins_to_latest = click.option(
            '--to-latest',
            multiple=True,
            required=False,
            help=helptexts.PLUGINS_UPDATE_TO_LATEST,
            callback=self.parse_comma_separated)

        self.plugins_all_to_latest = click.option(
            '--all-to-latest',
            is_flag=True,
            default=None,
            help=helptexts.PLUGINS_UPDATE_ALL_TO_LATEST)

        self.plugins_to_minor = click.option(
            '--to-minor',
            multiple=True,
            required=False,
            help=helptexts.PLUGINS_UPDATE__TO_MINOR,
            callback=self.parse_comma_separated)

        self.plugins_all_to_minor = click.option(
            '--all-to-minor',
            is_flag=True,
            default=None,
            help=helptexts.PLUGINS_UPDATE_ALL_TO_MINOR)

        self.labels = click.option(
            '--labels',
            required=False,
            callback=parse_and_validate_labels,
            help=helptexts.LABELS
        )
        self.deployment_labels = click.option(
            '--deployment-labels',
            required=False,
            callback=parse_and_validate_labels,
            help=helptexts.LABELS
        )
        self.blueprint_labels = click.option(
            '--blueprint-labels',
            required=False,
            callback=parse_and_validate_labels,
            help=helptexts.LABELS
        )
        self.async_upload = click.option(
            '-a',
            '--async-upload',
            is_flag=True,
            default=False,
            help=helptexts.ASYNC_UPLOAD,
        )

        self.schedule_name = click.option(
            '-n',
            '--schedule-name',
            required=False,
            help=helptexts.SCHEDULE_NAME)

        self.recurrence = click.option(
            '-r',
            '--recurrence',
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['rrule'],
            required=False,
            help=helptexts.SCHEDULE_RECURRENCE
        )

        self.tz = click.option(
            '--tz',
            required=False,
            help=helptexts.TIMEZONE
        )

        self.count = click.option(
            '-c',
            '--count',
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['rrule'],
            required=False,
            type=int,
            help=helptexts.SCHEDULE_COUNT
        )

        self.weekdays = click.option(
            '--weekdays',
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['rrule'],
            required=False,
            help=helptexts.SCHEDULE_WEEKDAYS,
            multiple=True,
            callback=self.parse_comma_separated,
        )

        self.rrule = click.option(
            '--rrule',
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['recurrence', 'count', 'weekdays'],
            required=False,
            help=helptexts.SCHEDULE_RRULE
        )

        self.slip = click.option(
            '--slip',
            required=False,
            default=0,
            type=int,
            help=helptexts.SCHEDULE_SLIP
        )

        self.stop_on_fail = click.option(
            '--stop-on-fail',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.SCHEDULE_STOP_ON_FAIL
        )

        self.group_default_blueprint = click.option(
            '--default-blueprint', '-b',
            help=helptexts.DEP_GROUP_BLUEPRINT
        )

        self.group_description = click.option(
            '--description',
            help=helptexts.DEP_GROUP_DESCRIPTION
        )

        self.group_deployment_id = click.option(
            '--deployment-id', '-d',
            help=helptexts.DEP_GROUP_DEP_ID,
            multiple=True
        )

        self.group_count = click.option(
            '--count',
            help=helptexts.DEP_GROUP_COUNT,
            type=int
        )

        self.deployment_group_filter_id = click.option(
            '--filter-id',
            help=helptexts.DEP_GROUP_FILTER_ID
        )

        self.deployment_group_deployments_from_group = click.option(
            '--from-group',
            help=helptexts.DEP_GROUP_FROM_GROUP,
        )

        self.into_environments_group = click.option(
            '--into-environments', 'environments_group',
            help=helptexts.DEP_GROUP_INTO_ENVIRONMENTS,
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['count'],
        )

        self.deployment_group_id = click.option(
            '-g', '--deployment-group-id',
            help=helptexts.DEP_GROUP_ID,
        )

        self.group_id_filter = click.option(
            '--group-id',
            help=helptexts.GROUP_ID_FILTER,
        )

        self.filter_id = click.option(
            '--filter-id',
            callback=validate_name,
            help=helptexts.FILTER_ID
        )

        self.generate_id = click.option(
            '--generate-id',
            is_flag=True,
            default=False,
            help=helptexts.GENERATE_ID
        )

        self.display_name = click.option(
            '-n',
            '--display-name',
            callback=validate_value_not_empty,
            help=helptexts.DISPLAY_NAME
        )

        self.search_name = click.option(
            '--search-name',
            callback=validate_value_not_empty,
            help=helptexts.SEARCH_NAME
        )

        self.dependencies_of = click.option(
            '--dependencies-of',
            callback=validate_value_not_empty,
            help=helptexts.DEPENDENCIES_OF
        )

        self.execution_group_concurrency = click.option(
            '--concurrency',
            type=int,
            default=5,
            help=helptexts.EXECUTION_GROUP_CONCURRENCY
        )

        self.worker_names = click.option(
            '-w', '--with-worker-names/--without-worker-names',
            'with_worker_names',
            is_flag=True,
            help=helptexts.WORKER_NAMES,
            default=False,
        )

        self.drift_only = click.option(
            '--drift-only',
            is_flag=True,
            help=helptexts.DRIFT_ONLY,
            default=False,
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['blueprint_id', 'blueprint_path', 'inputs'],
        )

        self.secrets_provider_name = click.option(
            '--name',
            'secrets_provider_name',
            required=True,
            callback=validate_value_not_empty,
            help=helptexts.SECRETS_PROVIDER_NAME,
        )

        self.provider_name = click.option(
            '-p',
            '--provider',
            'provider_name',
            required=False,
            callback=validate_value_not_empty,
            help=helptexts.SECRETS_PROVIDER_NAME,
        )

        self.evaluate_functions = click.option(
            '--evaluate-functions',
            is_flag=True,
            default=False,
            required=False,
            help=helptexts.EVALUATE_FUNCTIONS,
        )
        self.recursive_delete = click.option(
            '--recursive',
            default=False,
            is_flag=True,
            help=helptexts.RECURSIVE_DELETE,
        )

    def common_options(self, f):
        """A shorthand for applying commonly used arguments.

        To be used for arguments that are going to be applied for all or
        almost all commands.
        """
        for arg in [self.manager, self.json, self.format,
                    self.verbose(), self.quiet()]:
            f = arg(f)
        return f

    def local_common_options(self, f):
        """A shorthand for applying commonly used arguments for local profiles.

        Similar to common_options, but doesn't apply the options that are only
        relevant to managers.
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
        node_instance_id = click.option(
            '--node-instance-id',
            multiple=True,
            help=helptexts.AGENT_NODE_INSTANCE_ID,
            callback=self.parse_comma_separated,
        )
        node_id = click.option(
            '--node-id',
            multiple=True,
            help=helptexts.AGENT_NODE_ID,
            callback=self.parse_comma_separated,
        )
        install_method = click.option(
            '--install-method',
            multiple=True,
            help=helptexts.AGENT_INSTALL_METHOD,
            callback=self.parse_comma_separated,
        )
        deployment_id = click.option(
            '--deployment-id',
            multiple=True,
            help=helptexts.AGENT_DEPLOYMENT_ID,
            callback=self.parse_comma_separated,
        )
        all_states = click.option(
            '--all-states',
            default=False,
            is_flag=True,
            help=helptexts.AGENT_ALL_STATES,
        )

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

                if not kwargs.pop('all_states', False):
                    filters['state'] = [AgentState.STARTED]
                kwargs['agent_filters'] = filters
                return f(*args, **kwargs)
            return _inner

        for arg in [install_method, node_instance_id, node_id,
                    deployment_id, all_states, _filters_deco]:
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
    def blueprint_icon_path(required=False):
        return click.option(
            '-i',
            '--icon-path',
            required=required,
            help=helptexts.BLUEPRINT_ICON_PATH)

    @staticmethod
    def workflow_id(default=None, required=False):
        return click.option(
            '-w',
            '--workflow-id',
            default=default,
            required=required,
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
    def blueprint_id(
        required=False,
        validate=False,
        help=helptexts.BLUEPRINT_ID,
    ):
        return click.option(
            '-b',
            '--blueprint-id',
            required=required,
            help=help,
            callback=_get_validate_callback(validate))

    @staticmethod
    def blueprint_path(required=False,
                       extra_message='',
                       exists=True):
        return click.option(
            '-p',
            '--blueprint-path',
            required=required,
            type=click.Path(exists=exists),
            help=helptexts.BLUEPRINT_PATH + extra_message)

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
            multiple=True,
            help=helptexts.PLUGIN_YAML_PATH)

    @staticmethod
    def plugin_icon_path():
        return click.option(
            '-i',
            '--icon-path',
            required=False,
            help=helptexts.PLUGIN_ICON_PATH)

    @staticmethod
    def plugin_title():
        return click.option(
            '--title',
            required=False,
            help=helptexts.PLUGIN_TITLE)

    @staticmethod
    def new_name(resource_name_for_help=None):
        return click.option(
            '-n',
            '--new-name',
            required=False,
            help=helptexts.NEW_NAME.format(resource_name_for_help),
            callback=validate_name
        )

    def networks(self, required=True):
        return click.option(
            '-n',
            '--networks',
            required=required,
            multiple=True,
            callback=inputs_callback,
            help=helptexts.NETWORKS
        )

    @staticmethod
    def input_path(required=False, help=helptexts.INPUT_PATH):
        return click.option(
            '-i',
            '--input-path',
            required=required,
            help=help
        )

    @staticmethod
    def import_input_path():
        return click.option(
            '-i',
            '--input-path',
            required=True,
            type=click.Path(exists=True),
            help=helptexts.IMPORT_SECRETS
        )

    @staticmethod
    def non_encrypted():
        return click.option(
            '--non-encrypted',
            cls=MutuallyExclusiveOption,
            mutually_exclusive=['passphrase'],
            is_flag=True,
            default=False,
            help=helptexts.NON_ENCRYPTED
        )

    @staticmethod
    def from_datetime(required=False, mutually_exclusive_with=None,
                      help=helptexts.FROM_DATETIME):
        kwargs = {
            'required': required,
            'type': Timestamp((
                '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f',)),
            'help': help,
        }
        if mutually_exclusive_with:
            kwargs['cls'] = MutuallyExclusiveOption
            kwargs['mutually_exclusive'] = mutually_exclusive_with
        return click.option('from_datetime', '--from', **kwargs)

    @staticmethod
    def to_datetime(required=False, mutually_exclusive_with=None,
                    help=helptexts.TO_DATETIME):
        kwargs = {
            'required': required,
            'type': Timestamp((
                '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f',)),
            'help': help,
        }
        if mutually_exclusive_with:
            kwargs['cls'] = MutuallyExclusiveOption
            kwargs['mutually_exclusive'] = mutually_exclusive_with
        return click.option('to_datetime', '--to', **kwargs)

    @staticmethod
    def since(required=False, mutually_exclusive_with=None, help_lead=None):
        help_lead = help_lead or 'The earliest possible time to run'
        kwargs = {
            'required': required,
            'type': str,
            'expose_value': True,
            'help': helptexts.TIME_EXPRESSION.format(help_lead),
        }
        if mutually_exclusive_with:
            kwargs['cls'] = MutuallyExclusiveOption
            kwargs['mutually_exclusive'] = mutually_exclusive_with
        return click.option('-s', '--since', **kwargs)

    @staticmethod
    def until(required=False, mutually_exclusive_with=None, help_lead=None):
        help_lead = help_lead or 'The latest possible time to run'
        kwargs = {
            'required': required,
            'type': str,
            'expose_value': True,
            'help': helptexts.TIME_EXPRESSION.format(help_lead),
        }
        if mutually_exclusive_with:
            kwargs['cls'] = MutuallyExclusiveOption
            kwargs['mutually_exclusive'] = mutually_exclusive_with
        return click.option('-u', '--until', **kwargs)

    @staticmethod
    def before(required=False,
               mutually_exclusive_with=None,
               help=helptexts.BEFORE):
        kwargs = {
            'required': required,
            'type': str,
            'callback': _parse_relative_datetime,
            'expose_value': True,
            'help': help,
        }
        if mutually_exclusive_with:
            kwargs['cls'] = MutuallyExclusiveOption
            kwargs['mutually_exclusive'] = mutually_exclusive_with
        return click.option('--before', **kwargs)

    @staticmethod
    def keep_last(resource_name,
                  required=False,
                  mutually_exclusive_with=None):
        kwargs = {
            'required': required,
            'type': click.IntRange(min=1),
            'help': helptexts.KEEP_LAST.format(resource_name),
        }
        if mutually_exclusive_with:
            kwargs['cls'] = MutuallyExclusiveOption
            kwargs['mutually_exclusive'] = mutually_exclusive_with
        return click.option('--keep-last', **kwargs)

    @staticmethod
    def store_before(default=False):
        return click.option(
            '--store-before',
            is_flag=True,
            default=default,
            help=helptexts.STORE_BEFORE_DELETION
        )

    @staticmethod
    def store_output_path():
        return click.option(
            '-o',
            '--output-path',
            required=False,
            type=click.Path(file_okay=True, dir_okay=False),
            help=helptexts.STORE_OUTPUT_PATH
        )

    @staticmethod
    def manager_tenant(default=None):
        return click.option(
            '-t',
            '--manager-tenant',
            required=False,
            help=helptexts.MANAGER_TENANT,
            callback=validate_name,
            default=default
        )

    @staticmethod
    def reevaluate_active_statuses(
            help=helptexts.REEVALUATE_ACTIVE_STATUSES):
        return click.option(
            '--reevaluate-active-statuses',
            is_flag=True,
            default=False,
            required=False,
            help=help)

    @staticmethod
    def new_username(required=True):
        return click.option(
            '-s',
            '--username',
            required=required,
            help=helptexts.SET_USERNAME)

    @staticmethod
    def _filter_rules(f, resource):
        help_text = (helptexts.DEPLOYMENTS_ATTRS_FILTER_RULES if
                     resource == 'deployment' else
                     helptexts.BLUEPRINTS_ATTRS_FILTER_RULES)
        attrs_rule = click.option(
            '-ar',
            '--attrs-rule',
            callback=parse_attributes_filter_rules,
            help=help_text,
            multiple=True
        )

        labels_rule = click.option(
            '-lr',
            '--labels-rule',
            callback=parse_labels_filter_rules,
            help=helptexts.LABELS_FILTER_RULES,
            multiple=True
        )

        def _filter_rules_deco(f):
            @wraps(f)
            def _inner(*args, **kwargs):
                filter_rules = get_filter_rules(
                    kwargs.pop('labels_rule', None),
                    kwargs.pop('attrs_rule', None))

                kwargs['filter_rules'] = filter_rules
                return f(*args, **kwargs)
            return _inner

        for arg in [attrs_rule, labels_rule, _filter_rules_deco]:
            f = arg(f)

        return f

    def blueprint_filter_rules(self, f):
        return self._filter_rules(f, 'blueprint')

    def deployment_filter_rules(self, f):
        return self._filter_rules(f, 'deployment')

    @staticmethod
    def secrets_provider_type(
            required=True,
            _help=None,
            default=None,
            callback=validate_value_not_empty,
    ):
        args = [
            '-y',
            '--type',
            'secrets_provider_type',
        ]
        kwargs = {
            'required': required,
            'help': _help or helptexts.SECRETS_PROVIDER_TYPE,
            'callback': callback,
        }

        if default is not None:
            kwargs['default'] = default

        return click.option(*args, **kwargs)

    @staticmethod
    def secrets_provider_skip_check():
        return click.option(
            '-s',
            '--skip-check',
            is_flag=True,
            default=False,
            required=False,
            help=helptexts.SECRETS_PROVIDER_SKIP_CHECK,
        )

    @staticmethod
    def connection_parameters(required=True, _help=None, default=None):
        args = [
            '-c',
            '--connection-parameters',
        ]
        kwargs = {
            'required': required,
            'help': _help or helptexts.SECRETS_PROVIDER_CONNECTION_PARAMETERS,
            'callback': inputs_callback,
            'multiple': True,
            'default': default,
        }

        return click.option(*args, **kwargs)

    @staticmethod
    def provider_options(required=True, _help=None, default=None):
        args = [
            '-o',
            '--provider-options',
        ]
        kwargs = {
            'required': required,
            'help': _help or helptexts.SECRETS_PROVIDER_OPTIONS,
            'callback': inputs_callback,
            'multiple': True,
            'default': default,
        }

        return click.option(*args, **kwargs)

    @staticmethod
    def provider_multiple(required=False, _help=None, default=None):
        args = [
            '-p',
            '--provider',
            'provider',
        ]
        kwargs = {
            'required': required,
            'help': _help or helptexts.SECRETS_PROVIDER_NAME_MULTIPLE,
            'multiple': True,
            'default': default,
        }

        return click.option(*args, **kwargs)


options = Options()


class SummaryArgs(click.Choice):
    """
    Used for correctly displaying usage of summary commands (e.g. `cfy
    blueprints summary`) in which the user must choose a field to summarize
    by from a list.
    We want  Usage: cfy blueprints summary [OPTIONS] TARGET_FIELD [SUB_FIELD]
    Not      Usage: cfy blueprints summary [OPTIONS]
                    [visibility|tenant_name] [[visibility|tenant_name]]
    """
    def get_metavar(self, param):
        pass
