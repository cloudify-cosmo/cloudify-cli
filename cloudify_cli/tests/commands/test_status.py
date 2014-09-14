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
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

"""
Tests 'cfy status'
"""

import os

from mock import MagicMock
from cloudify_cli import utils
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class StatusTest(CliCommandTest):

    def test_status_command(self):
        self._create_cosmo_wd_settings()
        self.client.manager.get_status = MagicMock()
        cli_runner.run_cli('cfy status')

    def test_status_no_management_server_defined(self):
        # running a command which requires a target management server without
        # first calling "cfy use" or providing a target server explicitly
        cli_runner.run_cli('cfy init -p mock_provider')
        self._assert_ex('cfy status', "Must either first run 'cfy use' command")

    def test_status_command_from_inner_dir(self):
        self.client.manager.get_status = MagicMock()
        self._create_cosmo_wd_settings()
        cwd = utils.get_cwd()
        new_dir = os.path.join(cwd, 'test_command_from_inner_dir')
        os.mkdir(new_dir)
        utils.get_cwd = lambda: new_dir
        cli_runner.run_cli('cfy status')

    def test_status_command_from_outer_dir(self):
        self._create_cosmo_wd_settings()
        cwd = utils.get_cwd()
        new_dir = os.path.dirname(cwd)
        utils.get_cwd = lambda: new_dir
        self._assert_ex('cfy status',
                        'Cannot find .cloudify in {0}, '
                        'or in any of its parent directories'
                        .format(new_dir))
