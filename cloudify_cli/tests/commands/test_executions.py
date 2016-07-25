########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

from uuid import uuid4
from datetime import datetime

from mock import patch
from mock import MagicMock

from cloudify_rest_client import exceptions
from cloudify_rest_client.executions import Execution

from cloudify_cli.commands import executions

from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class ExecutionsTest(CliCommandTest):

    def setUp(self):
        super(ExecutionsTest, self).setUp()
        self.create_cosmo_wd_settings()

    def test_executions_get(self):
        execution = execution_mock('terminated')
        self.client.executions.get = MagicMock(return_value=execution)
        self.invoke('cfy executions get execution-id')

    def test_executions_list(self):
        self.client.executions.list = MagicMock(return_value=[])
        self.invoke('cfy executions list deployment-id')

    def test_executions_cancel(self):
        self.client.executions.cancel = MagicMock()
        self.invoke('cfy executions cancel e_id')

    @patch('cloudify_cli.logger.get_events_logger')
    def test_executions_start_json(self, get_events_logger_mock):
        execution = execution_mock('started')
        self.client.executions.start = MagicMock(return_value=execution)
        with patch('cloudify_cli.execution_events_fetcher.wait_for_execution',
                   return_value=execution):
            self.invoke('cfy executions start mock_wf -d dep --json')
        get_events_logger_mock.assert_called_with(True)

    def test_executions_start_dep_env_pending(self):
        self._test_executions_start_dep_env(
            ex=exceptions.DeploymentEnvironmentCreationPendingError('m'))

    def test_executions_start_dep_env_in_progress(self):
        self._test_executions_start_dep_env(
            ex=exceptions.DeploymentEnvironmentCreationInProgressError('m'))

    def test_executions_start_dep_other_ex_sanity(self):
        self.assertRaises(RuntimeError, self._test_executions_start_dep_env,
                          ex=RuntimeError)

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


def execution_mock(status, wf_id='mock_wf'):
    return Execution({
        'status': status,
        'workflow_id': wf_id,
        'deployment_id': 'deployment-id',
        'blueprint_id': 'blueprint-id',
        'error': '',
        'id': uuid4(),
        'created_at': datetime.now().isoformat()[:-3],
        'parameters': {}
    })
