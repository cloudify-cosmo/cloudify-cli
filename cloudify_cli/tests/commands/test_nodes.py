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

from mock import MagicMock

from .test_base import CliCommandTest
from .mocks import node_get_mock, node_instance_get_mock, MockListResponse


class NodesTest(CliCommandTest):

    def setUp(self):
        super(NodesTest, self).setUp()
        self.use_manager()

    def test_nodes_get(self):
        node = node_get_mock()
        node_instance = node_instance_get_mock()
        self.client.nodes.get = MagicMock(return_value=node)
        self.client.node_instances.list = MagicMock(
            return_value=[node_instance])
        outcome = self.invoke('cfy nodes get mongod -d nodecellar')
        self.assertIn(str(node_instance.id), outcome.logs)
        self.assertIn(str(node.properties['port']), outcome.output)

    def test_nodes_get_json(self):
        node = node_get_mock()
        node_instance = node_instance_get_mock()
        self.client.nodes.get = MagicMock(return_value=node)
        self.client.node_instances.list = MagicMock(
            return_value=[node_instance])
        outcome = self.invoke('cfy nodes get mongod -d nodecellar --json')
        parsed = json.loads(outcome.output)
        self.assertEqual(parsed['instances'], [node_instance.id.hex])
        self.assertEqual(parsed['properties'], node.properties)

    def test_node_get_no_node_id(self):
        outcome = self.invoke(
            'cfy nodes get -d nodecellar',
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )

        self.assertIn('Missing argument "node-id"', outcome.output)

    def test_node_get_no_deployment_id(self):
        outcome = self.invoke(
            'cfy nodes get mongod',
            err_str_segment='2',  # Exit code
            exception=SystemExit,
        )

        self.assertIn(
            'Missing option "-d" / "--deployment-id"',
            outcome.output
        )

    def test_nodes_list(self):
        self.client.nodes.list = MagicMock(
            return_value=MockListResponse(items=[node_get_mock(),
                                                 node_get_mock()])
        )
        self.invoke('cfy nodes list')
        self.invoke('cfy nodes list -d nodecellar')
        self.invoke('cfy nodes list -t dummy_tenant')
        self.invoke('cfy nodes list -a')
