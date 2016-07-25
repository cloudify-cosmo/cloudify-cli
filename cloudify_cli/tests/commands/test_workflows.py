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

from mock import MagicMock

from cloudify_rest_client.deployments import Deployment
from cloudify_rest_client.exceptions import CloudifyClientError

from .test_cli_command import CliCommandTest


class WorkflowsTest(CliCommandTest):
    def setUp(self):
        super(WorkflowsTest, self).setUp()
        self.create_cosmo_wd_settings()

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
        self.invoke('cfy workflows list -d a-deployment-id')

    def test_workflows_sort_list(self):

        deployment = Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'workflows': [
                {
                    'created_at': None,
                    'name': 'my_workflow_1',
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
                },
                {
                    'created_at': None,
                    'name': 'my_workflow_0',
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

        output = self.invoke('cfy workflows list -d a-deployment-id').logs
        first = output.find('my_workflow_0')
        second = output.find('my_workflow_1')
        self.assertTrue(0 < first < second)

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
        self.invoke('cfy workflows get mock_workflow -d dep_id')

    def test_workflows_get_nonexistent_workflow(self):

        expected_message = 'Workflow nonexistent_workflow not found'
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
        self.invoke('cfy workflows get nonexistent_workflow -d dep_id',
                    expected_message)

    def test_workflows_get_nonexistent_deployment(self):

        expected_message = \
            "Deployment 'nonexistent-dep' not found on management server"

        self.client.deployments.get = MagicMock(
            side_effect=CloudifyClientError(expected_message))
        self.invoke('cfy workflows get wf -d nonexistent-dep -v',
                    err_str_segment=expected_message,
                    exception=CloudifyClientError)
