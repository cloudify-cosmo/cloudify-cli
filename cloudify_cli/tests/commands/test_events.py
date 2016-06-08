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

"""
Tests all commands that start with 'cfy events'
"""

import json
import time
from StringIO import StringIO

from mock import patch

from cloudify_rest_client.executions import Execution

from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest
from cloudify_cli.tests.resources.mocks.mock_list_response \
    import MockListResponse


def mock_log_message_prefix(event):
    return event['event_name']


class EventsTest(CliCommandTest):

    def setUp(self):
        super(EventsTest, self).setUp()
        self.events = []
        self._create_cosmo_wd_settings()
        # execution will terminate after 10 seconds
        self.execution_start_time = time.time()
        self.execution_termination_time = self.execution_start_time + 10
        self.events = self._generate_events(self.execution_start_time,
                                            self.execution_termination_time)
        self.executions_status = Execution.STARTED

    def _generate_events(self, start_time, end_time):
        events = []
        event_time = start_time

        while event_time < end_time:
            event = {'event_name': 'test_event_{0}'.format(event_time)}
            events.append((event_time, event))
            event_time += 0.3

        success_event = {
            'event_name': 'test_event_{0}'.format(end_time),
            'event_type': 'workflow_succeeded'
        }
        events.append((end_time, success_event))
        return events

    def _get_events_before(self, end_time):
        return [event for event_time, event in self.events
                if event_time < end_time]

    def _mock_executions_get(self, execution_id):
        self.update_execution_status()
        if self.executions_status != Execution.TERMINATED:
            execution = Execution({'id': 'execution_id',
                                   'status': Execution.STARTED})

        else:
            execution = Execution({'id': 'execution_id',
                                   'status': Execution.TERMINATED})

        return execution

    def _mock_events_list(self, include_logs=False, message=None,
                          from_datetime=None, to_datetime=None, _include=None,
                          sort='@timestamp', **kwargs):
        from_event = kwargs.get('_offset', 0)
        batch_size = kwargs.get('_size', 100)
        events = self._get_events_before(time.time())
        return MockListResponse(
            events[from_event:from_event+batch_size], len(events))

    def update_execution_status(self):
        """ sets the execution status to TERMINATED when
        reaching execution_termination_time
        """
        if time.time() > self.execution_termination_time:
            self.executions_status = Execution.TERMINATED

    def _assert_events_displayed(self, events, output):
        expected_event_logs = []
        for event in events:
            expected_event_logs.append(event['event_name'])

        missing_events_error_message = \
            'command output does not contain all expected values.'\
            '\noutput: \n{0}\n'\
            '\nexpected: \n{1}\n'\
            .format(output, '\n'.join(expected_event_logs))

        self.assertTrue(all(event_log in output
                            for event_log in expected_event_logs),
                        missing_events_error_message)

    @patch('cloudify_cli.logger.logs.create_event_message_prefix',
           new=mock_log_message_prefix)
    def test_events_tail(self):
        self.client.executions.get = self._mock_executions_get
        self.client.events.list = self._mock_events_list

        stdout = StringIO()
        with patch('sys.stdout', stdout):
            cli_runner.run_cli(
                'cfy events list --tail --execution-id execution-id')
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
        stdout = StringIO()
        with patch('sys.stdout', stdout):
            cli_runner.run_cli(
                'cfy events list --execution-id execution-id {}'.format(flag))
        return stdout.getvalue()
