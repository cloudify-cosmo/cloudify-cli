from mock import MagicMock

from .test_base import CliCommandTest

from cloudify_rest_client import deployments
from cloudify_rest_client.exceptions import CloudifyClientError


class GroupsTest(CliCommandTest):

    def setUp(self):
        super(GroupsTest, self).setUp()
        self.use_manager()

    def test_groups_list(self):
        deployment = deployments.Deployment({
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
        self.invoke('cfy groups list -d a-deployment-id')

    def test_groups_sort_list(self):
        deployment = deployments.Deployment({
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
        output = self.invoke('cfy groups list -d a-deployment-id').logs
        first = output.find('group1')
        second = output.find('group2')
        third = output.find('group3')
        self.assertTrue(0 < first < second < third)

    def test_groups_list_nonexistent_deployment(self):
        expected_message = 'Deployment nonexistent-dep not found'
        error = CloudifyClientError('')
        error.status_code = 404
        self.client.deployments.get = MagicMock(side_effect=error)
        self.invoke("cfy groups list -d nonexistent-dep", expected_message)
