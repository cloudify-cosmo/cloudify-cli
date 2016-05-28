########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

"""
Tests all commands that start with 'cfy workflows'
"""

from mock import MagicMock
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest
from cloudify_rest_client.deployments import Deployment
from cloudify_rest_client.exceptions import CloudifyClientError


class WorkflowsTest(CliCommandTest):
    def setUp(self):
        super(WorkflowsTest, self).setUp()
        self._create_cosmo_wd_settings()

    def test_workflows_list(self):
        deployment = Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'workflows': [
                {
                    'created_at': None,
                    'name': 'mock_workflow',
                    'parameters': {
                        'test-key': {
                            'default': 'test-value'
                        },
                        'test-mandatory-key': {},
                        'test-nested-key': {
                            'default': {
                                'key': 'val'
                            }
                        }
                    }
                }
            ]
        })

        self.client.deployments.get = MagicMock(return_value=deployment)
        cli_runner.run_cli('cfy workflows list -d a-deployment-id')

    def test_workflows_get(self):
        deployment = Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'workflows': [
                {
                    'created_at': None,
                    'name': 'mock_workflow',
                    'parameters': {
                        'test-key': {
                            'default': 'test-value'
                        },
                        'test-mandatory-key': {},
                        'test-nested-key': {
                            'default': {
                                'key': 'val'
                            }
                        }
                    }
                }
            ]
        })

        self.client.deployments.get = MagicMock(return_value=deployment)
        cli_runner.run_cli('cfy workflows get -w mock_workflow -d dep_id')

    def test_workflows_get_nonexistent_workflow(self):

        expected_message = ('Workflow nonexistent_workflow not found')
        deployment = Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'workflows': [
                {
                    'created_at': None,
                    'name': 'mock_workflow',
                    'parameters': {
                        'test-key': {
                            'default': 'test-value'
                        },
                        'test-mandatory-key': {},
                        'test-nested-key': {
                            'default': {
                                'key': 'val'
                            }
                        }
                    }
                }
            ]
        })

        self.client.deployments.get = MagicMock(return_value=deployment)
        self._assert_ex('cfy workflows get -w nonexistent_workflow -d dep_id',
                        expected_message)

    def test_workflows_get_nonexistent_deployment(self):

        expected_message = ("Deployment 'nonexistent-dep' "
                            "not found on management server")

        self.client.deployments.get = MagicMock(
            side_effect=CloudifyClientError(expected_message)
        )
        self._assert_ex("cfy workflows get -w wf -d nonexistent-dep -v",
                        expected_message)
