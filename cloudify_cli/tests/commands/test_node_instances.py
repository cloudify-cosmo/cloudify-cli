import os
import json
import tempfile

from mock import MagicMock

from .. import cfy
from .test_base import CliCommandTest
from cloudify_cli.exceptions import CloudifyCliError
from .mocks import node_instance_get_mock, MockListResponse
from .constants import BLUEPRINTS_DIR, DEFAULT_BLUEPRINT_FILE_NAME


class NodeInstancesTest(CliCommandTest):

    def setUp(self):
        super(NodeInstancesTest, self).setUp()
        self.use_manager()

    def test_instances_get(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        self.invoke('node-instances get instance_id', context='node_instances')

    def test_instances_get_json(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        # this needs to be --quiet because click's testing framework doesn't
        # expose stdout/stderr separately, just mushed together. To be fixed
        # in click 6.8/7.0
        result = self.invoke('node-instances get instance_id --json --quiet',
                             context='node_instances')
        data = json.loads(result.output)
        self.assertIn('runtime_properties', data)

    def test_instance_get_no_instance_id(self):
        outcome = self.invoke(
            'cfy node-instances get',
            err_str_segment='2',  # Exit code
            exception=SystemExit,
            context='node_instances'
        )

        self.assertIn('Missing argument "node_instance_id"', outcome.output)

    def test_instances_list(self):
        self.client.node_instances.list = MagicMock(
            return_value=MockListResponse(items=[node_instance_get_mock(),
                                                 node_instance_get_mock()])
        )
        self.invoke('cfy node-instances list', context='node_instances')
        self.invoke('cfy node-instances list -d nodecellar',
                    context='node_instances')
        self.invoke('cfy node-instances list -t dummy_t',
                    context='node_instances')
        self.invoke('cfy node-instances list -a', context='node_instances')

    def test_local_instances(self):
        self._create_local_env()
        output = self.invoke('cfy node-instances -b local', context='local')
        self._assert_outputs(output, {'node_id': 'node'})

    def test_local_instances_with_existing_node_id(self):
        self._create_local_env()
        output = self.invoke(
            'cfy node-instances -b local node', context='local')
        self._assert_outputs(output, {'node_id': 'node'})

    def test_local_instances_with_non_existing_node_id(self):
        self._create_local_env()
        self.invoke(
            'cfy node-instances -b local noop', context='local',
            err_str_segment='Could not find node noop'
        )

    def test_update_runtime_missing_args(self):
        self._common_runtime_missing_args('update-runtime')

    def test_update_runtime_invalid_key_value(self):
        self.invoke('cfy node-instances update-runtime instance_id -p abc',
                    err_str_segment='It must represent a dictionary',
                    exception=CloudifyCliError)

    def test_update_runtime_invalid_dict(self):
        self._common_runtime_invalid_dict('update-runtime')

    def test_update_runtime_successful(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        self.client.node_instances.update = MagicMock(return_value={})

        self.invoke('cfy node-instances update-runtime instance_id -p abc=2')
        call_args = self.client.node_instances.update.call_args
        self.assertEqual('2', call_args[1]['runtime_properties']['abc'])
        self.assertEqual(2, call_args[1]['version'])

        self.invoke('cfy node-instances update-runtime instance_id -p x.y=z')
        self.assertEqual('z', call_args[1]['runtime_properties']['x']['y'])

    def test_update_runtime_successful_key_exists(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        self.client.node_instances.update = MagicMock(return_value={})

        self.invoke('cfy node-instances update-runtime instance_id -p x.y=z')
        self.invoke('cfy node-instances update-runtime instance_id -p "{0}"'
                    .format({'x': {'z': 5}}))
        self.invoke('cfy node-instances update-runtime instance_id -p "{0}"'
                    .format({'floating_ip': '0.0.0.0', 'x': {'y': 'w'}}))
        call_args = self.client.node_instances.update.call_args
        self.assertEqual('w', call_args[1]['runtime_properties']['x']['y'])
        self.assertEqual(5, call_args[1]['runtime_properties']['x']['z'])

    def test_update_runtime_successful_dict_in_place_of_literal(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        self.client.node_instances.update = MagicMock(return_value={})

        self.invoke('cfy node-instances update-runtime instance_id -p abc=2')
        call_args = self.client.node_instances.update.call_args
        self.assertEqual('2', call_args[1]['runtime_properties']['abc'])
        self.invoke('cfy node-instances update-runtime instance_id -p abc.d=2')
        self.assertEqual({'d': '2'}, call_args[1]['runtime_properties']['abc'])

    def test_update_runtime_successful_literal_in_place_of_dict(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        self.client.node_instances.update = MagicMock(return_value={})

        self.invoke('cfy node-instances update-runtime instance_id -p a.b=c')
        call_args = self.client.node_instances.update.call_args
        self.assertEqual({'b': 'c'}, call_args[1]['runtime_properties']['a'])
        self.invoke('cfy node-instances update-runtime instance_id -p a=3')
        self.assertEqual('3', call_args[1]['runtime_properties']['a'])

    def test_update_runtime_from_yaml(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        self.client.node_instances.update = MagicMock(return_value={})

        yaml_path = tempfile.mktemp(suffix='.yaml')
        with open(yaml_path, 'wb') as f:
            f.write("""
                    x1:
                        y: 1
                    x2:
                        y:
                            z: 2
                    """)
        self.invoke('cfy node-instances update-runtime instance_id -p {0}'
                    .format(yaml_path))
        call_args = self.client.node_instances.update.call_args
        self.assertEqual(1, call_args[1]['runtime_properties']['x1']['y'])
        self.assertEqual(2, call_args[1]['runtime_properties']['x2']['y']['z'])

    def test_update_runtime_invalid_yaml_format(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        self.client.node_instances.update = MagicMock(return_value={})

        yaml_path = tempfile.mktemp(suffix='.yaml')
        with open(yaml_path, 'wb') as f:
            f.write("""
                    x1:
                        y: 1
                      x2:
                        y: 2
                    """)
        self.invoke('cfy node-instances update-runtime instance_id -p {0}'
                    .format(yaml_path),
                    err_str_segment='is not a valid YAML',
                    exception=CloudifyCliError)
        with open(yaml_path, 'wb') as f:
            f.write("""
                    - x1
                    - x2
                    """)
        self.invoke('cfy node-instances update-runtime instance_id -p {0}'
                    .format(yaml_path),
                    err_str_segment='Resource is valid YAML, '
                                    'but does not represent a dictionary',
                    exception=CloudifyCliError)

    def test_delete_runtime_missing_args(self):
        self._common_runtime_missing_args('delete-runtime')

    def test_delete_runtime_invalid_dict(self):
        self._common_runtime_invalid_dict('delete-runtime')

    def test_update_runtime_invalid_yaml_path(self):
        self._common_runtime_invalid_yaml_path('delete-runtime')

    def test_delete_runtime_invalid_yaml_path(self):
        self._common_runtime_invalid_yaml_path('update-runtime')

    def test_delete_runtime_no_such_property(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        self.invoke('cfy node-instances delete-runtime instance_id -p "abc"',
                    err_str_segment='Key abc does not exist',
                    exception=CloudifyCliError)
        self.invoke('cfy node-instances delete-runtime instance_id -p {abc}',
                    err_str_segment='Key abc does not exist',
                    exception=CloudifyCliError)
        self.invoke('cfy node-instances delete-runtime instance_id -p "a.b"',
                    err_str_segment="argument of type 'NoneType' "
                                    "is not iterable",
                    exception=TypeError)

    def test_delete_runtime_using_dict(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        self.client.node_instances.update = MagicMock(return_value={})
        self.invoke('cfy node-instances update-runtime instance_id -p '
                    '"x.y.z=1" -p "x.w=2"')
        self.invoke('cfy node-instances delete-runtime instance_id -p '
                    '{x:{y:}}')
        call_args = self.client.node_instances.update.call_args
        self.assertEqual({'w': '2'}, call_args[1]['runtime_properties']['x'])

    def test_delete_runtime_using_dot_syntax(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        self.client.node_instances.update = MagicMock(return_value={})
        self.invoke('cfy node-instances update-runtime instance_id -p '
                    '"x.y.z=1; x.w=2"')
        self.invoke('cfy node-instances delete-runtime instance_id -p '
                    '"x.y.z; x.w"')
        call_args = self.client.node_instances.update.call_args
        self.assertEqual({'y': {}}, call_args[1]['runtime_properties']['x'])

    def test_delete_runtime_from_yaml(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        self.client.node_instances.update = MagicMock(return_value={})

        yaml_path = tempfile.mktemp(suffix='.yaml')
        with open(yaml_path, 'wb') as f:
            f.write("""
                    x:
                        y:
                            z: 2
                        w: 3
                    """)
        self.invoke('cfy node-instances update-runtime instance_id -p {0}'
                    .format(yaml_path))
        call_args = self.client.node_instances.update.call_args
        with open(yaml_path, 'wb') as f:
            f.write("""
                    x:
                        y:
                            z:
                    """)
        self.invoke('cfy node-instances delete-runtime instance_id -p {0}'
                    .format(yaml_path))
        self.assertEqual({}, call_args[1]['runtime_properties']['x']['y'])
        self.assertEqual(3, call_args[1]['runtime_properties']['x']['w'])

    def _common_runtime_missing_args(self, command):
        outcome = self.invoke('cfy node-instances {0}'.format(command),
                              err_str_segment='2',
                              exception=SystemExit)
        self.assertIn('Missing argument "node_instance_id"', outcome.output)
        outcome = self.invoke('cfy node-instances {0} instance_id'
                              .format(command),
                              err_str_segment='2',
                              exception=SystemExit)
        self.assertIn('Missing option "-p"', outcome.output)
        outcome = self.invoke('cfy node-instances {0} instance_id -p'
                              .format(command),
                              err_str_segment='2',
                              exception=SystemExit)
        self.assertIn('-p option requires an argument', outcome.output)

    def _common_runtime_invalid_dict(self, command):
        self.invoke('cfy node-instances {0} instance_id -p "{1}"'
                    .format(command, '{a: {b: c}'),  # unbalanced brackets
                    err_str_segment='It must represent a dictionary',
                    exception=CloudifyCliError)

    def _common_runtime_invalid_yaml_path(self, command):
        self.invoke('cfy node-instances {0} instance_id -p {1}'
                    .format(command, 'no_such.yaml'),
                    err_str_segment='It must represent a dictionary',
                    exception=CloudifyCliError)
        self.invoke('cfy node-instances {0} instance_id -p {1}'
                    .format(command, 'nosuch_folder/'),
                    err_str_segment='It must represent a dictionary',
                    exception=CloudifyCliError)

    def _create_local_env(self):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )

        self.invoke('cfy init {0}'.format(blueprint_path))
        cfy.register_commands()
        self.invoke(
            'cfy executions start -b local {0}'
            .format('run_test_op_on_nodes')
        )

    def _assert_outputs(self, output, expected_outputs):
        output = output.logs.split('\n')
        for key, value in expected_outputs.iteritems():
            if value == 'null':
                key_val_string = '    "{0}": {1}, '.format(key, value)
            else:
                key_val_string = '    "{0}": "{1}", '.format(key, value)
            self.assertIn(key_val_string, output)
