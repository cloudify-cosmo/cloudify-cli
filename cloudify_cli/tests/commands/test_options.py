from mock import MagicMock

from cloudify_cli.logger import get_global_json_output

from .mocks import MockListResponse
from .test_base import CliCommandTest


class OptionsTest(CliCommandTest):

    def setUp(self):
        super(OptionsTest, self).setUp()
        self.use_manager()

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
