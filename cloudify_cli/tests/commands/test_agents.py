########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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

from mock import MagicMock, patch

from .test_base import CliCommandTest
from cloudify_rest_client.executions import ExecutionsClient
from cloudify_rest_client.node_instances import NodeInstance
from cloudify_cli.cli import cfy
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_rest_client.client import CLOUDIFY_TENANT_HEADER

from cloudify_cli.commands.agents import (
    get_node_instances_map,
    get_deployments_and_run_workers)

DEFAULT_TENANT_NAME = 'tenant0'


def _node_instance(ni_id, node_id, dep_id):
    return NodeInstance({
        'id': ni_id,
        'node_id': node_id,
        'deployment_id': dep_id
    })


class AgentsTests(CliCommandTest):
    def setUp(self):
        super(AgentsTests, self).setUp()
        self.use_manager()

    # @staticmethod
    # def create_tenants_and_deployments(num_of_tenants, num_of_deps,
    #                                    unique_deps_id=True):
    #     tenants_list = []
    #     deps = {}
    #     index = 0
    #     # create requested num of tenants
    #     for i in range(num_of_tenants):
    #         ten = tenants.Tenant({'name': 'tenant{0}'.format(i)})
    #         tenants_list.append(ten)
    #     # create requested num of deployments for each tenant
    #     for tenant in tenants_list:
    #         if not unique_deps_id:
    #             index = 0
    #         deps[tenant['name']] = []
    #         index = AgentsTests.create_deployments_in_tenant(
    #             deps[tenant['name']], num_of_deps, tenant, index)
    #     return tenants_list, deps
    #
    # @staticmethod
    # def create_deployments_in_tenant(deps_list, num_of_deps, tenant,
    #                                  start_index):
    #     for i in range(num_of_deps):
    #         deps_list.append(deployments.Deployment({
    #             'id': 'dep{0}'.format(start_index),
    #             'tenant_name': tenant['name']}))
    #         start_index += 1
    #     return start_index

    @staticmethod
    def _agent_filters(node_ids=None, node_instance_ids=None,
                       deployment_ids=None, install_methods=None):
        return {cfy.AGENT_FILTER_NODE_IDS: node_ids,
                cfy.AGENT_FILTER_NODE_INSTANCE_IDS: node_instance_ids,
                cfy.AGENT_FILTER_DEPLOYMENT_ID: deployment_ids,
                cfy.AGENT_FILTER_INSTALL_METHODS: install_methods}

    DEFAULT_TENANTS_MAP = {
        DEFAULT_TENANT_NAME: [
            _node_instance('t0d0node1_1', 'node1', 'd0'),
            _node_instance('t0d0node1_2', 'node1', 'd0'),
            _node_instance('t0d0node2_1', 'node2', 'd0'),
            _node_instance('t0d1node1_1', 'node1', 'd1'),
            _node_instance('t0d1node1_2', 'node1', 'd1'),
            _node_instance('t0d1node3_1', 'node3', 'd1'),
        ],
        'other_tenant': [
            _node_instance('t1d0node1_1', 'node1', 'd0'),
            _node_instance('t1d0node1_2', 'node1', 'd0'),
            _node_instance('t1d1node3_1', 'node3', 'd1'),
            _node_instance('t1d2node4_1', 'node4', 'd2'),
        ]
    }

    def mock_client(self, tenants_map):
        def list_node_instances(**kwargs):
            tenant_name = self.client._client.headers.get(
                CLOUDIFY_TENANT_HEADER)
            if not tenant_name:
                tenant_name = DEFAULT_TENANT_NAME
            if tenant_name not in tenants_map:
                return []
            results = list()
            if kwargs.get('_all_tenants', False):
                candidate_tenants = tenants_map.keys()
            else:
                candidate_tenants = [tenant_name]
            for tenant_name in candidate_tenants:
                node_instances = tenants_map[tenant_name]
                for node_instance in node_instances:
                    ni_id = node_instance['id']
                    ni_node_id = node_instance['node_id']
                    ni_dep_id = node_instance['deployment_id']
                    if ni_id in kwargs.get('id', [ni_id]) and \
                            ni_node_id in kwargs.get('node_id', [ni_node_id]) \
                            and ni_dep_id in kwargs.get(
                           'deployment_id', [ni_dep_id]):
                        results.append(node_instance)
            return results

        self.client.tenants.list = MagicMock(return_value=tenants_map.keys())
        self.client.node_instances.list = list_node_instances

    def assert_execution_started(self, client_mock, deployment_id,
                                 node_instances):
        self.assertIn(
            ((deployment_id, 'workflow', {
                'node_instance_ids': node_instances
            }), {
                'allow_custom_parameters': True
            }), client_mock.call_args_list)

    def _to_node_instance_ids_set(self, results):
        return set(map(lambda x: x['id'], [item for sublist in results.values()
                                           for item in sublist]))

    # Tests for get_node_instances_map

    def test_parameters_error(self):
        self.mock_client({})
        self.assertRaises(
            CloudifyCliError,
            get_node_instances_map,
            self.client,
            AgentsTests._agent_filters(
                node_instance_ids=['a1'],
                deployment_ids=['d1']
            ),
            [DEFAULT_TENANT_NAME])

    def test_instance_map_empty(self):
        self.mock_client({})
        results = get_node_instances_map(
            self.client, AgentsTests._agent_filters(),
            [DEFAULT_TENANT_NAME])
        self.assertFalse(results)

    def test_instance_map_empty_node_instances(self):
        self.mock_client({})
        results = get_node_instances_map(
            self.client, AgentsTests._agent_filters(
                node_instance_ids=['t0d0node1_1']), [DEFAULT_TENANT_NAME])
        self.assertFalse(results)

    def test_instance_map_empty_deployment_ids(self):
        self.mock_client({})
        results = get_node_instances_map(
            self.client, AgentsTests._agent_filters(
                deployment_ids=['d0']), [DEFAULT_TENANT_NAME])
        self.assertFalse(results)

    def test_instance_map_bad_tenant(self):
        self.mock_client(AgentsTests.DEFAULT_TENANTS_MAP)
        results = get_node_instances_map(
            self.client, AgentsTests._agent_filters(), ['FAKE'])
        self.assertFalse(results)

    def test_instance_map_all(self):
        self.mock_client(AgentsTests.DEFAULT_TENANTS_MAP)
        results = get_node_instances_map(
            self.client, AgentsTests._agent_filters(),
            AgentsTests.DEFAULT_TENANTS_MAP.keys())
        self.assertEquals(
            {'t0d0node1_1', 't0d0node1_2', 't0d0node2_1', 't0d1node1_1',
             't0d1node1_2', 't0d1node3_1', 't1d0node1_1', 't1d0node1_2',
             't1d1node3_1', 't1d2node4_1'},
            self._to_node_instance_ids_set(results))

    def test_instance_map_node_id_single_tenant(self):
        self.mock_client(AgentsTests.DEFAULT_TENANTS_MAP)
        results = get_node_instances_map(
            self.client, AgentsTests._agent_filters(
                node_ids=['node1']),
            [DEFAULT_TENANT_NAME])

        self.assertEquals(
            {'t0d0node1_1', 't0d0node1_2', 't0d1node1_1', 't0d1node1_2'},
            self._to_node_instance_ids_set(results))

    def test_instance_map_node_id_all_tenants(self):
        self.mock_client(AgentsTests.DEFAULT_TENANTS_MAP)
        results = get_node_instances_map(
            self.client, AgentsTests._agent_filters(
                node_ids=['node1']),
            AgentsTests.DEFAULT_TENANTS_MAP.keys())

        self.assertEquals(
            {'t0d0node1_1', 't0d0node1_2', 't0d1node1_1', 't0d1node1_2',
             't1d0node1_1', 't1d0node1_2'},
            self._to_node_instance_ids_set(results))

    # Tests for get_deployments_and_run_workers

    def test_empty_node_instances_map(self):
        self.mock_client({})
        self.assertRaises(
            CloudifyCliError,
            get_deployments_and_run_workers,
            self.client,
            self._agent_filters(),
            [],
            self.logger,
            '')

    @patch.object(ExecutionsClient, 'start')
    def test_node_instances_map_full(self, exec_client_mock):
        self.mock_client(AgentsTests.DEFAULT_TENANTS_MAP)
        get_deployments_and_run_workers(
            self.client, self._agent_filters(),
            AgentsTests.DEFAULT_TENANTS_MAP.keys(),
            self.logger, 'workflow'
        )

        self.assert_execution_started(
            exec_client_mock, 'd1',
            ['t0d1node1_1', 't0d1node1_2', 't0d1node3_1'])
        self.assert_execution_started(
            exec_client_mock, 'd0',
            ['t0d0node1_1', 't0d0node1_2', 't0d0node2_1'])
        self.assert_execution_started(
            exec_client_mock, 'd0', ['t1d0node1_1', 't1d0node1_2'])
        self.assert_execution_started(
            exec_client_mock, 'd1', ['t1d1node3_1'])
        self.assert_execution_started(
            exec_client_mock, 'd2', ['t1d2node4_1'])
        self.assertEquals(len(exec_client_mock.call_args_list), 5)
