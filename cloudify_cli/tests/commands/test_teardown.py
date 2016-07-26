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

from mock import patch

from cloudify_rest_client.exceptions import CloudifyClientError

from .test_blueprints import MagicMock
from .test_cli_command import CliCommandTest


class TeardownTest(CliCommandTest):

    def test_teardown_no_force(self):
        self.invoke('cfy teardown',
                    'This action requires additional confirmation.')

    @patch('cloudify_cli.bootstrap.bootstrap.teardown')
    def test_teardown_has_existing_deployments_ignore_deployments(self, mock_teardown):  # NOQA
        self.client.manager.get_status = MagicMock()
        self.client.deployments.list = MagicMock(return_value=[{}])
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        self.invoke('cfy use 10.0.0.1')
        self.invoke('cfy teardown -f --ignore-deployments')
        # TODO: The values are the values of the task-retry flags.
        # These should be retrieved from somewhere else.
        mock_teardown.assert_called_once_with(
            task_retries=0,
            task_retry_interval=1,
            task_thread_pool_size=1
        )

    def test_teardown_has_existing_deployments_dont_ignore_deployments(self):
        self.client.manager.get_status = MagicMock()
        self.client.deployments.list = MagicMock(return_value=[{}])
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        self.invoke('cfy use 10.0.0.1')
        self.invoke('cfy teardown -f',
                    'has existing deployments')

    def test_teardown_manager_down_dont_ignore_deployments(self):
        self.client.manager.get_status = MagicMock()

        def raise_client_error():
            raise CloudifyClientError('CloudifyClientError')

        self.client.deployments.list = raise_client_error
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        self.invoke('cfy use 10.0.0.1')
        self.invoke('cfy teardown -f',
                    'The manager may be down')

    @patch('cloudify_cli.bootstrap.bootstrap.teardown')
    def test_teardown_manager_down_ignore_deployments(self, mock_teardown):
        def raise_client_error():
            raise CloudifyClientError('this is an IOError')

        self.client.deployments.list = raise_client_error
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )

        self.use_manager(host='10.0.0.1')

        self.invoke('cfy teardown -f --ignore-deployments')
        mock_teardown.assert_called_once_with(
            task_retries=0,
            task_retry_interval=1,
            task_thread_pool_size=1
        )

    # TODO: Not sure we're checking the right things here
    @patch('cloudify_cli.bootstrap.bootstrap.teardown')
    def test_teardown_no_management_ip_in_context_right_directory(
            self, mock_teardown):  # NOQA

        def mock_client_list():
            return list()

        self.client.deployments.list = mock_client_list

        self.use_manager(host='10.0.0.1')

        self.invoke('cfy teardown -f')
        mock_teardown.assert_called_once_with(
            task_retries=0,
            task_retry_interval=1,
            task_thread_pool_size=1
        )
