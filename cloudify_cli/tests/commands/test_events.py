import json
import time
from StringIO import StringIO

from mock import patch

from .test_base import CliCommandTest
from .mocks import MockListResponse, mock_log_message_prefix

from cloudify_rest_client import executions, deployments


class EventsTest(CliCommandTest):

    def setUp(self):
        super(EventsTest, self).setUp()
        self.events = []
        self.use_manager()
        # Execution will terminate after 10 seconds
        self.execution_start_time = time.time()
        self.execution_termination_time = self.execution_start_time + 1
        self.events = self._generate_events(self.execution_start_time,
                                            self.execution_termination_time)
        self.executions_status = executions.Execution.STARTED

    def _generate_events(self, start_time, end_time):
        events = []
        event_time = start_time
        event_count = 0

        while event_time < end_time:
            odd = event_count % 2
            event_type = 'cloudify_log' if odd else 'cloudify_event'

            deployment_id = 'deployment_id_{0}'.format(odd)  # 0/1
            event = {
                'event_name': 'test_event_{0}'.format(event_time),
                'deployment_id': deployment_id,
                'type': event_type
            }
            events.append((event_time, event))
            event_time += 0.3
            event_count += 1

        success_event = {
            'event_name': 'test_event_{0}'.format(end_time),
            'event_type': 'workflow_succeeded',
            'deployment_id': 'deployment_id_{0}'.format(0),
            'type': 'cloudify_event'
        }
        events.append((end_time, success_event))
        return events

    def _get_events_before(self, end_time, include_logs=True):
        events = [event for event_time, event in self.events
                if event_time < end_time]
        return filter(
            lambda event: include_logs or event['type'] == 'cloudify_event',
            events
        )

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
        events = self._get_events_before(time.time(), include_logs)
        return MockListResponse(
            events[from_event:from_event+batch_size], len(events))

    def _mock_events_delete(self, deployment_id, include_logs=False, **kwargs):
        events_before = len(self.events)
        events_to_delete = list()
        for event in self.events:
            if event[1]['deployment_id'] == deployment_id:
                if not include_logs and event[1]['type'] == 'cloudify_log':
                    continue
                events_to_delete.append(event)
        self.events[:] = [event for event in self.events if event
                          not in events_to_delete]
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

    @patch('cloudify_cli.logger.logs.create_event_message_prefix',
           new=mock_log_message_prefix)
    def test_events_no_logs(self):
        output = self._test_events('--no-logs')
        expected_events = self._get_events_before(time.time(), include_logs=False)
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
        if flag == '--json':
            return outcome.output
        return outcome.logs

    def _patch_clients_for_deletion(self):
        self.client.deployments.get = self._mock_deployments_get
        self.client.events.delete = self._mock_events_delete

    def test_delete_events(self):
        self._patch_clients_for_deletion()
        self.assertEqual(len(self.events), 5)

        outcome = self.invoke('cfy events delete deployment_id_1')
        self.assertEqual(outcome.logs.split('\n')[-1], 'Deleted 2 events')
        self.assertEqual(len(self.events), 3)

        outcome = self.invoke('cfy events delete deployment_id_0')
        self.assertEqual(outcome.logs.split('\n')[-1], 'Deleted 3 events')
        self.assertEqual(len(self.events), 0)

        outcome = self.invoke('cfy events delete deployment_id_0')
        self.assertEqual(outcome.logs.split('\n')[-1], 'No events to delete')
        self.assertEqual(len(self.events), 0)

    def test_delete_events_no_logs(self):
        self._patch_clients_for_deletion()
        self.assertEqual(len(self.events), 5)

        outcome = self.invoke('cfy events delete deployment_id_1 --no-logs')
        self.assertEqual(outcome.logs.split('\n')[-1], 'No events to delete')
        self.assertEqual(len(self.events), 5)

        outcome = self.invoke('cfy events delete deployment_id_0 --no-logs')
        self.assertEqual(outcome.logs.split('\n')[-1], 'Deleted 3 events')
        self.assertEqual(len(self.events), 2)

        outcome = self.invoke('cfy events delete deployment_id_0 --no-logs')
        self.assertEqual(outcome.logs.split('\n')[-1], 'No events to delete')
        self.assertEqual(len(self.events), 2)
