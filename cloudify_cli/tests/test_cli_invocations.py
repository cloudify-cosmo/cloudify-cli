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

import argparse
import json
import tempfile
import unittest
import cli_runner

from itertools import combinations
from mock import create_autospec
from cloudify_cli import utils
from cloudify_cli import commands


TEMP_FILE = tempfile.NamedTemporaryFile()

ARG_VALUES = {
    bool: '',
    int: 1,
    file: TEMP_FILE.name,
    dict: "{\"key\":\"val\"}",
    str: 'mock_value',
    bytearray: 'mock_value1 mock_value2'
}


def get_combinations(command_path):

    def traverse(dictionary, key):
        if 'sub_commands' in dictionary:
            return dictionary['sub_commands'][key]
        return dictionary[key]

    def type_of(arg):
        if 'action' in arg and arg['action'] == 'store_true':
            return bool
        if 'type' in arg:
            if isinstance(arg['type'], argparse.FileType):
                return file
            if arg['type'] == json.loads:
                return dict
        return arg['type']

    from cloudify_cli.config.parser_config import PARSER

    reduced = reduce(traverse, command_path.split(), PARSER['commands'])
    if 'arguments' not in reduced:
        return []

    required_args = set()
    optional_args = set()
    arguments = reduced['arguments']
    for argument_name, argument in arguments.iteritems():
        possible_arguments = argument_name.split(',')
        type_of_argument = type_of(argument)

        def add_value(arg_name):
            return '{0} {1}'.format(arg_name, ARG_VALUES[type_of_argument])

        if 'required' in argument and argument['required']:
            required_args.update(map(add_value, possible_arguments))
        else:
            optional_args.update(map(add_value, possible_arguments))

    all_commands = []
    for i in range(0, len(optional_args) + 1):
        combs = set(combinations(optional_args, i))
        for combination in combs:
            command = '{0} {1} {2}'.format(
                command_path,
                ' '.join(required_args),
                ' '.join(combination))
            all_commands.append(command)
    return all_commands


def get_all_commands():

    all_commands = []
    from cloudify_cli.config.parser_config import PARSER
    for command_name, command in PARSER['commands'].iteritems():
        if 'sub_commands' in command:
            for sub_command_name in command['sub_commands'].keys():
                command_path = '{0} {1}'.format(command_name, sub_command_name)
                all_commands.append(command_path)
        else:
            all_commands.append(command_name)
    return all_commands


class CliInvocationTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # setting up the mocks.
        utils.get_management_server_ip = lambda x: 'localhost'

        # direct commands
        commands.status = create_autospec(commands.status, return_value=None)
        commands.ssh = create_autospec(commands.ssh, return_value=None)
        commands.bootstrap = create_autospec(commands.bootstrap, return_value=None)
        commands.teardown = create_autospec(commands.teardown, return_value=None)
        commands.dev = create_autospec(commands.dev, return_value=None)
        commands.init = create_autospec(commands.init, return_value=None)
        commands.use = create_autospec(commands.use, return_value=None)

        # blueprint commands
        commands.blueprints.delete = create_autospec(commands.blueprints.delete, return_value=None)
        commands.blueprints.upload = create_autospec(commands.blueprints.upload, return_value=None)
        commands.blueprints.validate = create_autospec(commands.blueprints.validate, return_value=None)
        commands.blueprints.download = create_autospec(commands.blueprints.download, return_value=None)
        commands.blueprints.list = create_autospec(commands.blueprints.download, return_value=None)

        # deployment commands
        commands.deployments.delete = create_autospec(commands.deployments.delete, return_value=None)
        commands.deployments.create = create_autospec(commands.deployments.create, return_value=None)
        commands.deployments.list = create_autospec(commands.deployments.list, return_value=None)
        commands.deployments.execute = create_autospec(commands.deployments.execute, return_value=None)

        # executions commands
        commands.executions.get = create_autospec(commands.executions.get, return_value=None)
        commands.executions.cancel = create_autospec(commands.executions.cancel, return_value=None)
        commands.executions.list = create_autospec(commands.executions.list, return_value=None)

        # events commands
        commands.events.list = create_autospec(commands.events.list, return_value=None)

        # workflows commands
        commands.workflows.get = create_autospec(commands.workflows.get, return_value=None)
        commands.workflows.list = create_autospec(commands.workflows.list, return_value=None)

    def _test_all_combinations(self, command_path):
        possible_commands = get_combinations(command_path)
        for command in possible_commands:
            cli_runner.run_cli('cfy {0}'.format(command))

    def test_all_commands(self):

        """
        Run all commands.
        """

        all_commands = get_all_commands()
        for command in all_commands:
            possible_commands = get_combinations(command)
            for possible_command in possible_commands:
                cli_runner.run_cli('cfy {0}'.format(possible_command))

    def test_all_commands_help(self):

        """
        Run all commands with 'help' flags.
        """

        all_commands = get_all_commands()
        for command in all_commands:
            cli_runner.run_cli_expect_system_exit_0('cfy {0} -h'.format(command))
            cli_runner.run_cli_expect_system_exit_0('cfy {0} --help'.format(command))

    def test_all_commands_verbose(self):

        """
        Run all commands with 'verbosity' flags.
        """

        all_commands = get_all_commands()
        for command in all_commands:
            possible_commands = get_combinations(command)
            for possible_command in possible_commands:
                cli_runner.run_cli('cfy {0}'.format(possible_command))
                cli_runner.run_cli('cfy {0} -v'.format(possible_command))
                cli_runner.run_cli('cfy {0} --verbose'.format(possible_command))
