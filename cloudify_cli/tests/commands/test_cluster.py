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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import mock

from requests.exceptions import ConnectionError

from cloudify_rest_client.exceptions import UserUnauthorizedError
from cloudify_rest_client.manager import ManagerItem, RabbitMQBrokerItem

from .test_base import CliCommandTest
from ..cfy import ClickInvocationException


class ClusterTest(CliCommandTest):
    MANAGERS_LIST = [
        ManagerItem(
            {
                'id': '0',
                'hostname': 'hostname_1',
                'private_ip': '1.2.3.4',
                'public_ip': '2.2.3.4',
                'version': '5.0',
                'edition': 'premium',
                'distribution': 'centos',
                'distro_release': 'core',
                'fs_sync_node_id': 'hgujriewgthuiyenfjk'
            }
        ),
        ManagerItem(
            {
                'id': '1',
                'hostname': 'hostname_2',
                'private_ip': '1.2.3.5',
                'public_ip': '2.2.3.5',
                'version': '5.0',
                'edition': 'premium',
                'distribution': 'centos',
                'distro_release': 'core',
                'fs_sync_node_id': 'hgujriewgthuiyenfjk'
            }
        ),
        ManagerItem(
            {
                'id': '2',
                'hostname': 'hostname_3',
                'private_ip': '1.2.3.6',
                'public_ip': '2.2.3.6',
                'version': '5.0',
                'edition': 'premium',
                'distribution': 'centos',
                'distro_release': 'core',
                'fs_sync_node_id': 'hgujriewgthuiyenfjk'
            }
        )
    ]
    BROKERS_LIST = [
        RabbitMQBrokerItem(
            {
                'name': 'broker1',
                'host': '3.2.3.4',
                'port': '15671',
                'params': {},
                'ca_cert_content': 'CA CONTENT',
                'networks': {'default': '3.2.3.4'}
            }
        )
    ]

    def setUp(self):
        super(ClusterTest, self).setUp()
        self.client.cluster_status.get_status = mock.MagicMock()
        self.client.manager.get_managers = mock.MagicMock()
        self.client.manager.get_managers().items = self.MANAGERS_LIST

    def test_command_basic_run(self):
        self.use_manager()
        self.invoke('cfy cluster status')

    def test_cluster_status_by_unauthorized_user(self):
        self.use_manager()
        with mock.patch.object(self.client.cluster_status,
                               'get_status') as status:
            status.side_effect = UserUnauthorizedError('Unauthorized user')
            outcome = self.invoke('cfy cluster status')
            self.assertIn('User is unauthorized', outcome.logs)

    def test_cluster_status_no_manager_server_defined(self):
        # Running a command which requires a target manager server without
        # first calling "cfy profiles use" or providing a target server
        # explicitly
        self.invoke(
            'cfy cluster status',
            'This command is only available when using a manager'
        )

    def test_cluster_status_content(self):
        self.use_manager()

        self.client.cluster_status.get_status.side_effect = [
            {
                'status': 'OK',
                'services': {
                    'Service-1': {
                        'status': 'Active',
                        'is_remote': False
                    },
                    'Service-2': {
                        'status': 'Active',
                        'is_remote': True
                    },
                    'Service-3': {
                        'status': 'Inactive',
                        'is_remote': False
                    },
                    'Service-4': {
                        'status': 'Active',
                        'is_remote': False
                    }
                }
            },
            ConnectionError,
            {
                'services': {
                    'Service-BlaBla': {
                        'status': 'Active',
                        'is_remote': False
                    },
                    'Service-1': {
                        'status': 'Inactive',
                        'is_remote': False
                    }
                }
            }
        ]
        outcome = self.invoke('cfy cluster status')
        supposed_to_be_in_list = [
            "OK",
            'Active',
            'Service-1',
            'Service-2',
            'Service-3',
            'Service-4',
            'Inactive'
        ]
        not_supposed_to_be_in_list = [
            'remote'
        ]
        for supposed_to_be_in in supposed_to_be_in_list:
            self.assertIn(supposed_to_be_in, outcome.output)
        for not_supposed_to_be_in in not_supposed_to_be_in_list:
            self.assertNotIn(not_supposed_to_be_in, outcome.output)

    def test_cluster_status_json_format(self):
        self.use_manager()

        self.client.cluster_status.get_status.side_effect = [
            {
                'status': 'OK',
                'services': {
                    'Service-1': {
                        'status': 'Active',
                        'is_remote': False
                    },
                    'Service-2': {
                        'status': 'Active',
                        'is_remote': True
                    },
                    'Service-3': {
                        'status': 'Inactive',
                        'is_remote': False
                    },
                    'Service-4': {
                        'status': 'Active',
                        'is_remote': False
                    }
                }
            },
            ConnectionError,
            {
                'services': {
                    'Service-BlaBla': {
                        'status': 'Active',
                        'is_remote': False
                    },
                    'Service-1': {
                        'status': 'Inactive',
                        'is_remote': False
                    }
                }
            }
        ]
        outcome = self.invoke('cfy cluster status --json')
        supposed_to_be_in_list = [
            "OK",
            'Active',
            'Service-1',
            'Service-2',
            'Service-3',
            'Service-4',
            'Inactive',
            'remote'
        ]

        for supposed_to_be_in in supposed_to_be_in_list:
            self.assertIn(supposed_to_be_in, outcome.output)

    def test_remove_node(self):
        self.use_manager()
        list_result = mock.Mock()
        list_result.items = self.MANAGERS_LIST
        self.client.manager.get_managers = mock.MagicMock(
            return_value=list_result)
        self.client.manager.remove_manager = mock.MagicMock(
            return_value=self.MANAGERS_LIST[0])
        outcome = self.invoke('cfy cluster remove hostname_1')
        self.assertIn('Node hostname_1 was removed successfully!',
                      outcome.output)

    def test_remove_non_existing_node(self):
        self.use_manager()
        self.client.manager.remove_manager = mock.Mock(
            return_value=self.MANAGERS_LIST[0])
        self.assertRaises(ClickInvocationException, self.invoke,
                          'cfy cluster remove hostname_BlaBla')
