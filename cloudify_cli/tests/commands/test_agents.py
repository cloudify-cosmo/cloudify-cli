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

import uuid

from mock import patch, PropertyMock, DEFAULT

from .test_base import CliCommandTest
from cloudify_rest_client.client import CLOUDIFY_TENANT_HEADER
from cloudify_rest_client.executions import ExecutionsClient
from cloudify_rest_client.events import EventsClient
from cloudify_rest_client.node_instances import NodeInstance
from cloudify_rest_client.deployments import Deployment
from cloudify_rest_client.nodes import Node
from cloudify_rest_client.executions import Execution
from cloudify_rest_client.responses import ListResponse, Metadata
from cloudify_cli.cli import cfy
from cloudify_cli.exceptions import CloudifyCliError

from cloudify_cli.commands.agents import (
    get_filters_map,
    get_deployments_and_run_workers)

DEFAULT_TENANT_NAME = 'tenant0'


def _node_instance(tenant_name, ni_id, node_id, dep_id,
                   state='started'):
    return NodeInstance({
        'tenant_name': tenant_name,
        'id': ni_id,
        'host_id': ni_id,
        'node_id': node_id,
        'deployment_id': dep_id,
        'state': state
    })


class AgentsTests(CliCommandTest):
    def setUp(self):
        super(AgentsTests, self).setUp()
        self.use_manager()

    @staticmethod
    def _agent_filters(node_ids=None, node_instance_ids=None,
                       deployment_ids=None, install_methods=None):
        return {cfy.AGENT_FILTER_NODE_IDS: node_ids,
                cfy.AGENT_FILTER_NODE_INSTANCE_IDS: node_instance_ids,
                cfy.AGENT_FILTER_DEPLOYMENT_ID: deployment_ids,
                cfy.AGENT_FILTER_INSTALL_METHODS: install_methods}

    DEFAULT_TOPOLOGY = [
        _node_instance(DEFAULT_TENANT_NAME, 't0d0node1_1', 'node1', 'd0'),
        _node_instance(DEFAULT_TENANT_NAME, 't0d0node1_2', 'node1', 'd0'),
        _node_instance(DEFAULT_TENANT_NAME, 't0d0node2_1', 'node2', 'd0'),
        _node_instance(DEFAULT_TENANT_NAME, 't0d1node1_1', 'node1', 'd1'),
        _node_instance(DEFAULT_TENANT_NAME, 't0d1node1_2', 'node1', 'd1'),
        _node_instance(DEFAULT_TENANT_NAME, 't0d1node3_1', 'node3', 'd1'),
        _node_instance('other_tenant', 't1d0node1_1', 'node1', 'd0'),
        _node_instance('other_tenant', 't1d0node1_2', 'node1', 'd0'),
        _node_instance('other_tenant', 't1d1node3_1', 'node3', 'd1'),
        _node_instance('other_tenant', 't1d2node4_1', 'node4', 'd2'),
    ]

    def mock_client(self, topology):
        def _topology_filter(predicate, **kwargs):
            tenant_name = self.client._client.headers.get(
                CLOUDIFY_TENANT_HEADER)
            if not tenant_name:
                tenant_name = DEFAULT_TENANT_NAME
            results = list()
            all_tenants = kwargs.get('_all_tenants', False)
            for node_instance in topology:
                ni_tenant_name = node_instance['tenant_name']
                if (all_tenants or ni_tenant_name == tenant_name) \
                        and predicate(node_instance):
                    results.append(node_instance)
            return results

        def list_node_instances(**kwargs):
            def _matcher(node_instance):
                ni_id = node_instance['id']
                ni_node_id = node_instance['node_id']
                ni_dep_id = node_instance['deployment_id']
                return ni_id in kwargs.get('id', [ni_id]) and \
                    ni_node_id in kwargs.get('node_id', [ni_node_id]) and \
                    ni_dep_id in kwargs.get('deployment_id', [ni_dep_id])

            return _topology_filter(_matcher, **kwargs)

        def list_deployments(**kwargs):
            tenant_name = self.client._client.headers.get(
                CLOUDIFY_TENANT_HEADER)
            if not tenant_name:
                tenant_name = DEFAULT_TENANT_NAME
            all_node_instances = _topology_filter(lambda x: True, **kwargs)
            deployments = {(x['tenant_name'], x['deployment_id'])
                           for x in all_node_instances}
            deployments = [Deployment({'id': b, 'tenant_name': a}) for a, b in
                           deployments]
            results = list()
            searched_ids = kwargs['id']
            for dep in deployments:
                if (not searched_ids) or dep.id in searched_ids:
                    results.append(dep)
            return results

        def list_nodes(**kwargs):
            node_ids = kwargs.get('id')
            all_node_instances = _topology_filter(lambda x: True, **kwargs)
            nodes = {(x['tenant_name'], x['deployment_id'], x['node_id'])
                     for x in all_node_instances}
            nodes = [Node({'id': c, 'deployment_id': b, 'tenant_name': a}) for
                     (a, b, c) in nodes]
            if node_ids is None:
                return nodes
            return [x for x in nodes if x['id'] in node_ids]

        self.client.node_instances.list = list_node_instances
        self.client.deployments.list = list_deployments
        self.client.nodes.list = list_nodes

    def assert_execution_started(self, client_mock, deployment_id,
                                 filters):
        self.assertIn(
            ((deployment_id, 'workflow', filters), {
                'allow_custom_parameters': True
            }), client_mock.call_args_list)

    # Tests for get_node_instances_map

    def test_parameters_error(self):
        self.mock_client({})
        self.assertRaises(
            CloudifyCliError,
            get_filters_map,
            self.client,
            self.logger,
            AgentsTests._agent_filters(
                node_instance_ids=['a1'],
                deployment_ids=['d1']
            ),
            [DEFAULT_TENANT_NAME])

    def test_filters_map_empty(self):
        self.mock_client({})
        results = get_filters_map(
            self.client, self.logger, AgentsTests._agent_filters(), False)
        self.assertFalse(results)

    def test_filters_map_empty_node_instances(self):
        self.mock_client({})
        self.assertRaises(
            CloudifyCliError,
            get_filters_map,
            self.client,
            self.logger,
            AgentsTests._agent_filters(node_instance_ids=['t0d0node1_1']),
            False)

    def test_filters_map_empty_deployment_ids(self):
        self.mock_client({})
        self.assertRaises(
            CloudifyCliError,
            get_filters_map,
            self.client,
            self.logger,
            AgentsTests._agent_filters(deployment_ids=['d0']),
            False)

    def test_filters_map_all(self):
        self.mock_client(AgentsTests.DEFAULT_TOPOLOGY)
        results = get_filters_map(
            self.client, self.logger, AgentsTests._agent_filters(),
            True)
        self.assertEquals({
            DEFAULT_TENANT_NAME: {
                'd0': {},
                'd1': {}
            },
            'other_tenant': {
                'd0': {},
                'd1': {},
                'd2': {}
            }
        }, results)

    def test_filters_map_node_id_single_tenant(self):
        self.mock_client(AgentsTests.DEFAULT_TOPOLOGY)
        results = get_filters_map(
            self.client, self.logger, AgentsTests._agent_filters(
                node_ids=['node1']), False)

        self.assertEquals({
            DEFAULT_TENANT_NAME: {
                'd0': {'node_ids': ['node1']},
                'd1': {'node_ids': ['node1']}
            }
        }, results)

    def test_filters_map_node_id_all_tenants(self):
        self.mock_client(AgentsTests.DEFAULT_TOPOLOGY)
        results = get_filters_map(
            self.client, self.logger, AgentsTests._agent_filters(
                node_ids=['node1']), True)

        self.assertEquals({
            DEFAULT_TENANT_NAME: {
                'd0': {
                    'node_ids': ['node1']
                },
                'd1': {
                    'node_ids': ['node1']
                }
            },
            'other_tenant': {
                'd0': {
                    'node_ids': ['node1']
                }
            }
        }, results)

    def test_filters_map_dep_id_single_tenant(self):
        self.mock_client(AgentsTests.DEFAULT_TOPOLOGY)
        results = get_filters_map(
            self.client, self.logger, AgentsTests._agent_filters(
                deployment_ids=['d0']), False)

        self.assertEquals({
            DEFAULT_TENANT_NAME: {
                'd0': {}
            }
        }, results)

    def test_filters_map_dep_id_all_tenants(self):
        self.mock_client(AgentsTests.DEFAULT_TOPOLOGY)
        results = get_filters_map(
            self.client, self.logger, AgentsTests._agent_filters(
                deployment_ids=['d0']), True)

        self.assertEquals({
            DEFAULT_TENANT_NAME: {
                'd0': {}
            },
            'other_tenant': {
                'd0': {}
            }
        }, results)

    def test_filters_map_bad_dep_id(self):
        self.mock_client(AgentsTests.DEFAULT_TOPOLOGY)
        self.assertRaises(
            CloudifyCliError,
            get_filters_map,
            self.client,
            self.logger,
            AgentsTests._agent_filters(deployment_ids=['error']),
            False)

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
            '',
            False)

    @patch.object(ExecutionsClient, 'start')
    def test_full_topology(self, exec_client_mock):
        self.mock_client(AgentsTests.DEFAULT_TOPOLOGY)
        get_deployments_and_run_workers(
            self.client, self._agent_filters(),
            True, self.logger, 'workflow', False
        )

        self.assert_execution_started(exec_client_mock, 'd1', {})
        self.assert_execution_started(exec_client_mock, 'd0', {})
        self.assert_execution_started(exec_client_mock, 'd2', {})
        self.assertEquals(len(exec_client_mock.call_args_list), 5)

    @patch.object(ExecutionsClient, 'start')
    def test_full_topology_one_nonstarted(self, exec_client_mock):
        topology = list(AgentsTests.DEFAULT_TOPOLOGY)
        topology.append(_node_instance(DEFAULT_TENANT_NAME, 't0d1node4_1',
                                       'node4', 'd1', 'creating'))
        self.mock_client(topology)
        get_deployments_and_run_workers(
            self.client, self._agent_filters(),
            True, self.logger, 'workflow', False
        )
        self.assertEquals(len(exec_client_mock.call_args_list), 4)

    @patch.object(ExecutionsClient, 'start')
    def test_node_instances_map_none(self, exec_client_mock):
        self.mock_client(AgentsTests.DEFAULT_TOPOLOGY)
        get_deployments_and_run_workers(
            self.client, self._agent_filters(install_methods=['provided']),
            True, self.logger, 'workflow', False
        )
        self.assertEquals(exec_client_mock.call_count, 5)
        for call in exec_client_mock.call_args_list:
            self.assertTrue(call[0][2]['install_methods'] == ['provided'])

    @patch.object(ExecutionsClient, 'get',
                  return_value=Execution({'status': 'terminated'}))
    @patch.object(EventsClient, 'list',
                  return_value=ListResponse(
                      [],
                      Metadata({'pagination': {
                          'total': 0,
                          'offset': 0,
                          'size': 10}})))
    def test_execution_tracking(self, events_list_mock, exec_get_mock):
        self.mock_client(AgentsTests.DEFAULT_TOPOLOGY)

        def _mock_execution_start(*args, **kwargs):
            tenant_name = args[0].api.headers.get(CLOUDIFY_TENANT_HEADER)
            deployment_id = args[1]
            return Execution({'id': str(uuid.uuid4()),
                              'deployment_id': deployment_id,
                              'tenant_name': tenant_name})

        def _wait_side_effect(*args, **kwargs):
            client_tenant = args[0]._client.headers[CLOUDIFY_TENANT_HEADER]
            execution = args[1]
            self.assertEquals(client_tenant, execution['tenant_name'])
            return DEFAULT

        with patch('cloudify_cli.commands.agents.wait_for_execution',
                   return_value=PropertyMock(error=False),
                   side_effect=_wait_side_effect), \
            patch.object(ExecutionsClient, 'start',
                         _mock_execution_start), \
                patch('cloudify_cli.commands.agents.time.sleep'):

            get_deployments_and_run_workers(
                self.client, self._agent_filters(), True, self.logger,
                'workflow', True)
