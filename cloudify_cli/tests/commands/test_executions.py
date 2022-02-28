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

import os
import json

from mock import MagicMock, patch

from ...commands import executions
from .test_base import CliCommandTest, ClickInvocationException
from .mocks import execution_mock, MockListResponse
from .constants import BLUEPRINTS_DIR, DEFAULT_BLUEPRINT_FILE_NAME
from cloudify_rest_client.exceptions import \
    DeploymentEnvironmentCreationPendingError, \
    DeploymentEnvironmentCreationInProgressError


class ExecutionsTest(CliCommandTest):

    def setUp(self):
        super(ExecutionsTest, self).setUp()
        self.use_manager()

    def test_executions_get(self):
        execution = execution_mock('terminated')
        self.client.executions.get = MagicMock(return_value=execution)
        outcome = self.invoke('cfy executions get execution-id')
        self.assertIn(execution.parameters['param1'], outcome.output)

    def test_executions_get_json(self):
        execution = execution_mock('terminated')
        self.client.executions.get = MagicMock(return_value=execution)
        outcome = self.invoke('cfy executions get execution-id --json')
        parsed = json.loads(outcome.output)
        self.assertEqual(parsed['parameters'], execution.parameters)

    def test_executions_list(self):
        self.client.executions.list = MagicMock(
            return_value=MockListResponse())
        self.invoke('cfy executions list -d deployment-id')
        self.invoke('cfy executions list -t dummy_tenant')

    def test_executions_cancel(self):
        self.client.executions.cancel = MagicMock()
        self.invoke('cfy executions cancel e_id')

    @patch('cloudify_cli.commands.executions.get_events_logger')
    def test_executions_start_json(self, get_events_logger_mock):
        execution = execution_mock('started')
        original_client_execution_start = self.client.executions.start
        original_wait_for_executions = executions.wait_for_execution
        try:
            self.client.executions.start = MagicMock(return_value=execution)
            executions.wait_for_execution = MagicMock(return_value=execution)
            self.invoke('cfy executions start mock_wf -d dep --json')
            get_events_logger_mock.assert_called_with(False)
        finally:
            self.client.executions.start = original_client_execution_start
            executions.wait_for_execution = original_wait_for_executions

    def test_executions_start_dep_env_pending(self):
        self._test_executions_start_dep_env(
            ex=DeploymentEnvironmentCreationPendingError('m'))

    def test_executions_start_dep_env_in_progress(self):
        self._test_executions_start_dep_env(
            ex=DeploymentEnvironmentCreationInProgressError('m'))

    def test_executions_start_dep_other_ex_sanity(self):
        try:
            self._test_executions_start_dep_env(ex=RuntimeError)
        except ClickInvocationException as e:
            self.assertIsInstance(e.exception, RuntimeError)

    def _test_executions_start_dep_env(self, ex):
        start_mock = MagicMock(side_effect=[ex, execution_mock('started')])
        self.client.executions.start = start_mock

        list_mock = MagicMock(return_value=[
            execution_mock('terminated', 'create_deployment_environment')])
        self.client.executions.list = list_mock

        wait_for_mock = MagicMock(return_value=execution_mock('terminated'))
        original_wait_for = executions.wait_for_execution
        try:
            executions.wait_for_execution = wait_for_mock
            self.invoke('cfy executions start mock_wf -d dep')
            self.assertEqual(wait_for_mock.mock_calls[0][1][1].workflow_id,
                             'create_deployment_environment')
            self.assertEqual(wait_for_mock.mock_calls[1][1][1].workflow_id,
                             'mock_wf')
        finally:
            executions.wait_for_execution = original_wait_for

    def test_local_execution_default_param(self):
        self._init_local_env()
        self._assert_outputs({'param': None})
        self.invoke(
            'cfy executions start {0} '
            '-b local'
            .format('run_test_op_on_nodes'))
        self._assert_outputs({'param': 'default_param'})

    def test_local_execution_custom_param_value(self):
        self._init_local_env()
        self.invoke(
            'cfy executions start {0} '
            '-b local '
            '-p param=custom_value'
            .format('run_test_op_on_nodes')
        )
        self._assert_outputs({'param': 'custom_value'})

    def test_local_execution_allow_custom_params(self):
        self._init_local_env()
        self.invoke(
            'cfy executions start {0} '
            '-b local '
            '-p custom_param=custom_value --allow-custom-parameters'
            .format('run_test_op_on_nodes')
        )
        self._assert_outputs(
            {'param': 'default_param', 'custom_param': 'custom_value'}
        )

    def test_local_execution_dont_allow_custom_params(self):
        self._init_local_env()
        self.invoke(
            'cfy executions start {0} '
            '-b local '
            '-p custom_param=custom_value'
            .format('run_test_op_on_nodes'),
            err_str_segment='Workflow "run_test_op_on_nodes" does not '
                            'have the following parameters declared: '
                            'custom_param',
            exception=ValueError
        )

    def _assert_outputs(self, expected_outputs):
        outcome = self.invoke('cfy deployments outputs -b local')
        output = json.loads(outcome.output)
        for key, value in expected_outputs.items():
            self.assertEqual(output[key], value)

    def _init_local_env(self):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )
        self.use_local_profile()
        self.invoke('cfy init {0}'.format(blueprint_path))


class OperationsTest(CliCommandTest):
    def test_get_operation(self):
        with patch.object(self.client.operations, 'get') as mock_get:
            mock_get.return_value = {
                'id': '11-22-33',
                'type': 'RemoteWorkflowTask',
            }
            out = self.invoke('executions operations get 11-22-33')
        mock_get.assert_called_with('11-22-33')
        assert 'RemoteWorkflowTask' in out.output

    def test_list_operations_exc_id(self):
        with patch.object(self.client.operations, 'list') as mock_list:
            self.invoke('executions operations list 1234-5678')
        kws = mock_list.mock_calls[0][2]
        assert kws['execution_id'] == '1234-5678'

    def test_list_operations_graph_id(self):
        with patch.object(self.client.operations, 'list') as mock_list:
            self.invoke('executions operations list --graph-id 1234-5678')
        kws = mock_list.mock_calls[0][2]
        assert not kws['execution_id']
        assert kws['graph_id'] == '1234-5678'

    def test_list_operations_show_internal(self):
        with patch.object(self.client.operations, 'list') as mock_list:
            self.invoke('executions operations list 1')
        kws = mock_list.mock_calls[0][2]
        assert kws.get('skip_internal', True)

        with patch.object(self.client.operations, 'list') as mock_list:
            self.invoke('executions operations list 1 --show-internal')
        kws = mock_list.mock_calls[0][2]
        assert not kws.get('skip_internal', True)

    def test_list_operations_state(self):
        with patch.object(self.client.operations, 'list') as mock_list:
            self.invoke('executions operations list 1')
        kws = mock_list.mock_calls[0][2]
        assert not kws.get('state')

        with patch.object(self.client.operations, 'list') as mock_list:
            self.invoke('executions operations list 1 --state xyz')
        kws = mock_list.mock_calls[0][2]
        assert kws['state'] == 'xyz'


class TasksGraphsTest(CliCommandTest):
    def test_list_execution_id(self):
        with patch.object(self.client.tasks_graphs, 'list') as mock_list:
            self.invoke('executions graphs list 1234-5678')
        kws = mock_list.mock_calls[0][2]
        assert kws['execution_id'] == '1234-5678'

    def test_list_name(self):
        with patch.object(self.client.tasks_graphs, 'list') as mock_list:
            self.invoke('executions graphs list 1234-5678')
        kws = mock_list.mock_calls[0][2]
        assert not kws.get('name')

        with patch.object(self.client.tasks_graphs, 'list') as mock_list:
            self.invoke('executions graphs list 1234-5678 --name install')
        kws = mock_list.mock_calls[0][2]
        assert kws['name'] == 'install'
