########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

"""
Tests all commands that start with 'cfy nodes'
"""

from uuid import uuid4

from mock import MagicMock
from cloudify_rest_client.nodes import Node
from cloudify_rest_client.node_instances import NodeInstance

from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class NodesTest(CliCommandTest):

    def setUp(self):
        super(NodesTest, self).setUp()
        self._create_cosmo_wd_settings()

    def test_nodes_get(self):
        self.client.nodes.get = MagicMock(return_value=node_get_mock())
        self.client.node_instances.list = \
            MagicMock(return_value=[node_instance_get_mock()])
        cli_runner.run_cli('cfy nodes get --node-id mongod -d nodecellar')

        with self.assertRaises(SystemExit) as sys_exit:
            cli_runner.run_cli('cfy nodes get --node-id mongod')
        self.assertNotEquals(sys_exit.exception.code, 0)

        with self.assertRaises(SystemExit) as sys_exit:
            cli_runner.run_cli('cfy nodes get -d nodecellar')
        self.assertNotEquals(sys_exit.exception.code, 0)

    def test_nodes_list(self):
        self.client.nodes.list = MagicMock(return_value=[node_get_mock(),
                                                         node_get_mock()])
        cli_runner.run_cli('cfy nodes list')
        cli_runner.run_cli('cfy nodes list -d nodecellar')


def node_get_mock():
    return Node({
        'id': uuid4(),
        'deployment_id': 'deployment-id',
        'blueprint_id': 'blueprint_id',
        'host_id': 'host_id',
        'type': 'Compute',
        'number_of_instances': '1',
        'planned_number_of_instances': '2',
        'properties': {
            'port': '8080'
        }
    })


def node_instance_get_mock():
    return NodeInstance({
        'id': uuid4(),
        'deployment_id': 'deployment_id',
        'host_id': 'host_id',
        'node_id': 'node_id',
        'state': 'started',
        'runtime_properties': {
            'floating_ip': '127.0.0.1'
        }
    })
