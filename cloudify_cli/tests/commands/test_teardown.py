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

from mock import patch

from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify_cli.utils import update_wd_settings
from cloudify_cli.tests.commands.test_blueprints import MagicMock
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class TeardownTest(CliCommandTest):

    def test_teardown_no_force(self):
        self._assert_ex('cfy teardown',
                        "This action requires additional confirmation.")

    @patch('cloudify_cli.bootstrap.bootstrap.teardown')
    def test_teardown_has_existing_deployments_ignore_deployments(self, mock_teardown):  # NOQA
        self.client.manager.get_status = MagicMock()
        self.client.deployments.list = MagicMock(return_value=[{}])
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        cli_runner.run_cli('cfy init')
        cli_runner.run_cli('cfy use -t 10.0.0.1')
        cli_runner.run_cli('cfy teardown -f --ignore-deployments')
        mock_teardown.assert_called_once()

    def test_teardown_has_existing_deployments_dont_ignore_deployments(self):
        self.client.manager.get_status = MagicMock()
        self.client.deployments.list = MagicMock(return_value=[{}])
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        cli_runner.run_cli('cfy init')
        cli_runner.run_cli('cfy use -t 10.0.0.1')
        self._assert_ex('cfy teardown -f',
                        'has existing deployments')

    def test_teardown_manager_down_dont_ignore_deployments(self):
        self.client.manager.get_status = MagicMock()

        def raise_client_error():
            raise CloudifyClientError('CloudifyClientError')

        self.client.deployments.list = raise_client_error
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        cli_runner.run_cli('cfy init')
        cli_runner.run_cli('cfy use -t 10.0.0.1')
        self._assert_ex('cfy teardown -f',
                        'The Manager server may be down')

    @patch('cloudify_cli.bootstrap.bootstrap.teardown')
    def test_teardown_manager_down_ignore_deployments(self, mock_teardown):

        def raise_client_error():
            raise CloudifyClientError('this is an IOError')

        self.client.deployments.list = raise_client_error
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        cli_runner.run_cli('cfy init')

        with update_wd_settings() as wd:
            wd.set_management_server('10.0.0.1')
            wd.set_provider_context({})

        cli_runner.run_cli('cfy teardown -f --ignore-deployments')
        mock_teardown.assert_called_once()

    def test_teardown_no_management_ip_in_context_wrong_directory(self):
        cli_runner.run_cli('cfy init')
        self._assert_ex('cfy teardown -f',
                        "You are attempting to execute 'teardown' "
                        "from an invalid directory")

    @patch('cloudify_cli.bootstrap.bootstrap.teardown')
    @patch('cloudify_cli.bootstrap.bootstrap.load_env')
    def test_teardown_no_management_ip_in_context_right_directory(
            self, mock_load_env, mock_teardown):  # NOQA
        cli_runner.run_cli('cfy init')

        with update_wd_settings() as wd:
            wd.set_provider_context({})

        cli_runner.run_cli('cfy teardown -f')
        mock_teardown.assert_called_once()
        mock_load_env.assert_called_once()
