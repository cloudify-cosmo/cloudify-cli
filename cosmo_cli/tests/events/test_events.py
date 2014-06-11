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

__author__ = 'idanmo'


import unittest

from cosmo_cli.executions import ExecutionEvents
from cloudify_rest_client import CloudifyClient


class MockExecutionsClient(object):

    def get(self, execution_id):
        pass


class MockEventsClient(object):

    def __init__(self, mock_events):
        self._mock_events = mock_events

    def get(self, execution_id, from_event=0,
            batch_size=100, include_logs=False):
        if from_event >= len(self._mock_events):
            return [], len(self._mock_events)
        until_event = min(from_event + batch_size, len(self._mock_events))
        return \
            self._mock_events[from_event:until_event], len(self._mock_events)


class MockClient(CloudifyClient):

    def __init__(self, mock_events):
        self.executions = MockExecutionsClient()
        self.events = MockEventsClient(mock_events)


class ExecutionEventsTest(unittest.TestCase):

    def test_single_batch(self):
        mock_events = range(0, 10)
        client = MockClient(mock_events)
        execution_events = ExecutionEvents(client, 'execution_id')
        events = execution_events.fetch_events()
        self.assertListEqual(mock_events, events)

    def test_several_batches(self):
        mock_events = range(0, 10)
        client = MockClient(mock_events)
        execution_events = ExecutionEvents(client,
                                           'execution_id',
                                           batch_size=2)
        all_events = []
        for i in range(0, 5):
            events = execution_events.fetch_events()
            self.assertEqual(2, len(events))
            all_events.extend(events)
        events = execution_events.fetch_events()
        self.assertEqual(0, len(events))
        self.assertListEqual(mock_events, all_events)

    def test_no_events(self):
        mock_events = []
        client = MockClient(mock_events)
        execution_events = ExecutionEvents(client,
                                           'execution_id',
                                           batch_size=2)
        events = execution_events.fetch_events()
        self.assertEqual(0, len(events))

    def test_new_events_after_fetched_all(self):
        mock_events = range(0, 10)
        client = MockClient(mock_events)
        execution_events = ExecutionEvents(client, 'execution_id')
        execution_events.fetch_events()
        added = range(20, 25)
        mock_events.extend(range(20, 25))
        events = execution_events.fetch_events()
        self.assertListEqual(added, events)

    def test_get_remaining_events_single_batch(self):
        mock_events = range(0, 10)
        client = MockClient(mock_events)
        execution_events = ExecutionEvents(client, 'execution_id')
        events = execution_events.fetch_events(get_remaining_events=True)
        self.assertListEqual(mock_events, events)

    def test_get_remaining_events_several_batches(self):
        mock_events = range(0, 10)
        client = MockClient(mock_events)
        execution_events = ExecutionEvents(client,
                                           'execution_id',
                                           batch_size=2)
        events = execution_events.fetch_events(get_remaining_events=True)
        self.assertListEqual(mock_events, events)

    def test_get_remaining_events_timeout(self):
        mock_events = range(0, 20)
        client = MockClient(mock_events)
        execution_events = ExecutionEvents(client,
                                           'execution_id',
                                           batch_size=1,
                                           timeout=3)
        try:
            execution_events.fetch_events(get_remaining_events=True)
            self.fail()
        except RuntimeError:
            pass

    def test_events_progress(self):
        mock_events = range(0, 5)
        client = MockClient(mock_events)
        execution_events = ExecutionEvents(client,
                                           'execution_id',
                                           batch_size=100)
        events = execution_events.fetch_events()
        self.assertEqual(5, len(events))
        mock_events.extend(range(0, 10))
        events = execution_events.fetch_events()
        self.assertEqual(10, len(events))
        mock_events.extend(range(0, 5))
        events = execution_events.fetch_events()
        self.assertEqual(5, len(events))
