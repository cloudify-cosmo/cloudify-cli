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

from nose.tools import nottest
from cloudify_cli.exceptions import CloudifyCliError
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
        cli_runner.run_cli('cfy init -p mock_provider')
        cli_runner.run_cli('cfy use -t 10.0.0.1')
        self._assert_ex('cfy teardown',
                        "This action requires additional confirmation.")

    def test_teardown_force_deployments(self):
        self.client.manager.get_status = MagicMock()
        self.client.deployments.list = MagicMock(return_value=[{}])
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        cli_runner.run_cli('cfy init -p mock_provider')
        cli_runner.run_cli('cfy use -t 10.0.0.1')
        self._assert_ex('cfy teardown -f --ignore-validation '
                        '-c cloudify-config.yaml',
                        'has active deployments')

    def test_teardown(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        self.client.deployments.list = MagicMock(return_value=[])
        cli_runner.run_cli('cfy init -p mock_provider -v')
        cli_runner.run_cli('cfy use -t 10.0.0.1')
        cli_runner.run_cli('cfy teardown -f')
        # the teardown should have cleared the current target management server
        self.assertEquals(
            None,
            self._read_cosmo_wd_settings().get_management_server()
        )

    def test_provider_exception(self):
        cli_runner.run_cli('cfy init -p '
                           'cloudify_mock_provider_with_cloudify_prefix -v')

        try:
            self.client.manager.get_status = MagicMock()
            self.client.manager.get_context = MagicMock(
                return_value={
                    'name': 'cloudify_mock_provider_with_cloudify_prefix',
                    'context': {'key': 'value'}
                }
            )
            self.client.deployments.list = MagicMock(return_value=[])
            cli_runner.run_cli('cfy use -t 10.0.0.1')
            cli_runner.run_cli('cfy teardown -f')
            self.fail('Expected CloudifyCliError')
        except CloudifyCliError as e:
            self.assertIn('cloudify_mock_provider_with_cloudify_prefix'
                          ' teardown exception',
                          e.message)
