import os
import shutil
import tempfile
from collections import namedtuple

from mock import MagicMock

from ..constants import SNAPSHOTS_DIR, BLUEPRINTS_DIR, \
    DEFAULT_BLUEPRINT_FILE_NAME
from ..mocks import node_instance_get_mock, node_get_mock, make_tarfile
from ..test_base import CliCommandTest
from cloudify_rest_client import plugins, snapshots, executions


class ListSortTest(CliCommandTest):
    _resource = namedtuple('Resource', 'name,class_type,sort_order,context')

    def setUp(self):
        super(ListSortTest, self).setUp()
        self.use_manager()
        self.resources = [
            ListSortTest._resource(
                'plugins',
                self.client.plugins,
                'uploaded_at',
                None
            ),
            ListSortTest._resource(
                'deployments',
                self.client.deployments,
                'created_at',
                None
            ),
            ListSortTest._resource(
                'nodes',
                self.client.nodes,
                'deployment_id',
                None
            ),
            ListSortTest._resource(
                'node-instances',
                self.client.node_instances,
                'node_id',
                'manager'
            ),
            ListSortTest._resource(
                'blueprints',
                self.client.blueprints,
                'created_at',
                None
            ),
            ListSortTest._resource(
                'snapshots',
                self.client.snapshots,
                'created_at',
                None
            ),
            ListSortTest._resource(
                'executions',
                self.client.executions,
                'created_at',
                None
            ),
        ]

        self.count_mock_calls = 0

        self.original_lists = {}
        for r in self.resources:
            self.original_lists[r.name] = r.class_type.list

    def tearDown(self):
        for r in self.resources:
            r.class_type.list= self.original_lists[r.name]
        super(ListSortTest, self).tearDown()

    def test_list_sort(self):
        for r in self.resources:
            self._set_mock_list(r, 'order')
            self.invoke(
                'cfy {0} list --sort-by order'
                .format(r.name), context=r.context
            )
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def test_list_sort_reverse(self):
        for r in self.resources:
            self._set_mock_list(r, 'order', descending=True)
            self.invoke(
                'cfy {0} list --sort-by order --descending'
                .format(r.name), context=r.context
            )
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def test_list_sort_default(self):
        for r in self.resources:
            self._set_mock_list(r, r.sort_order)
            self.invoke('cfy {0} list'.format(r.name), context=r.context)
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def test_list_sort_default_reverse(self):
        for r in self.resources:
            self._set_mock_list(r, r.sort_order, descending=True)
            self.invoke('cfy {0} list --descending'
                        .format(r.name), context=r.context)
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def _set_mock_list(self, resource, sort, descending=False):
        def _mock_list(*_, **kwargs):
            self.count_mock_calls += 1
            self.assertEqual(sort, kwargs['sort'])
            self.assertEqual(descending, kwargs['is_descending'])
            return []

        resource.class_type.list = _mock_list


class LogsTest(CliCommandTest):
    def test_with_empty_config(self):
        self.use_manager(user=None, port=None, key=None)
        self.invoke('cfy logs download',
                    'Manager User is not set '
                    'in working directory settings')

    def test_with_no_key(self):
        self.use_manager(user='test', port='22', host='127.0.0.1', key=None)
        self.invoke('cfy logs download',
                    'Manager Key is not set '
                    'in working directory settings')

    def test_with_no_user(self):
        self.use_manager(port='22', key='/tmp/test.pem', user=None)
        self.invoke('cfy logs download',
                    'Manager User is not set '
                    'in working directory settings')

    def test_with_no_port(self):
        self.use_manager(user='test', key='/tmp/test.pem', host='127.0.0.1', port=None)
        self.invoke('cfy logs download',
                    'Manager Port is not set '
                    'in working directory settings')

    def test_with_no_server(self):
        self.use_manager(user='test', key='/tmp/test.pem', host=None)
        self.invoke(
            'cfy logs download',
            err_str_segment='command is only available when using a manager')

    def test_purge_no_force(self):
        self.use_manager()
        # unlike the other tests, this drops on argparse raising
        # that the `-f` flag is required for purge, which is why
        # the exception message is actually the returncode from argparse.
        self.invoke('cfy logs purge', 'You must supply the `-f, --force`')


class InstancesTest(CliCommandTest):

    def setUp(self):
        super(InstancesTest, self).setUp()
        self.use_manager()

    def test_instances_get(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        self.invoke('cfy node-instances get instance_id', context='manager')

    def test_instance_get_no_instance_id(self):
        self.invoke(
            'cfy node-instances get', should_fail=True, context='manager')

    def test_instances_list(self):
        self.client.node_instances.list = MagicMock(
            return_value=[node_instance_get_mock(), node_instance_get_mock()])
        self.invoke('cfy node-instances list', context='manager')
        self.invoke('cfy node-instances list -d nodecellar', context='manager')

    def test_local_instances(self):
        self._create_local_env()
        output = self.invoke('cfy node-instances', context='local')
        self._assert_outputs(output, {'node_id': 'node'})

    def test_local_instances_with_existing_node_id(self):
        self._create_local_env()
        output = self.invoke('cfy node-instances node', context='local')
        self._assert_outputs(output, {'node_id': 'node'})

    def test_local_instances_with_non_existing_node_id(self):
        self._create_local_env()
        self.invoke(
            'cfy node-instances noop', context='local',
            err_str_segment='Could not find node noop'
        )

    def _create_local_env(self):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )

        self.invoke('cfy init {0}'.format(blueprint_path))
        self.register_commands()
        self.invoke('cfy executions start {0}'.format('run_test_op_on_nodes'))

    def _assert_outputs(self, output, expected_outputs):
        output = output.logs.split('\n')
        for key, value in expected_outputs.iteritems():
            if value == 'null':
                key_val_string = '    "{0}": {1}, '.format(key, value)
            else:
                key_val_string = '    "{0}": "{1}", '.format(key, value)
            self.assertIn(key_val_string, output)


class NodesTest(CliCommandTest):

    def setUp(self):
        super(NodesTest, self).setUp()
        self.use_manager()

    def test_nodes_get(self):
        self.client.nodes.get = MagicMock(return_value=node_get_mock())
        self.client.node_instances.list = MagicMock(
            return_value=[node_instance_get_mock()])
        self.invoke('cfy nodes get mongod -d nodecellar')

    def test_node_get_no_node_id(self):
        self.invoke('cfy nodes get -d nodecellar', should_fail=True)

    def test_node_get_no_deployment_id(self):
        self.invoke('cfy nodes get --node-id mongod', should_fail=True)

    def test_nodes_list(self):
        self.client.nodes.list = MagicMock(
            return_value=[node_get_mock(), node_get_mock()])
        self.invoke('cfy nodes list')
        self.invoke('cfy nodes list -d nodecellar')


class PluginsTest(CliCommandTest):

    def setUp(self):
        super(PluginsTest, self).setUp()
        self.use_manager()

    def test_plugins_list(self):
        self.client.plugins.list = MagicMock(return_value=[])
        self.invoke('cfy plugins list')

    def test_plugin_get(self):
        self.client.plugins.get = MagicMock(
            return_value=plugins.Plugin({'id': 'id',
                                         'package_name': 'dummy',
                                         'package_version': '1.2',
                                         'supported_platform': 'any',
                                         'distribution_release': 'trusty',
                                         'distribution': 'ubuntu',
                                         'uploaded_at': 'now'}))

        self.invoke('cfy plugins get some_id')

    def test_plugins_delete(self):
        self.client.plugins.delete = MagicMock()
        self.invoke('cfy plugins delete a-plugin-id')

    def test_plugins_delete_force(self):
        for flag in ['--force', '-f']:
            mock = MagicMock()
            self.client.plugins.delete = mock
            self.invoke('cfy plugins delete a-plugin-id {0}'.format(
                flag))
            mock.assert_called_once_with(plugin_id='a-plugin-id', force=True)

    def test_plugins_upload(self):
        self.client.plugins.upload = MagicMock()
        plugin_dest = os.path.join(tempfile.gettempdir(), 'plugin.tar.gz')
        try:
            self.make_sample_plugin(plugin_dest)
            self.invoke('cfy plugins upload {0}'.format(plugin_dest))
        finally:
            shutil.rmtree(plugin_dest, ignore_errors=True)

    def test_plugins_download(self):
        self.client.plugins.download = MagicMock(return_value='some_file')
        self.invoke('cfy plugins download a-plugin-id')

    def make_sample_plugin(self, plugin_dest):
        temp_folder = tempfile.mkdtemp()
        with open(os.path.join(temp_folder, 'package.json'), 'w') as f:
            f.write('{}')
        make_tarfile(plugin_dest, temp_folder)


class SnapshotsTest(CliCommandTest):

    def setUp(self):
        super(SnapshotsTest, self).setUp()
        self.use_manager()

    def test_snapshots_list(self):
        self.client.snapshots.list = MagicMock(return_value=[])
        self.invoke('cfy snapshots list')

    def test_snapshots_delete(self):
        self.client.snapshots.delete = MagicMock()
        self.invoke('cfy snapshots delete a-snapshot-id')

    def test_snapshots_upload(self):
        self.client.snapshots.upload = MagicMock(
            return_value=snapshots.Snapshot({'id': 'some_id'}))
        self.invoke('cfy snapshots upload {0}/snapshot.zip '
                    '-s my_snapshot_id'.format(SNAPSHOTS_DIR))

    def test_snapshots_create(self):
        self.client.snapshots.create = MagicMock(
            return_value=executions.Execution({'id': 'some_id'}))
        self.invoke('cfy snapshots create a-snapshot-id')

    def test_snapshots_restore(self):
        self.client.snapshots.restore = MagicMock()
        self.invoke('cfy snapshots restore a-snapshot-id')
        self.invoke('cfy snapshots restore a-snapshot-id'
                    '--without-deployments-envs')

    def test_snapshots_download(self):
        self.client.snapshots.download = MagicMock(return_value='some_file')
        self.invoke('cfy snapshots download a-snapshot-id')
