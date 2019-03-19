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

from cloudify_rest_client.manager import ManagerItem

from .test_base import CliCommandTest
from ...exceptions import CloudifyCliError


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

    def setUp(self):
        super(ClusterTest, self).setUp()
        self.use_manager()

    def test_list_nodes(self):
        self.client.manager.get_managers = mock.Mock(
            return_value=self.MANAGERS_LIST)
        self.client.manager.get_status = mock.Mock(side_affect=[
            {
                'services': [
                    {
                        'display_name': 'Service-1',
                        'instances': [
                            {
                                'state': 'running'
                            }
                        ]
                    },
                    {
                        'display_name': 'Service-2',
                        'instances': [
                            {
                                'state': 'remote'
                            }
                        ]
                    },
                    {
                        'display_name': 'Service-3',
                        'instances': [
                            {
                                'state': 'down'
                            }
                        ]
                    },
                    {
                        'display_name': 'Service-4',
                        'instances': [
                            {
                                'state': 'running'
                            }
                        ]
                    }
                ]
            },
            ConnectionError,
            {
                'services': [
                    {
                        'display_name': 'Service-BlaBla',
                        'instances': [
                            {
                                'state': 'running'
                            }
                        ]
                    },
                    {
                        'display_name': 'Service-1',
                        'instances': [
                            {
                                'state': 'down'
                            }
                        ]
                    }
                ]
            }
        ])
        outcome = self.invoke('cfy status')
        self.assertIn([
            'Service-1',
            'Service-2',
            'Service-3',
            'Service-4',
            'Service-BlaBla',
            'down',
            'remote',
            'running',
            'Online',
            'Offline',
            'hostname_1',
            '1.2.3.5'
            ], outcome.output)
        self.assertNotIn([
            'id',
            'fs_sync_node_id',
            ], outcome.output
        )

    def test_remove_node(self):
        self.client.manager.get_managers = mock.Mock(
            return_value=self.MANAGERS_LIST)
        self.client.manager.remove_manager = mock.Mock(
            return_value=self.MANAGERS_LIST[0])
        outcome = self.invoke('cfy remove hostname_1')
        self.assertIn('Node hostname_1 was removed successfully!',
                      outcome.output)

    def test_remove_non_existing_node(self):
        self.client.manager.get_managers = mock.Mock(
            return_value=self.MANAGERS_LIST)
        self.client.manager.remove_manager = mock.Mock(
            return_value=self.MANAGERS_LIST[0])
        self.assertRaises(CloudifyCliError, self.invoke,
                          'cfy remove hostname_BlaBla')
