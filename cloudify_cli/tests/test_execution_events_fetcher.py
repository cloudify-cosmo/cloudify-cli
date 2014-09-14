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
from cloudify_cli.execution_events_fetcher import ExecutionEventsFetcher
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

    def test_single_batch(self):
        self.events = range(0, 10)
        execution_events = ExecutionEventsFetcher(self.client, 'execution_id')
        events = execution_events.fetch_events()
        self.assertListEqual(self.events, events)

    def test_several_batches(self):
        self.events = range(0, 10)
        execution_events = ExecutionEventsFetcher(self.client,
                                                  'execution_id',
                                                  batch_size=2)
        all_events = []
        for i in range(0, 5):
            events = execution_events.fetch_events()
            self.assertEqual(2, len(events))
            all_events.extend(events)
        events = execution_events.fetch_events()
        self.assertEqual(0, len(events))
        self.assertListEqual(self.events, all_events)

    def test_no_events(self):
        execution_events = ExecutionEventsFetcher(self.client,
                                                  'execution_id',
                                                  batch_size=2)
        events = execution_events.fetch_events()
        self.assertEqual(0, len(events))

    def test_new_events_after_fetched_all(self):
        self.events = range(0, 10)
        execution_events = ExecutionEventsFetcher(self.client, 'execution_id')
        execution_events.fetch_events()
        added = range(20, 25)
        self.events.extend(range(20, 25))
        events = execution_events.fetch_events()
        self.assertListEqual(added, events)

    def test_get_remaining_events_single_batch(self):
        self.events = range(0, 10)
        execution_events = ExecutionEventsFetcher(self.client, 'execution_id')
        events = execution_events.fetch_events(get_remaining_events=True)
        self.assertListEqual(self.events, events)

    def test_get_remaining_events_several_batches(self):
        self.events = range(0, 10)
        execution_events = ExecutionEventsFetcher(self.client,
                                                  'execution_id',
                                                  batch_size=2)
        events = execution_events.fetch_events(get_remaining_events=True)
        self.assertListEqual(self.events, events)

    def test_get_remaining_events_timeout(self):
        self.events = range(0, 20)
        execution_events = ExecutionEventsFetcher(self.client,
                                                  'execution_id',
                                                  batch_size=1,
                                                  timeout=3)
        try:
            execution_events.fetch_events(get_remaining_events=True)
            self.fail()
        except RuntimeError:
            pass

    def test_events_progress(self):
        self.events = range(0, 5)
        execution_events = ExecutionEventsFetcher(self.client,
                                                  'execution_id',
                                                  batch_size=100)
        events = execution_events.fetch_events()
        self.assertEqual(5, len(events))
        self.events.extend(range(0, 10))
        events = execution_events.fetch_events()
        self.assertEqual(10, len(events))
        self.events.extend(range(0, 5))
        events = execution_events.fetch_events()
        self.assertEqual(5, len(events))
