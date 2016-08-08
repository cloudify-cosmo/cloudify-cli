from mock import MagicMock

from .test_base import CliCommandTest
from .mocks import node_get_mock, node_instance_get_mock


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
        outcome = self.invoke(
            'cfy nodes get -d nodecellar',
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )

        self.assertIn('Missing argument "node-id"', outcome.output)

    def test_node_get_no_deployment_id(self):
        outcome = self.invoke(
            'cfy nodes get mongod',
            err_str_segment='2',  # Exit code
            exception=SystemExit,
        )

        self.assertIn(
            'Missing option "-d" / "--deployment-id"',
            outcome.output
        )

    def test_nodes_list(self):
        self.client.nodes.list = MagicMock(
            return_value=[node_get_mock(), node_get_mock()])
        self.invoke('cfy nodes list')
        self.invoke('cfy nodes list -d nodecellar')