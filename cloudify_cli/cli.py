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

import StringIO
import argparse
import logging
import sys
import traceback
import argcomplete

from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify_cli.constants import CLOUDIFY_REST_CLIENT_LOGGER_NAME
from cloudify_cli.exceptions import SuppressedCloudifyCliError
from cloudify_cli.exceptions import CloudifyBootstrapError
from cloudify_cli.logger import set_logger_handlers

output_level = logging.INFO
verbose_output = False


def main():
    _set_cli_except_hook()
    args = _parse_args(sys.argv[1:])
    args.handler(args)


def _parse_args(args):
    """
    Parses the arguments using the Python argparse library.
    Generates shell autocomplete using the argcomplete library.

    :param list args: arguments from cli
    :rtype: `python argument parser`
    """

    parser = register_commands()

    argcomplete.autocomplete(parser)
    parsed = parser.parse_args(args)
    set_global_verbosity_level(parsed.verbosity)
    return parsed


def register_commands():

    from cloudify_cli.config.parser_config import parser_config
    parser_conf = parser_config()

    parser = argparse.ArgumentParser(description=parser_conf['description'])

    # Direct arguments for the 'cfy' command (like -v)
    for argument_name, argument in parser_conf['arguments'].iteritems():
        parser.add_argument(argument_name, **argument)

    subparsers = parser.add_subparsers()

    for command_name, command in parser_conf['commands'].iteritems():

        if 'sub_commands' in command:

            # Add sub commands. Such as 'cfy blueprints list',
            # 'cfy deployments create' ...
            controller_help = command['help']
            controller_parser = subparsers.add_parser(
                command_name, help=controller_help
            )
            controller_subparsers = controller_parser.add_subparsers()
            for controller_sub_command_name, controller_sub_command in \
                    command['sub_commands'].iteritems():
                register_command(controller_subparsers,
                                 controller_sub_command_name,
                                 controller_sub_command)
        else:

            # Add direct commands. Such as 'cfy status', 'cfy ssh' ...
            register_command(subparsers, command_name, command)

    return parser


def register_command(subparsers, command_name, command):

    command_help = command['help']
    command_parser = subparsers.add_parser(
        command_name, help=command_help
    )
    command_arg_names = []
    if 'arguments' in command:
        for argument_name, argument in command['arguments'].iteritems():
            completer = argument.get('completer')
            if completer:
                del argument['completer']

            arg = command_parser.add_argument(
                *argument_name.split(','),
                **argument
            )

            if completer:
                arg.completer = completer

            command_arg_names.append(argument['dest'])

    # Add verbosity flag for each command
    command_parser.add_argument(
        '-v', '--verbose',
        dest='verbosity',
        action='store_true',
        help='A flag for setting verbose output'
    )

    def command_cmd_handler(args):
        kwargs = {}
        for arg_name in command_arg_names:
            # Filter verbosity since it accessed globally
            # and not via the method signature.
            if hasattr(args, arg_name):
                arg_value = getattr(args, arg_name)
                kwargs[arg_name] = arg_value

        command['handler'](**kwargs)

    command_parser.set_defaults(handler=command_cmd_handler)


def set_global_verbosity_level(is_verbose_output):
    """
    sets the global verbosity level for console and the lgr logger.

    :param bool is_verbose_output: should be output be verbose
    :rtype: `None`
    """
    # we need both lgr.setLevel and the verbose_output parameter
    # since not all output is generated at the logger level.
    # verbose_output can help us control that.
    global verbose_output
    global output_level
    from cloudify_cli.logger import lgr

    verbose_output = is_verbose_output
    if verbose_output:
        set_logger_handlers(CLOUDIFY_REST_CLIENT_LOGGER_NAME, logging.DEBUG)
        output_level = logging.DEBUG
        lgr.setLevel(logging.DEBUG)
    else:
        output_level = logging.INFO
        lgr.setLevel(logging.INFO)


def get_global_verbosity():
    """
    Returns the globally set verbosity
    :return:
    """
    global verbose_output
    return verbose_output


def _set_cli_except_hook():

    from cloudify_cli.logger import lgr

    def recommend(possible_solutions):
        lgr.info('Possible solutions:')
        for solution in possible_solutions:
            lgr.info('  - {0}'.format(solution))

    def new_excepthook(tpe, value, tb):
        prefix = tpe.__name__
        server_traceback = None
        output_message = True
        output_traceback = output_level <= logging.DEBUG
        if issubclass(tpe, CloudifyClientError):
            server_traceback = value.server_traceback
            # this means we made a server call and it failed.
            # we should include this information in the error
            prefix = 'An error occurred on the server'.format(prefix)
        if issubclass(tpe, SuppressedCloudifyCliError):
            output_message = False
        if issubclass(tpe, CloudifyBootstrapError):
            output_message = False
        if output_traceback:
            s_traceback = StringIO.StringIO()
            traceback.print_exception(
                etype=tpe,
                value=value,
                tb=tb,
                file=s_traceback)
            lgr.error(s_traceback.getvalue())
            if server_traceback:
                lgr.error('Server Traceback (most recent call last):')

                # No need for print_tb since this exception
                # is already formatted by the server
                lgr.error(server_traceback)
        if output_message and not output_traceback:
            # if we output the traceback
            # we output the message too.
            # print_exception does that.
            # here we just want the message (non verbose)
            lgr.error('{0}: {1}'.format(prefix, value))
        if hasattr(value, 'possible_solutions'):
            recommend(getattr(value, 'possible_solutions'))

    sys.excepthook = new_excepthook


if __name__ == '__main__':
    main()
