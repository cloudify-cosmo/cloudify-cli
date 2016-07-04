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

from cloudify_rest_client.deployments import Deployment
from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class GroupsTest(CliCommandTest):

    def setUp(self):
        super(GroupsTest, self).setUp()
        self._create_cosmo_wd_settings()

    def test_groups_list(self):
        deployment = Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'groups': {
                'group1': {
                    'members': ['node1', 'node2'],
                    'policies': {
                        'policy1': {
                            'type': 'cloudify.policies.threshold'
                        }
                    }
                },
                'group2': {
                    'members': ['node1', 'node2'],
                    'policies': {
                        'policy2': {
                            'type': 'cloudify.policies.host_failure'
                        }
                    }
                },
                'group3': {
                    'members': ['group1', 'node3']
                }
            },
            'scaling_groups': {
                'group2': {
                    'members': ['node1', 'node2'],
                    'properties': {

                    }
                },
                'group3': {
                    'members': ['group1', 'node3'],
                    'properties': {

                    }
                }
            }
        })
        self.client.deployments.get = MagicMock(return_value=deployment)
        cli_runner.run_cli('cfy groups list -d a-deployment-id')

    def test_groups_sort_list(self):
        deployment = Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'groups': {
                'group2': {
                    'members': ['node1', 'node2'],
                    'policies': {
                        'policy1': {
                            'type': 'cloudify.policies.threshold'
                        }
                    }
                },
                'group3': {
                    'members': ['node1', 'node2'],
                    'policies': {
                        'policy2': {
                            'type': 'cloudify.policies.host_failure'
                        }
                    }
                },
                'group1': {
                    'members': ['node2', 'node3']
                }
            }
        })
        self.client.deployments.get = MagicMock(return_value=deployment)
        output = cli_runner.run_cli('cfy groups list -d a-deployment-id')
        first = output.find('group1')
        second = output.find('group2')
        third = output.find('group3')
        self.assertTrue(0 < first < second < third)

    def test_groups_list_nonexistent_deployment(self):
        expected_message = ('Deployment nonexistent-dep not found')
        error = CloudifyClientError('')
        error.status_code = 404
        self.client.deployments.get = MagicMock(side_effect=error)
        self._assert_ex("cfy groups list -d nonexistent-dep", expected_message)
