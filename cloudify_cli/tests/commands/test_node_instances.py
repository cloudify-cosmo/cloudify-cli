import os

from mock import MagicMock

from .. import cfy
from .test_base import CliCommandTest
from .constants import BLUEPRINTS_DIR, DEFAULT_BLUEPRINT_FILE_NAME
from .mocks import node_instance_get_mock


class NodeInstancesTest(CliCommandTest):

    def setUp(self):
        super(NodeInstancesTest, self).setUp()
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
        cfy.register_commands()
        self.invoke('cfy executions start {0}'.format('run_test_op_on_nodes'))

    def _assert_outputs(self, output, expected_outputs):
        output = output.logs.split('\n')
        for key, value in expected_outputs.iteritems():
            if value == 'null':
                key_val_string = '    "{0}": {1}, '.format(key, value)
            else:
                key_val_string = '    "{0}": "{1}", '.format(key, value)
            self.assertIn(key_val_string, output)