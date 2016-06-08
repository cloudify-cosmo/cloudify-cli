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

from itertools import chain, repeat, count
import unittest

from mock import MagicMock, patch
from cloudify_cli.execution_events_fetcher import ExecutionEventsFetcher, \
    wait_for_execution
from cloudify_cli.exceptions import EventProcessingTimeoutError, \
    ExecutionTimeoutError
from cloudify_rest_client.client import CloudifyClient
from cloudify_rest_client.executions import Execution

from cloudify_cli.tests.resources.mocks.mock_list_response \
    import MockListResponse


class ExecutionEventsFetcherTest(unittest.TestCase):

    events = []

    def setUp(self):
        self.client = CloudifyClient()
        self.client.executions.get = MagicMock()
        self.client.events.list = self._mock_list

    def _mock_list(self, include_logs=False, message=None,
                   from_datetime=None, to_datetime=None, _include=None,
                   sort='@timestamp', **kwargs):
        from_event = kwargs.get('_offset', 0)
        batch_size = kwargs.get('_size', 100)
        if from_event >= len(self.events):
            return MockListResponse([], len(self.events))
        until_event = min(from_event + batch_size, len(self.events))
        return MockListResponse(
            self.events[from_event:until_event], len(self.events))

    def test_no_events(self):
        events_fetcher = ExecutionEventsFetcher(self.client,
                                                'execution_id',
                                                batch_size=2)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(0, events_count)

    def test_new_events_after_fetched_all(self):
        self.events = range(0, 10)
        events_fetcher = ExecutionEventsFetcher(self.client, 'execution_id')
        events_fetcher.fetch_and_process_events()
        added_events = range(20, 25)
        self.events.extend(added_events)
        added_events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(added_events), added_events_count)

    def test_fetch_and_process_events_implicit_single_batch(self):
        self.events = range(0, 10)
        events_fetcher = ExecutionEventsFetcher(self.client, 'execution_id',
                                                batch_size=100)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(self.events), events_count)

    def test_fetch_and_process_events_implicit_several_batches(self):
        event_log = {}
        self.batch_counter = 0
        self.events = range(0, 5)

        def test_events_logger(events):
            self.batch_counter += 1
            for index in range(0, len(events)):
                event_log[events[index]] = 'event {0} of {1} in batch {2}'.\
                    format(index+1, len(events), self.batch_counter)

        events_fetcher = ExecutionEventsFetcher(self.client,
                                                'execution_id',
                                                batch_size=2)
        # internally this will get 10 events in 2 batches of 2 events each
        # and a last batch of 1 event
        events_count = events_fetcher.fetch_and_process_events(
            events_handler=test_events_logger)
        # assert all events were handled
        self.assertEqual(len(self.events), events_count)
        # assert batching was as expected (2*2, 1*1)
        event_log[self.events[0]] = 'event 1 of 2 in batch 1'
        event_log[self.events[1]] = 'event 2 of 2 in batch 1'
        event_log[self.events[2]] = 'event 1 of 2 in batch 2'
        event_log[self.events[3]] = 'event 2 of 2 in batch 2'
        event_log[self.events[4]] = 'event 1 of 1 in batch 3'
        # there shouldn't be any remaining events, verify that
        remaining_events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(0, remaining_events_count)

    def test_fetch_and_process_events_explicit_several_batches(self):
            total_events_count = 0
            self.events = range(0, 9)
            batch_size = 2
            events_fetcher = ExecutionEventsFetcher(self.client,
                                                    'execution_id',
                                                    batch_size=batch_size)
            for i in range(0, 4):
                events_batch_count = \
                    events_fetcher._fetch_and_process_events_batch()
                self.assertEqual(events_batch_count, batch_size)
                total_events_count += events_batch_count
            remaining_events_count = \
                events_fetcher._fetch_and_process_events_batch()
            self.assertEqual(remaining_events_count, 1)
            total_events_count += remaining_events_count
            self.assertEqual(len(self.events), total_events_count)

    def test_fetch_events_explicit_single_batch(self):
        self.events = range(0, 10)
        events_fetcher = ExecutionEventsFetcher(self.client, 'execution_id',
                                                batch_size=100)
        batch_events = events_fetcher._fetch_events_batch()
        self.assertListEqual(self.events, batch_events)

    def test_fetch_events_explicit_several_batches(self):
        all_fetched_events = []
        self.events = range(0, 9)
        batch_size = 2
        events_fetcher = ExecutionEventsFetcher(self.client,
                                                'execution_id',
                                                batch_size=batch_size)

        for i in range(0, 4):
            events_batch = events_fetcher._fetch_events_batch()
            self.assertEqual(len(events_batch), batch_size)
            all_fetched_events.extend(events_batch)

        remaining_events_batch = events_fetcher._fetch_events_batch()
        self.assertEqual(len(remaining_events_batch), 1)
        all_fetched_events.extend(remaining_events_batch)
        self.assertEqual(self.events, all_fetched_events)

    def test_fetch_and_process_events_timeout(self):
        self.events = range(0, 2000000)
        events_fetcher = ExecutionEventsFetcher(self.client,
                                                'execution_id',
                                                batch_size=1)
        self.assertRaises(EventProcessingTimeoutError,
                          events_fetcher.fetch_and_process_events, timeout=2)

    def test_events_processing_progress(self):
        events_bulk1 = range(0, 5)
        self.events = events_bulk1
        events_fetcher = ExecutionEventsFetcher(self.client,
                                                'execution_id',
                                                batch_size=100)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(events_bulk1), events_count)
        events_bulk2 = range(0, 10)
        self.events.extend(events_bulk2)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(events_bulk2), events_count)
        events_bulk3 = range(0, 7)
        self.events.extend(events_bulk3)
        events_count = events_fetcher.fetch_and_process_events()
        self.assertEqual(len(events_bulk3), events_count)

    def test_wait_for_execution_timeout(self):
        self.events = [{'id': num} for num in range(0, 5)]
        mock_execution = self.client.executions.get('deployment_id')
        self.assertRaises(ExecutionTimeoutError, wait_for_execution,
                          self.client, mock_execution,
                          timeout=2)


class WaitForExecutionTests(unittest.TestCase):

    def setUp(self):
        self.client = CloudifyClient()

        time_patcher = patch('cloudify_cli.execution_events_fetcher.time')
        self.time = time_patcher.start()
        self.addCleanup(time_patcher.stop)
        # prepare mock time.time() calls - return 0, 1, 2, 3...
        self.time.time.side_effect = count(0)

    def test_wait_for_log_after_execution_finishes(self):
        """wait_for_execution continues polling logs, after execution status
        is terminated
        """

        # prepare mock executions.get() calls - first return a status='started'
        # then continue returning status='terminated'
        executions = chain(
            [MagicMock(status=Execution.STARTED)],
            repeat(MagicMock(status=Execution.TERMINATED))
        )

        # prepare mock events.get() calls - first return empty events 100 times
        # and only then return a 'workflow_succeeded' event
        events = chain(
            repeat(MockListResponse([], 0), 100),
            [MockListResponse([{'event_type': 'workflow_succeeded'}], 1)],
            repeat(MockListResponse([], 0))
        )

        self.client.executions.get = MagicMock(side_effect=executions)
        self.client.events.list = MagicMock(side_effect=events)

        mock_execution = MagicMock(status=Execution.STARTED)
        wait_for_execution(self.client, mock_execution, timeout=None)

        calls_count = len(self.client.events.list.mock_calls)
        self.assertEqual(calls_count, 101, """wait_for_execution didnt keep
            polling events after execution terminated (expected 101
            calls, got %d)""" % calls_count)

    def test_wait_for_execution_after_log_succeeded(self):
        """wait_for_execution continues polling the execution status,
        even after it received a "workflow succeeded" log
        """

        # prepare mock executions.get() calls - return a status='started'
        # execution the first 100 times, and then return a 'terminated' one
        executions = chain(
            [MagicMock(status=Execution.STARTED)] * 100,
            repeat(MagicMock(status=Execution.TERMINATED))
        )

        # prepare mock events.get() calls - return a 'workflow_succeeded'
        # immediately, and there's no events after that
        events = chain(
            [MockListResponse([{'event_type': 'workflow_succeeded'}], 1)],
            repeat(MockListResponse([], 0))
        )

        self.client.executions.get = MagicMock(side_effect=executions)
        self.client.events.list = MagicMock(side_effect=events)

        mock_execution = MagicMock(status=Execution.STARTED)
        wait_for_execution(self.client, mock_execution, timeout=None)

        calls_count = len(self.client.executions.get.mock_calls)
        self.assertEqual(calls_count, 101, """wait_for_execution didnt keep
            polling the execution status after it received a workflow_succeeded
            event (expected 101 calls, got %d)""" % calls_count)
