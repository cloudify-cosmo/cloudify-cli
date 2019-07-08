from mock import MagicMock

from cloudify_cli.logger import get_global_json_output

from .mocks import MockListResponse
from .test_base import CliCommandTest


class OptionsTest(CliCommandTest):
    def setUp(self):
        super(OptionsTest, self).setUp()
        self.use_manager()
        self.client.agents.list = MagicMock(return_value=MockListResponse())

    def test_json_command_sets(self):
        self.client.blueprints.list = MagicMock(
            return_value=MockListResponse()
        )
        self.invoke('cfy blueprints list --json ')
        self.assertTrue(get_global_json_output())

    def test_format_command_sets(self):
        self.client.blueprints.list = MagicMock(
            return_value=MockListResponse()
        )
        self.invoke('cfy blueprints list --format json')
        self.assertTrue(get_global_json_output())

    def test_agent_filters_all_tenants(self):
        self.invoke('agents list --node-id a --all-tenants')
        self.client.agents.list.assert_called_with(
            deployment_id=[],
            install_methods=[],
            node_ids=['a'],
            node_instance_ids=[],
            _all_tenants=True)

    def test_agent_filters_multiple(self):
        self.invoke('agents list --node-id a --node-id b')
        self.client.agents.list.assert_called_with(
            deployment_id=[],
            install_methods=[],
            node_ids=['a', 'b'],
            node_instance_ids=[],
            _all_tenants=False)

    def test_agent_filters_commaseparated(self):
        self.invoke('agents list --node-id a,b')
        self.client.agents.list.assert_called_with(
            deployment_id=[],
            install_methods=[],
            node_ids=['a', 'b'],
            node_instance_ids=[],
            _all_tenants=False)

    def test_agent_filters_commaseparated_multiple(self):
        self.invoke('agents list --node-id a,b --node-id c')
        self.client.agents.list.assert_called_with(
            deployment_id=[],
            install_methods=[],
            node_ids=['a', 'b', 'c'],
            node_instance_ids=[],
            _all_tenants=False)
