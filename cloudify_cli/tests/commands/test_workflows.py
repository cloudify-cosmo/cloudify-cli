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
from cloudify_cli import utils
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

    def test_workflows_sort_list(self):

        def set_mocks():
            def mock_table(*_, **kwargs):
                workflows = kwargs['data']
                self.assertEqual(2, len(workflows))
                self.assertEqual('0', workflows[0].name)
                self.assertEqual('1', workflows[1].name)

            def mock_print_table(*_, **__):
                pass

            utils.table, utils.print_table = mock_table, mock_print_table

        original_table, original_print_table = utils.table, utils.print_table
        deployment = Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'workflows': [
                {
                    'created_at': None,
                    'name': '1',
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
                    'name': '0',
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
        set_mocks()
        cli_runner.run_cli('cfy workflows list -d a-deployment-id')
        utils.table, utils.print_table = original_table, original_print_table

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
