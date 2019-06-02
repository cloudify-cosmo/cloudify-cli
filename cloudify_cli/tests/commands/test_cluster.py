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

from .test_base import CliCommandTest
from cloudify_rest_client.manager import ManagerItem, RabbitMQBrokerItem
from cloudify_cli.tests.cfy import ClickInvocationException


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
        self.client.manager.get_status = mock.MagicMock()
        self.client.maintenance_mode.status = mock.MagicMock()
        self.client.manager.get_managers = mock.MagicMock()
        self.client.manager.get_brokers = mock.MagicMock(
            return_value=self.BROKERS_LIST)
        self.client.manager.get_managers().items = self.MANAGERS_LIST

    def test_list_nodes(self):
        self.use_manager()

        self.client.manager.get_status.side_effect = [
            {
                'services': [
                    {
                        'instances': [{'state': 'running'}],
                        'display_name': 'Service-1'
                    },
                    {
                        'instances': [{'state': 'remote'}],
                        'display_name': 'Service-2'
                    },
                    {
                        'instances': [{'state': 'down'}],
                        'display_name': 'Service-3'
                    },
                    {
                        'instances': [{'state': 'running'}],
                        'display_name': 'Service-4'
                    }
                ]
            },
            ConnectionError,
            {
                'services': [
                    {
                        'instances': [{'state': 'running'}],
                        'display_name': 'Service-BlaBla'
                    },
                    {
                        'instances': [{'state': 'down'}],
                        'display_name': 'Service-1'
                    }
                ]
            }
        ]
        outcome = self.invoke('cfy cluster status')
        supposed_to_be_in_list = [
            'Active',
            'Offline',
            'hostname_1',
            '1.2.3.5',
            'broker1',
            '15671',
            '3.2.3.4'
        ]
        not_supposed_to_be_in_list = [
            'Service-1',
            'Service-2',
            'Service-3',
            'Service-4',
            'Service-BlaBla',
            'N/A',
            'down',
            'remote',
            'running',
            'id',
            'fs_sync_node_id'
        ]
        for supposed_to_be_in in supposed_to_be_in_list:
            self.assertIn(supposed_to_be_in, outcome.output)
        for not_supposed_to_be_in in not_supposed_to_be_in_list:
            self.assertNotIn(not_supposed_to_be_in, outcome.output)

    def test_list_nodes_verbose(self):
        self.use_manager()

        self.client.manager.get_status.side_effect = [
            {
                'services': [
                    {
                        'instances': [{'state': 'running'}],
                        'display_name': 'Service-1'
                    },
                    {
                        'instances': [{'state': 'remote'}],
                        'display_name': 'Service-2'
                    },
                    {
                        'instances': [{'state': 'down'}],
                        'display_name': 'Service-3'
                    },
                    {
                        'instances': [{'state': 'running'}],
                        'display_name': 'Service-4'
                    }
                ]
            },
            ConnectionError,
            {
                'services': [
                    {
                        'instances': [{'state': 'running'}],
                        'display_name': 'Service-BlaBla'
                    },
                    {
                        'instances': [{'state': 'down'}],
                        'display_name': 'Service-1'
                    }
                ]
            }
        ]
        outcome = self.invoke('cfy cluster status -v')
        supposed_to_be_in_list = [
            'Service-1',
            'Service-2',
            'Service-3',
            'Service-4',
            'Service-BlaBla',
            'down',
            'remote',
            'running',
            'Active',
            'Offline',
            'hostname_1',
            '1.2.3.5',
            'N/A',
            'broker1',
            '15671',
            '3.2.3.4'
        ]
        for supposed_to_be_in in supposed_to_be_in_list:
            self.assertIn(supposed_to_be_in, outcome.output)
        self.assertNotIn('id', outcome.output)
        self.assertNotIn('fs_sync_node_id', outcome.output)

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
