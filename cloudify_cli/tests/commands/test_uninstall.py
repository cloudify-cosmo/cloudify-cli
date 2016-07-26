########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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
Tests 'cfy uninstall'
"""

from mock import patch

from cloudify_rest_client.deployments import Deployment

from .test_cli_command import CliCommandTest

from ...constants import DEFAULT_TIMEOUT
from ...constants import DEFAULT_PARAMETERS
from ...constants import DEFAULT_UNINSTALL_WORKFLOW


class UninstallTest(CliCommandTest):
    def __init__(self):
        super(UninstallTest, self).__init__()
        self.use_manager()

    @patch('cloudify_cli.commands.blueprints.delete')
    @patch('cloudify_cli.commands.deployments.delete')
    @patch('cloudify_cli.env.get_rest_client')
    @patch('cloudify_cli.commands.executions.start')
    def test_default_executions_start_arguments(self, executions_start_mock,
                                                *_):
        uninstall_command = 'cfy uninstall did'
        self.invoke(uninstall_command)

        executions_start_mock.assert_called_with(
            workflow_id=DEFAULT_UNINSTALL_WORKFLOW,
            deployment_id='did',
            timeout=DEFAULT_TIMEOUT,
            force=False,
            include_logs=False,
            allow_custom_parameters=False,
            parameters=DEFAULT_PARAMETERS,
            json=False
        )

    @patch('cloudify_cli.commands.blueprints.delete')
    @patch('cloudify_cli.commands.deployments.delete')
    @patch('cloudify_cli.env.get_rest_client')
    @patch('cloudify_cli.commands.executions.start')
    def test_custom_executions_start_arguments(self,
                                               executions_start_mock, *_
                                               ):
        uninstall_command = 'cfy uninstall ' \
                            '-w my_uninstall ' \
                            '-d did ' \
                            '--timeout 1987 ' \
                            '--allow-custom-parameters ' \
                            '--include-logs ' \
                            '--parameters key=value ' \
                            '--json'

        self.invoke(uninstall_command)

        executions_start_mock.assert_called_with(
            workflow_id='my_uninstall',
            deployment_id='did',
            timeout=1987,
            force=False,
            include_logs=True,
            allow_custom_parameters=True,
            parameters=["key=value"],
            json=True
        )

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.delete')
    @patch('cloudify_cli.commands.blueprints.delete')
    def test_getting_blueprint_id_from_deployment(self,
                                                  mock_blueprints_delete,
                                                  *_):

        def mock_deployments_get(*args, **kwargs):
            return Deployment({'blueprint_id': 'bid'})

        self.client.deployments.get = mock_deployments_get

        self.invoke('cfy uninstall did')
        mock_blueprints_delete.assert_called_with('bid')

    @patch('cloudify_cli.commands.blueprints.delete')
    @patch('cloudify_cli.env.get_rest_client')
    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.delete')
    def test_deployments_delete_arguments(self, deployments_delete_mock, *_):

        self.invoke('cfy uninstall did')

        deployments_delete_mock.assert_called_with('did',
                                                   ignore_live_nodes=False)

    @patch('cloudify_cli.env.get_rest_client')
    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.delete')
    @patch('cloudify_cli.commands.blueprints.delete')
    def test_blueprint_is_deleted(self, blueprints_delete_mock, *_):

        self.invoke('cfy uninstall did', context='manager')
        self.assertTrue(blueprints_delete_mock.called)
