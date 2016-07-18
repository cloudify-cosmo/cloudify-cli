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

import datetime

from mock import MagicMock

from cloudify_rest_client import deployments
from cloudify_rest_client.executions import Execution
from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class DeploymentsTest(CliCommandTest):

    def setUp(self):
        super(DeploymentsTest, self).setUp()
        self.create_cosmo_wd_settings()

    def test_deployment_create(self):

        deployment = deployments.Deployment({
            'deployment_id': 'deployment_id'
        })

        self.client.deployments.create = MagicMock(return_value=deployment)
        self.invoke(
            'cfy deployments create a-blueprint-id -d deployment')

    def test_deployments_delete(self):
        self.client.deployments.delete = MagicMock()
        self.invoke('cfy deployments delete my-dep')

    def test_deployments_execute(self):
        execute_response = Execution({'status': 'started'})
        get_execution_response = Execution({
            'status': 'terminated',
            'workflow_id': 'mock_wf',
            'deployment_id': 'deployment-id',
            'blueprint_id': 'blueprint-id',
            'error': '',
            'id': 'id',
            'created_at': datetime.datetime.now(),
            'parameters': {}
        })
        success_event = {
            'event_type': 'workflow_succeeded',
            'type': 'foo',
            'timestamp': '12345678',
            'message': {
                'text': 'workflow execution succeeded'
            },
            'context': {
                'deployment_id': 'deployment-id'
            }
        }
        get_events_response = ([success_event], 1)

        self.client.executions.start = MagicMock(
            return_value=execute_response)
        self.client.executions.get = MagicMock(
            return_value=get_execution_response)
        self.client.events.get = MagicMock(return_value=get_events_response)
        self.invoke('cfy executions start install -d a-deployment-id')

    def test_deployments_list_all(self):
        self.client.deployments.list = MagicMock(return_value=[])
        self.invoke('cfy deployments list')

    def test_deployments_list_of_blueprint(self):

        deployments = [
            {
                'blueprint_id': 'b1_blueprint',
                'created_at': 'now',
                'updated_at': 'now',
                'id': 'id'
            },
            {
                'blueprint_id': 'b1_blueprint',
                'created_at': 'now',
                'updated_at': 'now',
                'id': 'id'
            },
            {
                'blueprint_id': 'b2_blueprint',
                'created_at': 'now',
                'updated_at': 'now',
                'id': 'id'
            }
        ]

        self.client.deployments.list = MagicMock(return_value=deployments)
        outcome = self.invoke('cfy deployments list b1_blueprint -v')
        self.assertNotIn('b2_blueprint', outcome.logs)
        self.assertIn('b1_blueprint', outcome.logs)

    def test_deployments_execute_nonexistent_operation(self):
        # Verifying that the CLI allows for arbitrary operation names,
        # while also ensuring correct error-handling of nonexistent
        # operations

        expected_error = "operation nonexistent-operation doesn't exist"

        self.client.executions.start = MagicMock(
            side_effect=CloudifyClientError(expected_error))

        command = \
            'cfy executions start nonexistent-operation -d a-deployment-id'
        self.invoke(
            command,
            err_str_segment=expected_error,
            exception=CloudifyClientError)

    def test_deployments_outputs(self):

        outputs = deployments.DeploymentOutputs({
            'deployment_id': 'dep1',
            'outputs': {
                'port': 8080
            }
        })
        deployment = deployments.Deployment({
            'outputs': {
                'port': {
                    'description': 'Webserver port.',
                    'value': '...'
                }
            }
        })
        self.client.deployments.get = MagicMock(return_value=deployment)
        self.client.deployments.outputs.get = MagicMock(return_value=outputs)
        self.invoke('cfy deployments outputs dep1')
