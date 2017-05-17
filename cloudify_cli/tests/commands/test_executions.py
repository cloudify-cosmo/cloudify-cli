import os

from mock import MagicMock, patch

from .. import cfy
from .mocks import execution_mock
from .constants import BLUEPRINTS_DIR, DEFAULT_BLUEPRINT_FILE_NAME
from .test_base import CliCommandTest
from ...commands import executions
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
        self.invoke('cfy executions get execution-id')

    def test_executions_list(self):
        self.client.executions.list = MagicMock(return_value=[])
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
            self.invoke('cfy executions start mock_wf -d dep --json-output')
            get_events_logger_mock.assert_called_with(True)
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
        except cfy.ClickInvocationException as e:
            self.assertEqual(str(RuntimeError), e.exception)

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
        self._assert_outputs({'param': 'null'})
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
        output = self.invoke(
            'cfy deployments outputs -b local').logs.split('\n')
        for key, value in expected_outputs.iteritems():
            if value == 'null':
                key_val_string = '  "{0}": {1}, '.format(key, value)
            else:
                key_val_string = '  "{0}": "{1}", '.format(key, value)
            self.assertIn(key_val_string, output)

    def _init_local_env(self):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )

        self.invoke('cfy init {0}'.format(blueprint_path))
        cfy.register_commands()
