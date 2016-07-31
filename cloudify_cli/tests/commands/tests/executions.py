import json
import time
from StringIO import StringIO

from mock import MagicMock, patch

from .... import execution_events_fetcher
from ... import cfy
from ..mocks import execution_mock, MockListResponse, \
    mock_log_message_prefix
from ..test_base import CliCommandTest
from cloudify_rest_client import deployments, executions
from cloudify_rest_client.exceptions import CloudifyClientError, \
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


class WorkflowsTest(CliCommandTest):
    def setUp(self):
        super(WorkflowsTest, self).setUp()
        self.use_manager()

    def test_workflows_list(self):
        deployment = deployments.Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'workflows': [
                {
                    'created_at': None,
                    'name': 'mock_workflow',
                    'parameters': {
                        'test-key': {
                            'default': 'test-value'
                        },
                        'test-mandatory-key': {},
                        'test-nested-key': {
                            'default': {
                                'key': 'val'
                            }
                        }
                    }
                }
            ]
        })

        self.client.deployments.get = MagicMock(return_value=deployment)
        self.invoke('cfy workflows list -d a-deployment-id')

    def test_workflows_sort_list(self):

        deployment = deployments.Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'workflows': [
                {
                    'created_at': None,
                    'name': 'my_workflow_1',
                    'parameters': {
                        'test-key': {
                            'default': 'test-value'
                        },
                        'test-mandatory-key': {},
                        'test-nested-key': {
                            'default': {
                                'key': 'val'
                            }
                        }
                    }
                },
                {
                    'created_at': None,
                    'name': 'my_workflow_0',
                    'parameters': {
                        'test-key': {
                            'default': 'test-value'
                        },
                        'test-mandatory-key': {},
                        'test-nested-key': {
                            'default': {
                                'key': 'val'
                            }
                        }
                    }
                }
            ]
        })

        self.client.deployments.get = MagicMock(return_value=deployment)

        output = self.invoke('cfy workflows list -d a-deployment-id').logs
        first = output.find('my_workflow_0')
        second = output.find('my_workflow_1')
        self.assertTrue(0 < first < second)

    def test_workflows_get(self):
        deployment = deployments.Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'workflows': [
                {
                    'created_at': None,
                    'name': 'mock_workflow',
                    'parameters': {
                        'test-key': {
                            'default': 'test-value'
                        },
                        'test-mandatory-key': {},
                        'test-nested-key': {
                            'default': {
                                'key': 'val'
                            }
                        }
                    }
                }
            ]
        })

        self.client.deployments.get = MagicMock(return_value=deployment)
        self.invoke('cfy workflows get mock_workflow -d dep_id')

    def test_workflows_get_nonexistent_workflow(self):

        expected_message = 'Workflow nonexistent_workflow not found'
        deployment = deployments.Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'workflows': [
                {
                    'created_at': None,
                    'name': 'mock_workflow',
                    'parameters': {
                        'test-key': {
                            'default': 'test-value'
                        },
                        'test-mandatory-key': {},
                        'test-nested-key': {
                            'default': {
                                'key': 'val'
                            }
                        }
                    }
                }
            ]
        })

        self.client.deployments.get = MagicMock(return_value=deployment)
        self.invoke('cfy workflows get nonexistent_workflow -d dep_id',
                    expected_message)

    def test_workflows_get_nonexistent_deployment(self):

        expected_message = \
            "Deployment 'nonexistent-dep' not found on manager server"

        self.client.deployments.get = MagicMock(
            side_effect=CloudifyClientError(expected_message))
        self.invoke('cfy workflows get wf -d nonexistent-dep -v',
                    err_str_segment=expected_message,
                    exception=CloudifyClientError)


class EventsTest(CliCommandTest):

    def setUp(self):
        super(EventsTest, self).setUp()
        self.events = []
        self.use_manager()
        # Execution will terminate after 10 seconds
        self.execution_start_time = time.time()
        self.execution_termination_time = self.execution_start_time + 10
        self.events = self._generate_events(self.execution_start_time,
                                            self.execution_termination_time)
        self.executions_status = executions.Execution.STARTED

    def _generate_events(self, start_time, end_time):
        events = []
        event_time = start_time
        event_count = 0

        while event_time < end_time:
            deployment_id = 'deployment_id_{0}'.format(event_count % 2)  # 0/1
            event = {'event_name': 'test_event_{0}'.format(event_time),
                     'deployment_id': deployment_id}
            events.append((event_time, event))
            event_time += 0.3
            event_count += 1

        success_event = {
            'event_name': 'test_event_{0}'.format(end_time),
            'event_type': 'workflow_succeeded',
            'deployment_id': 'deployment_id_{0}'.format(event_count % 2)
        }
        events.append((end_time, success_event))
        return events

    def _get_events_before(self, end_time):
        return [event for event_time, event in self.events
                if event_time < end_time]

    def _mock_executions_get(self, execution_id):
        self.update_execution_status()
        if self.executions_status != executions.Execution.TERMINATED:
            execution = executions.Execution({'id': 'execution_id',
                                   'status': executions.Execution.STARTED})
        else:
            execution = executions.Execution({'id': 'execution_id',
                                   'status': executions.Execution.TERMINATED})

        return execution

    def _mock_deployments_get(self, deployment_id):
        return deployments.Deployment({'id': deployment_id})

    def _mock_events_list(self, include_logs=False, message=None,
                           from_datetime=None, to_datetime=None, _include=None,
                           sort='@timestamp', **kwargs):
        from_event = kwargs.get('_offset', 0)
        batch_size = kwargs.get('_size', 100)
        events = self._get_events_before(time.time())
        return MockListResponse(
            events[from_event:from_event+batch_size], len(events))

    def _mock_events_delete(self, deployment_id, **kwargs):
        events_before = len(self.events)
        self.events = [event for event in self.events if
                       event[1]['deployment_id'] != deployment_id]
        events_after = len(self.events)

        class DeletedEvents(object):
            def __init__(self, deleted_events_count):
                self.items = [deleted_events_count]

        return DeletedEvents(events_before - events_after)

    def update_execution_status(self):
        """Sets the execution status to TERMINATED when
        reaching execution_termination_time
        """
        if time.time() > self.execution_termination_time:
            self.executions_status = executions.Execution.TERMINATED

    def _assert_events_displayed(self, events, output):
        expected_event_logs = []
        for event in events:
            expected_event_logs.append(event['event_name'])

        missing_events_error_message = (
            'Command output does not contain all expected values.'
            '\nOutput: \n{0}\n'
            '\nExpected: \n{1}\n'
            .format(output, '\n'.join(expected_event_logs)))

        self.assertTrue(
            all(event_log in output for event_log in expected_event_logs),
            missing_events_error_message)

    @patch('cloudify_cli.logger.logs.create_event_message_prefix',
           new=mock_log_message_prefix)
    def test_events_tail(self):
        self.client.executions.get = self._mock_executions_get
        self.client.events.list = self._mock_events_list

        # Since we're tailing stdout here, we have to patch it.
        # Can't just read the output once.
        stdout = StringIO()
        with patch('sys.stdout', stdout):
            self.invoke('cfy events list execution-id --tail')
        output = stdout.getvalue()
        expected_events = self._get_events_before(
            self.execution_termination_time)

        self._assert_events_displayed(expected_events, output)

    @patch('cloudify_cli.logger.logs.create_event_message_prefix',
           new=mock_log_message_prefix)
    def test_events(self):
        output = self._test_events()
        expected_events = self._get_events_before(time.time())
        self._assert_events_displayed(expected_events, output)

    def test_event_json(self):
        output = self._test_events(flag='--json')
        expected_events = self._get_events_before(time.time())
        self._assert_events_displayed(expected_events, output)
        for event in expected_events:
            self.assertIn(json.dumps(event), output)

    def _test_events(self, flag=''):
        self.client.executions.get = self._mock_executions_get
        self.client.events.list = self._mock_events_list
        outcome = self.invoke('cfy events list execution-id {0}'.format(
            flag))
        return outcome.output if flag else outcome.logs

    def _patch_clients_for_deletion(self):
        self.client.deployments.get = self._mock_deployments_get
        self.client.events.delete = self._mock_events_delete

    def test_delete_events(self):
        self._patch_clients_for_deletion()
        self.assertEqual(len(self.events), 35)

        outcome = self.invoke('cfy events delete deployment_id_1')
        self.assertEqual(outcome.logs.split('\n')[-1], 'Deleted 17 events')
        self.assertEqual(len(self.events), 18)

        outcome = self.invoke('cfy events delete deployment_id_0')
        self.assertEqual(outcome.logs.split('\n')[-1], 'Deleted 18 events')
        self.assertEqual(len(self.events), 0)

        outcome = self.invoke('cfy events delete deployment_id_0')
        self.assertEqual(outcome.logs.split('\n')[-1], 'No events to delete')
        self.assertEqual(len(self.events), 0)
