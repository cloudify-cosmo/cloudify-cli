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
Tests all commands that start with 'cfy deployments'
"""

import datetime

from mock import MagicMock
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest
from cloudify_rest_client.deployments import Deployment, DeploymentOutputs
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.executions import Execution


class DeploymentsTest(CliCommandTest):

    def setUp(self):
        super(DeploymentsTest, self).setUp()
        self._create_cosmo_wd_settings()

    def test_deployment_create(self):

        deployment = Deployment({
            'deployment_id': 'deployment_id'
        })

        self.client.deployments.create = MagicMock(return_value=deployment)
        cli_runner.run_cli('cfy deployments create -b '
                           'a-blueprint-id -d deployment')

    def test_deployments_delete(self):
        self.client.deployments.delete = MagicMock()
        cli_runner.run_cli('cfy deployments delete -d my-dep')

    def test_deployments_execute(self):
        execute_response = Execution({'status': 'terminated'})
        get_execution_response = Execution({
            'status': 'terminated',
            'workflow_id': 'mock_wf',
            'deployment_id': 'deployment-id',
            'blueprint_id': 'blueprint-id',
            'error': '',
            'id': id,
            'created_at': datetime.datetime.now(),
            'parameters': {}
        })

        self.client.executions.start = MagicMock(
            return_value=execute_response
        )
        self.client.executions.get = MagicMock(
            return_value=get_execution_response
        )
        self.client.events.get = MagicMock(return_value=([], 0))
        cli_runner.run_cli('cfy executions start '
                           '-d a-deployment-id -w install')

    def test_deployments_list_all(self):
        self.client.deployments.list = MagicMock(return_value=[])
        cli_runner.run_cli('cfy deployments list')

    def test_deployments_list_of_blueprint(self):

        deployments = [
            {
                'blueprint_id': 'b1',
                'created_at': 'now',
                'updated_at': 'now',
                'id': 'id'
            },
            {
                'blueprint_id': 'b1',
                'created_at': 'now',
                'updated_at': 'now',
                'id': 'id'
            },
            {
                'blueprint_id': 'b2',
                'created_at': 'now',
                'updated_at': 'now',
                'id': 'id'
            }
        ]

        self.client.deployments.list = MagicMock(return_value=deployments)
        output = cli_runner.run_cli('cfy deployments list -b b1 -v')
        self.assertNotIn('b2', output)
        self.assertIn('b1', output)

    def test_deployments_execute_nonexistent_operation(self):
        # verifying that the CLI allows for arbitrary operation names,
        # while also ensuring correct error-handling of nonexistent
        # operations

        expected_error = "operation nonexistent-operation doesn't exist"

        self.client.executions.start = MagicMock(
            side_effect=CloudifyClientError(expected_error))

        command = 'cfy executions start ' \
                  '-w nonexistent-operation -d a-deployment-id'
        self._assert_ex(command, expected_error)

    def test_deployments_outputs(self):

        outputs = DeploymentOutputs({
            'deployment_id': 'dep1',
            'outputs': {
                'port': {
                    'description': 'Web server port.',
                    'value': [8080]
                }
            }
        })
        self.client.deployments.outputs.get = MagicMock(return_value=outputs)
        cli_runner.run_cli('cfy deployments outputs -d dep1')
