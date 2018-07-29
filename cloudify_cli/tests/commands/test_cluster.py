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

import os
import mock
import json
import tempfile
import unittest

from cloudify_rest_client.cluster import ClusterState, ClusterNode
from cloudify_rest_client.exceptions import NotClusterMaster

from ... import env
from .test_base import CliCommandTest
from ...exceptions import CloudifyCliError
from ...commands.cluster import (_wait_for_cluster_initialized,
                                 pass_cluster_client)
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

        with mock.patch('cloudify_cli.commands.cluster.time') as mock_time:
            mock_time.time.return_value = 0
            status = _wait_for_cluster_initialized(client)
        self.assertEqual(5, len(client.cluster.status.mock_calls))
        self.assertTrue(status['initialized'])

    def test_stops_at_timeout(self):
        """If the cluster is never started, polling stops at timeout."""
        timeout = 900
        clock = {'time': 1000}
        client = mock.Mock()
        client.cluster.status = mock.Mock(
            return_value=ClusterState({'initialized': False}))

        def _mock_sleep(n):
            clock['time'] += n

        def _mock_time():
            return clock['time']

        with mock.patch('cloudify_cli.commands.cluster.time') as mock_time:
            mock_time.sleep = mock.Mock(side_effect=_mock_sleep)
            mock_time.time = _mock_time

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

        with mock.patch('cloudify_cli.commands.cluster.time') as mock_time:
            mock_time.time.return_value = 1000
            _wait_for_cluster_initialized(client, logger=mock.Mock())
        self.assertEqual(4, len(client.cluster.status.mock_calls))

        since_passed = [kw['since'] for _, _, kw in
                        client.cluster.status.mock_calls]

        self.assertEqual([None, '1', '3', '3'], since_passed)


class ClusterStartTest(CliCommandTest):
    def setUp(self):
        super(ClusterStartTest, self).setUp()
        self.use_manager()

    def test_already_in_cluster(self):
        self.client.cluster.status = mock.Mock(
            return_value=ClusterState({'initialized': True}))
        self.invoke('cfy cluster start --cluster-host-ip 1.2.3.4',
                    'already part of a Cloudify Manager cluster')

    def test_start_success(self):
        self.client.cluster.status = mock.Mock(side_effect=[
            ClusterState({'initialized': False}),
            ClusterState({'initialized': True}),
        ])
        self.client.cluster.start = mock.Mock()
        outcome = self.invoke('cfy cluster start --cluster-host-ip 1.2.3.4')
        self.assertIn('cluster started', outcome.logs)

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
        with mock.patch('cloudify_cli.commands.cluster.time') as mock_time:
            mock_time.time.return_value = 1000
            outcome = self.invoke(
                'cfy cluster start --cluster-host-ip 1.2.3.4')
        self.assertIn('cluster started', outcome.logs)
        self.assertIn('one log message', outcome.logs)

    def test_start_error(self):
        self.client.cluster.status = mock.Mock(side_effect=[
            ClusterState({'initialized': False}),
            ClusterState({'error': 'some error happened'}),
        ])
        self.client.cluster.start = mock.Mock()
        self.invoke('cfy cluster start --cluster-host-ip 1.2.3.4',
                    'some error happened')

    def test_profile_updated(self):
        self.client.cluster.status = mock.Mock(side_effect=[
            ClusterState({'initialized': False}),
            ClusterState({'initialized': True}),
        ])
        self.client.cluster.start = mock.Mock()
        outcome = self.invoke('cfy cluster start --cluster-host-ip 1.2.3.4')
        self.assertIn('cluster started', outcome.logs)
        self.assertEqual(1, len(env.profile.cluster))
        self.assertEqual(env.profile.manager_ip,
                         env.profile.cluster[0]['manager_ip'])


class ClusterNodesTest(CliCommandTest):
    def setUp(self):
        super(ClusterNodesTest, self).setUp()
        self.use_manager()

    def test_list_nodes(self):
        self.client.cluster.status = mock.Mock(
            return_value=ClusterState({'initialized': True}))
        self.client.cluster.nodes.list = mock.Mock(return_value=[
            ClusterNode({'name': 'node name 1', 'host_ip': '1.2.3.4'})
        ])
        outcome = self.invoke('cfy cluster nodes list')
        self.assertIn('node name 1', outcome.output)

    def test_list_not_initialized(self):
        self.client.cluster.status = mock.Mock(
            return_value=ClusterState({'initialized': False}))
        self.invoke('cfy cluster nodes list',
                    'not part of a Cloudify Manager cluster')

    def test_set_node_cert(self):
        env.profile.cluster = [{'name': 'm1', 'manager_ip': '1.2.3.4'}]
        with tempfile.NamedTemporaryFile() as f:
            self.invoke('cfy cluster nodes set-certificate m1 {0}'
                        .format(f.name))

    def test_set_node_cert_doesnt_exist(self):
        env.profile.cluster = [{'name': 'm1', 'manager_ip': '1.2.3.4'}]
        self.invoke('cfy cluster nodes set-certificate m1 /tmp/not-a-file',
                    'does not exist')

    def test_set_node_cert_no_such_node(self):
        env.profile.cluster = [{'name': 'm1', 'manager_ip': '1.2.3.4'}]
        with tempfile.NamedTemporaryFile() as f:
            self.invoke('cfy cluster nodes set-certificate not-a-node {0}'
                        .format(f.name),
                        'not found in the cluster profile')

    def test_get_node(self):
        self.client.cluster.status = mock.Mock(
            return_value=ClusterState({'initialized': True}))
        self.client.cluster.nodes.details = mock.Mock(return_value={
            'id': 'm1',
            'options': {
                'option1': 'value1'
            }
        })
        outcome = self.invoke('cluster nodes get m1')
        self.assertIn('value1', outcome.output)

    def test_get_node_json(self):
        self.client.cluster.status = mock.Mock(
            return_value=ClusterState({'initialized': True}))
        self.client.cluster.nodes.details = mock.Mock(return_value={
            'id': 'm1',
            'options': {
                'option1': 'value1'
            }
        })
        outcome = self.invoke('cluster nodes get m1 --json')
        parsed = json.loads(outcome.output)
        self.assertEqual(parsed['options'], {'option1': 'value1'})


class ClusterJoinTest(CliCommandTest):
    def setUp(self):
        super(ClusterJoinTest, self).setUp()
        self.use_manager()

        self.master_profile = env.ProfileContext()
        self.master_profile.manager_ip = 'master_profile'
        self.master_profile.cluster = [{'manager_ip': '1.2.3.4'}]
        self.master_profile.save()

    def test_join_success(self):
        self.client.cluster.status = mock.Mock(side_effect=[
            ClusterState({'initialized': False}),
            NotClusterMaster('not cluster master')
        ])
        self.client.cluster.nodes.list = mock.Mock(return_value=[
            ClusterNode({'host_ip': '10.10.1.10', 'online': True})
        ])
        self.client.cluster.nodes.add = mock.Mock(return_value=ClusterNode({
            'credentials': 'abc'
        }))

        self.client.cluster.join = mock.Mock()
        outcome = self.invoke('cfy cluster join {0}'
                              .format(self.master_profile.manager_ip))
        self.assertIn('joined cluster', outcome.logs)

    def test_join_profile_updated(self):
        self.client.cluster.status = mock.Mock(side_effect=[
            ClusterState({'initialized': False}),
            NotClusterMaster('not cluster master')
        ])
        self.client.cluster.nodes.add = mock.Mock(return_value=ClusterNode({
            'credentials': 'abc'
        }))

        self.client.cluster.nodes.list = mock.Mock(return_value=[
            ClusterNode({'host_ip': '10.10.1.10', 'online': True})
        ])
        self.client.cluster.join = mock.Mock()
        outcome = self.invoke('cfy cluster join {0}'
                              .format(self.master_profile.manager_ip))
        self.assertIn('joined cluster', outcome.logs)

        master_profile = env.get_profile_context('master_profile')
        self.assertEqual(2, len(master_profile.cluster))
        self.assertEqual(env.profile.manager_ip,
                         master_profile.cluster[1]['manager_ip'])

    def test_join_origin_profile_updated(self):
        self.client.cluster.status = mock.Mock(side_effect=[
            ClusterState({'initialized': False}),
            NotClusterMaster('not cluster master')
        ])
        self.client.cluster.nodes.add = mock.Mock(return_value=ClusterNode({
            'credentials': 'abc'
        }))
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write('cert or key here\n')
        self.addCleanup(os.unlink, f.name)
        self.master_profile.cluster[0]['ssh_key'] = f.name
        self.master_profile.save()

        self.client.cluster.nodes.list = mock.Mock(return_value=[
            ClusterNode({'host_ip': '10.10.1.10', 'online': True})
        ])
        self.client.cluster.join = mock.Mock()
        outcome = self.invoke('cfy cluster join {0}'
                              .format(self.master_profile.manager_ip))
        self.assertIn('joined cluster', outcome.logs)

        self.assertEqual(2, len(env.profile.cluster))

        joined_node = env.profile.cluster[1]
        self.assertEqual('10.10.1.10', joined_node['manager_ip'])

        master_node = env.profile.cluster[0]
        self.assertIn('ssh_key', master_node)
        # check that the master's ssh key was copied to the local profile's
        # workdir
        self.assertTrue(master_node['ssh_key'].startswith(env.profile.workdir))

    def test_join_duplicate_name(self):
        self.client.cluster.status = mock.Mock(side_effect=[
            ClusterState({'initialized': False}),
            ClusterState({}),
        ])
        self.client.cluster.nodes.list = mock.Mock(return_value=[
            ClusterNode({'host_ip': '10.10.1.10', 'online': True, 'name': 'n'})
        ])

        self.client.cluster.join = mock.Mock()
        self.invoke('cfy cluster join {0} --cluster-node-name n'
                    .format(self.master_profile.manager_ip),
                    'is already a member of the cluster')


class UpdateProfileTest(CliCommandTest):
    def setUp(self):
        super(UpdateProfileTest, self).setUp()
        self.use_manager()
        env.profile.cluster = [{'manager_ip': env.profile.manager_ip,
                                'name': 'master'}]
        env.profile.save()

    def test_nodes_added_to_profile(self):
        self.client.cluster.status = mock.Mock(
            return_value=ClusterState({'initialized': True}))
        self.client.cluster.nodes.list = mock.Mock(return_value=[
            ClusterNode({'name': 'master',
                         'host_ip': env.profile.manager_ip}),
            ClusterNode({'name': 'node name 1', 'host_ip': '1.2.3.4'}),
            ClusterNode({'name': 'node name 2', 'host_ip': '5.6.7.8'})
        ])
        self.client.cluster.join = mock.Mock()

        outcome = self.invoke('cfy cluster update-profile')
        self.assertIn('Adding cluster node 1.2.3.4', outcome.logs)
        self.assertIn('Adding cluster node 5.6.7.8', outcome.logs)

        self.assertEqual(env.profile.cluster, [
            {'manager_ip': env.profile.manager_ip, 'name': 'master'},
            {'manager_ip': '1.2.3.4', 'name': 'node name 1'},
            {'manager_ip': '5.6.7.8', 'name': 'node name 2'}
        ])

    def test_nodes_removed_from_profile(self):
        self.client.cluster.status = mock.Mock(
            return_value=ClusterState({'initialized': True}))
        self.client.cluster.nodes.list = mock.Mock(return_value=[
            ClusterNode({'name': 'node name 1', 'host_ip': '1.2.3.4'}),
            ClusterNode({'name': 'node name 2', 'host_ip': '5.6.7.8'})
        ])
        self.client.cluster.join = mock.Mock()

        self.invoke('cfy cluster update-profile')
        self.assertEqual(env.profile.cluster, [
            {'manager_ip': '1.2.3.4', 'name': 'node name 1'},
            {'manager_ip': '5.6.7.8', 'name': 'node name 2'}
        ])

    def test_set_node_cert(self):
        env.profile.cluster.append({'manager_ip': '1.2.3.4', 'name': 'node2'})
        env.profile.save()
        with tempfile.NamedTemporaryFile() as f:
            self.invoke('cfy cluster nodes set-certificate {0} {1}'
                        .format('master', f.name))
        with tempfile.NamedTemporaryFile() as f2:
            self.invoke('cfy cluster nodes set-certificate {0} {1}'
                        .format('node2', f2.name))
        self.assertEqual(env.profile.cluster[0]['cert'], f.name)
        self.assertEqual(env.profile.cluster[1]['cert'], f2.name)


class PassClusterClientTest(unittest.TestCase):
    def test_pass_cluster_client_not_initialized(self):
        @pass_cluster_client()
        def _f(client):
            pass

        mock_client = mock.Mock()
        mock_client.cluster.status.return_value = \
            ClusterState({'initialized': False})
        with mock.patch('cloudify_cli.env.get_rest_client',
                        return_value=mock_client):
            with self.assertRaises(CloudifyCliError) as cm:
                _f()
        mock_client.cluster.status.assert_any_call()
        self.assertIn('not part of a Cloudify Manager cluster',
                      str(cm.exception))

    def test_pass_cluster_client_initialized(self):
        @pass_cluster_client()
        def _f(client):
            pass

        mock_client = mock.Mock()
        mock_client.cluster.status.return_value = \
            ClusterState({'initialized': True})
        with mock.patch('cloudify_cli.env.get_rest_client',
                        return_value=mock_client):
            _f()
        mock_client.cluster.status.assert_any_call()
