import os

from mock import MagicMock, patch

from ... import cfy
from ..mocks import execution_mock
from ..constants import BLUEPRINTS_DIR
from ..test_base import CliCommandTest
from .... import execution_events_fetcher
from cloudify_rest_client.exceptions import \
    DeploymentEnvironmentCreationPendingError, \
    DeploymentEnvironmentCreationInProgressError
from ....constants import DEFAULT_BLUEPRINT_FILE_NAME


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

    def test_executions_cancel(self):
        self.client.executions.cancel = MagicMock()
        self.invoke('cfy executions cancel e_id')

    @patch('cloudify_cli.logger.get_events_logger')
    def test_executions_start_json(self, get_events_logger_mock):
        execution = execution_mock('started')
        original = self.client.executions.start
        try:
            self.client.executions.start = MagicMock(return_value=execution)
            with patch('cloudify_cli.execution_events_fetcher.wait_for_execution',
                       return_value=execution):
                self.invoke('cfy executions start mock_wf -d dep --json')
            get_events_logger_mock.assert_called_with(True)
        finally:
            self.client.executions.start = original

    def test_executions_start_dep_env_pending(self):
        self._test_executions_start_dep_env(
            ex=DeploymentEnvironmentCreationPendingError('m'))

    def test_executions_start_dep_env_in_progress(self):
        self._test_executions_start_dep_env(
            ex=DeploymentEnvironmentCreationInProgressError('m'))

    def test_executions_start_dep_other_ex_sanity(self):
        try:
            self._test_executions_start_dep_env(ex=RuntimeError)
        except cfy.ClickInvocationException, e:
            self.assertEqual(str(RuntimeError), e.exception)

    def _test_executions_start_dep_env(self, ex):
        start_mock = MagicMock(side_effect=[ex, execution_mock('started')])
        self.client.executions.start = start_mock

        list_mock = MagicMock(return_value=[
            execution_mock('terminated', 'create_deployment_environment')])
        self.client.executions.list = list_mock

        wait_for_mock = MagicMock(return_value=execution_mock('terminated'))
        original_wait_for = execution_events_fetcher.wait_for_execution
        try:
            execution_events_fetcher.wait_for_execution = wait_for_mock
            self.invoke('cfy executions start mock_wf -d dep')
            self.assertEqual(wait_for_mock.mock_calls[0][1][1].workflow_id,
                             'create_deployment_environment')
            self.assertEqual(wait_for_mock.mock_calls[1][1][1].workflow_id,
                             'mock_wf')
        finally:
            execution_events_fetcher.wait_for_execution = original_wait_for

    def test_local_execution_default_param(self):
        self._init_local_env()
        self._assert_outputs({'param': 'null'})
        self.invoke('cfy executions start {0}'.format('run_test_op_on_nodes'))
        self._assert_outputs({'param': 'default_param'})

    def test_local_execution_custom_param_value(self):
        self._init_local_env()
        self.invoke('cfy executions start {0} -p param=custom_value'.format(
            'run_test_op_on_nodes')
        )
        self._assert_outputs({'param': 'custom_value'})

    def test_local_execution_allow_custom_params(self):
        self._init_local_env()
        self.invoke('cfy executions start {0} '
                    '-p custom_param=custom_value --allow-custom-parameters'
                    ''.format('run_test_op_on_nodes')
                    )
        self._assert_outputs(
            {'param': 'default_param', 'custom_param': 'custom_value'}
        )

    def test_local_execution_dont_allow_custom_params(self):
        self._init_local_env()
        self.invoke(
            'cfy executions start {0} -p custom_param=custom_value'.format(
                'run_test_op_on_nodes'
            ),
            err_str_segment='Workflow "run_test_op_on_nodes" does not '
                            'have the following parameters declared: '
                            'custom_param',
            exception=ValueError
        )

    def _assert_outputs(self, expected_outputs):
        output = self.invoke('cfy deployments outputs').logs.split('\n')
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
        self.register_commands()