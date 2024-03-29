########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import json

from mock import Mock

from cloudify_cli.logger import set_global_json_output

from .test_base import CliCommandTest

from cloudify_rest_client import deployments
from cloudify_rest_client.exceptions import CloudifyClientError


class WorkflowsTest(CliCommandTest):
    def setUp(self):
        super(WorkflowsTest, self).setUp()
        self.use_manager()

    def test_workflows_list(self):
        deployment = deployments.Deployment({
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

        self.client.deployments.get = Mock(return_value=deployment)
        self.invoke('cfy workflows list -d a-deployment-id')

    def test_workflows_sort_list(self):

        deployment = deployments.Deployment({
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

        self.client.deployments.get = Mock(return_value=deployment)

        output = self.invoke('cfy workflows list -d a-deployment-id').output
        first = output.find('my_workflow_0')
        second = output.find('my_workflow_1')
        self.assertTrue(0 < first < second)

    def test_workflows_get(self):
        deployment = deployments.Deployment({
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
                                'key': 'nested value'
                            }
                        }
                    }
                }
            ]
        })

        self.client.deployments.get = Mock(return_value=deployment)
        outcome = self.invoke('workflows get mock_workflow -d dep_id')
        self.assertIn('test-mandatory-key', outcome.output)
        self.assertIn('nested value', outcome.output)

    def test_workflows_get_json(self):
        deployment = deployments.Deployment({
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
                                'key': 'nested value'
                            }
                        }
                    }
                }
            ]
        })

        self.client.deployments.get = Mock(return_value=deployment)
        outcome = self.invoke('workflows get mock_workflow -d dep_id --json')
        parsed = json.loads(outcome.output)
        self.assertEqual(deployment.workflows[0]['parameters'],
                         parsed['parameters'])

    def test_workflows_get_nonexistent_workflow(self):

        expected_message = \
            'Workflow nonexistent_workflow of deployment dep_id not found'
        deployment = deployments.Deployment({
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

        self.client.deployments.get = Mock(return_value=deployment)
        self.invoke('cfy workflows get nonexistent_workflow -d dep_id',
                    expected_message)

    def test_workflows_get_nonexistent_deployment(self):

        expected_message = \
            "Deployment 'nonexistent-dep' not found on manager server"

        self.client.deployments.get = Mock(
            side_effect=CloudifyClientError(expected_message))
        self.invoke('cfy workflows get wf -d nonexistent-dep -v',
                    err_str_segment=expected_message,
                    exception=CloudifyClientError)

    def test_workflows_list_hides_unavailable(self):
        deployment = deployments.Deployment({
            'workflows': [
                {
                    'name': 'wf1',
                    'is_available': False,
                },
                {
                    'name': 'wf2',
                    'is_available': True,
                    'availability_rules': {
                        'rule1': True,
                    },
                }
            ]
        })
        self.client.deployments.get = Mock(return_value=deployment)

        # listing by default only shows available wfs
        outcome = self.invoke('workflows list -d d1 --json')
        parsed = json.loads(outcome.output)
        assert len(parsed) == 1

        # with --all, all workflows are shown
        outcome = self.invoke('workflows list -d d1 --json --all')
        parsed = json.loads(outcome.output)
        assert len(parsed) == 2
        assert 'availability_rules' in parsed[1]
        assert 'rule1' in parsed[1]['availability_rules']

        # when some workflows are hidden, we also emit a log
        set_global_json_output(False)
        outcome = self.invoke('workflows list -d d1')
        assert 'unavailable workflows hidden' in outcome.logs
        assert 'rule1' in outcome.output
