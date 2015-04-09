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

from mock import patch
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest
from cloudify_rest_client.executions import Execution
import time
import threading


def mock_log_message_prefix(event):
    return event['event_name']


class EventsTest(CliCommandTest):

    events = []

    def setUp(self):
        super(EventsTest, self).setUp()
        self._create_cosmo_wd_settings()
        # execution will terminate after 10 seconds
        self.execution_termination_time = time.time() + 10
        self.executions_status = Execution.STARTED
        events_generator = threading.Thread(
            target=self.generate_events,
            args=(self.execution_termination_time,))
        events_generator.daemon = True
        events_generator.start()

    def generate_events(self, execution_termination_time):
        while time.time() < execution_termination_time:
            # to simulate a common events flow, sleep for 3 secs every 2 secs
            if len(EventsTest.events) > 0 and time.time() % 2 == 0:
                time.sleep(3)
            event = {'event_name': 'test_event_{0}'.format(time.time())}
            EventsTest.events.append(event)
            time.sleep(0.3)

    def _mock_executions_get(self, execution_id):
        self.update_execution_status()
        if self.executions_status != Execution.TERMINATED:
            execution = Execution({'id': 'execution_id',
                                   'status': Execution.STARTED})

        else:
            execution = Execution({'id': 'execution_id',
                                   'status': Execution.TERMINATED})

        return execution

    def _mock_events_get(self, execution_id, from_event=0,
                         batch_size=100, include_logs=False):
        if from_event >= len(EventsTest.events):
            return [], len(EventsTest.events)
        until_event = min(from_event + batch_size, len(EventsTest.events))
        return EventsTest.events[from_event:until_event], \
            len(EventsTest.events)

    def update_execution_status(self):
        """ sets the execution status to TERMINATED when
        reaching execution_termination_time
        """
        if time.time() > self.execution_termination_time:
            self.executions_status = Execution.TERMINATED

    @patch('cloudify_cli.logger.create_event_message_prefix',
           new=mock_log_message_prefix)
    def test_events_tail(self):
        self.client.executions.get = self._mock_executions_get
        self.client.events.get = self._mock_events_get

        out = cli_runner.run_cli(
            'cfy events list --tail --execution-id execution-id')

        expected_event_logs = []
        for event in EventsTest.events:
            expected_event_logs.append(event['event_name'])

        missing_events_error_message = \
            'command output does not contain all expected values.'\
            '\noutput: \n{0}\n'\
            '\nexpected: \n{1}\n'\
            .format(out, '\n'.join(expected_event_logs))

        self.assertTrue(all(event_log in out
                            for event_log in expected_event_logs),
                        missing_events_error_message)

    @patch('cloudify_cli.logger.create_event_message_prefix',
           new=mock_log_message_prefix)
    def test_events(self):
        self.client.executions.get = self._mock_executions_get
        self.client.events.get = self._mock_events_get
        cli_runner.run_cli('cfy events list --execution-id execution-id')
        # TODO assert something here...
