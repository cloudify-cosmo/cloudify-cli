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
Tests 'cfy teardown'
"""

from cloudify_cli.tests.commands.test_blueprints import MagicMock
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class TeardownTest(CliCommandTest):

    def test_teardown_no_force(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        self.client.deployments.list = MagicMock(return_value=[])
        cli_runner.run_cli('cfy init')
        cli_runner.run_cli('cfy use -t 10.0.0.1')
        self._assert_ex('cfy teardown',
                        "This action requires additional confirmation.")

    def test_teardown_force_deployments(self):
        self.client.manager.get_status = MagicMock()
        self.client.deployments.list = MagicMock(return_value=[{}])
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        cli_runner.run_cli('cfy init')
        cli_runner.run_cli('cfy use -t 10.0.0.1')
        self._assert_ex('cfy teardown -f',
                        'has existing deployments')

    def test_teardown_no_manager(self):
        self.client.manager.get_status = MagicMock()

        def raise_ioerror():
            raise IOError('this is an IOError')

        self.client.deployments.list = raise_ioerror
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        cli_runner.run_cli('cfy init')
        cli_runner.run_cli('cfy use -t 10.0.0.1')
        self._assert_ex('cfy teardown -f',
                        'The Manager server may be down')
