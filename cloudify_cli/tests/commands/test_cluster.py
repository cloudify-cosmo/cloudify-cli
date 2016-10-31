########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import mock
import unittest

from cloudify_rest_client.cluster import ClusterState

from .test_base import CliCommandTest
from ...exceptions import CloudifyCliError
from ...commands.cluster import _wait_for_cluster_initialized
from ...execution_events_fetcher import WAIT_FOR_EXECUTION_SLEEP_INTERVAL


class WaitForClusterTest(unittest.TestCase):
    def test_polls_until_done(self):
        """The CLI stops polling when the cluster is initialized."""

        client = mock.Mock()
        # prepare a mock "cluster.status()" method that will return
        # initialized = False on the first 4 calls, and initialized = True
        # on the 5th call
        client.cluster.status = mock.Mock(
            side_effect=[ClusterState({'initialized': False})] * 4 +
                        [ClusterState({'initialized': True})])

        with mock.patch('cloudify_cli.commands.cluster.time'):
            status = _wait_for_cluster_initialized(client)
        self.assertEqual(5, len(client.cluster.status.mock_calls))
        self.assertTrue(status['initialized'])

    def test_stops_at_timeout(self):
        """If the cluster is never started, polling stops at timeout."""
        timeout = 900
        client = mock.Mock()
        client.cluster.status = mock.Mock(
            return_value=ClusterState({'initialized': False}))

        with mock.patch('cloudify_cli.commands.cluster.time') as mock_time:
            with self.assertRaises(CloudifyCliError) as cm:
                _wait_for_cluster_initialized(client, timeout=timeout)

        self.assertIn('timed out', cm.exception.message.lower())
        # there should be (timeout//interval) time.sleep(interval) calls,
        # so the total time waited is equal to timeout
        self.assertEqual(timeout // WAIT_FOR_EXECUTION_SLEEP_INTERVAL,
                         len(mock_time.sleep.mock_calls))

    def test_passes_log_cursor(self):
        # prepare mock status responses containing logs. The first status
        # contains logs that end at cursor=1, so the next call needs to provide
        # since='1'. The 2nd status has cursor=2 and 3, so the next call needs
        # to be since='3'. The next call returns no logs at all, so since stays
        # '3'.
        status_responses = [
            ClusterState({
                'initialized': False,
                'logs': [{'timestamp': 1, 'message': 'a', 'cursor': '1'}]
            }),
            ClusterState({
                'initialized': False,
                'logs': [{'timestamp': 1, 'message': 'a', 'cursor': '2'},
                         {'timestamp': 1, 'message': 'a', 'cursor': '3'}]
            }),
            ClusterState({'initialized': False}),
            ClusterState({
                'initialized': True,
                'logs': [{'timestamp': 1, 'message': 'a', 'cursor': '4'}]
            })
        ]
        client = mock.Mock()
        client.cluster.status = mock.Mock(side_effect=status_responses)

        with mock.patch('cloudify_cli.commands.cluster.time'):
            _wait_for_cluster_initialized(client, logger=mock.Mock())
        self.assertEqual(4, len(client.cluster.status.mock_calls))

        since_passed = [kw['since'] for _, _, kw in
                        client.cluster.status.mock_calls]

        self.assertEqual([None, '1', '3', '3'], since_passed)


class ClusterStartTest(CliCommandTest):
    def test_already_in_cluster(self):
        self.client.cluster.status = mock.Mock(
            return_value=ClusterState({'initialized': True}))
        self.invoke('cfy cluster start --cluster-host-ip 1.2.3.4',
                    'already part of a HA cluster')

    def test_start_success(self):
        self.client.cluster.status = mock.Mock(side_effect=[
            ClusterState({'initialized': False}),
            ClusterState({'initialized': True}),
        ])
        self.client.cluster.start = mock.Mock()
        outcome = self.invoke('cfy cluster start --cluster-host-ip 1.2.3.4')
        self.assertIn('HA cluster started', outcome.logs)

    def test_start_success_with_logs(self):
        self.client.cluster.status = mock.Mock(side_effect=[
            ClusterState({'initialized': False}),
            ClusterState({
                'initialized': False,
                'logs': [{'timestamp': 1, 'message': 'one log message',
                          'cursor': '1'}]
            }),
            ClusterState({'initialized': True}),
        ])
        self.client.cluster.start = mock.Mock()
        with mock.patch('cloudify_cli.commands.cluster.time'):
            outcome = self.invoke(
                'cfy cluster start --cluster-host-ip 1.2.3.4')
        self.assertIn('HA cluster started', outcome.logs)
        self.assertIn('one log message', outcome.logs)

    def test_start_error(self):
        self.client.cluster.status = mock.Mock(side_effect=[
            ClusterState({'initialized': False}),
            ClusterState({'error': 'some error happened'}),
        ])
        self.client.cluster.start = mock.Mock()
        self.invoke('cfy cluster start --cluster-host-ip 1.2.3.4',
                    'some error happened')
