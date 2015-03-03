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

import unittest

from mock import MagicMock
from cloudify_cli.execution_events_fetcher import ExecutionEventsFetcher, \
    wait_for_execution
from cloudify_cli.exceptions import EventProcessingTimeoutError, \
    ExecutionTimeoutError
from cloudify_rest_client.client import CloudifyClient


class ExecutionEventsFetcherTest(unittest.TestCase):

    events = []

    def setUp(self):
        self.client = CloudifyClient()
        self.client.executions.get = MagicMock()
        self.client.events.get = self._mock_get

    def _mock_get(self, execution_id, from_event=0,
                  batch_size=100, include_logs=False):
        if from_event >= len(self.events):
            return [], len(self.events)
        until_event = min(from_event + batch_size, len(self.events))
        return self.events[from_event:until_event], len(self.events)

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
        self.events = range(0, 20)
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
        self.events = range(0, 5)
        mock_execution = self.client.executions.get('deployment_id')
        self.assertRaises(ExecutionTimeoutError, wait_for_execution,
                          self.client, 'deployment_id', mock_execution,
                          timeout=2)

    def test_wait_for_execution_expect_event_processing_timeout(self):
        self.events = range(0, 1000)
        mock_execution = self.client.executions.get('deployment_id')
        self.assertRaises(EventProcessingTimeoutError,
                          wait_for_execution,
                          self.client, 'deployment_id', mock_execution,
                          timeout=3)