from mock import MagicMock, patch, call

from ..test_base import CliCommandTest
from ..mocks import mock_activated_status, mock_is_timeout


class MaintenanceModeTest(CliCommandTest):

    def setUp(self):
        super(MaintenanceModeTest, self).setUp()
        self.use_manager()
        self.client.maintenance_mode.deactivate = MagicMock()
        self.client.maintenance_mode.activate = MagicMock()

    def test_maintenance_status(self):
        self.client.maintenance_mode.status = MagicMock()
        self.invoke('cfy maintenance-mode status')

    def test_activate_maintenance(self):
        self.invoke('cfy maintenance-mode activate')

    def test_activate_maintenance_with_wait(self):
        with patch('cloudify_rest_client.maintenance.'
                   'MaintenanceModeClient.status',
                   new=mock_activated_status):
            with patch('time.sleep') as sleep_mock:
                self.invoke('cfy maintenance-mode activate --wait')
                self.invoke('cfy maintenance-mode '
                               'activate --wait --timeout 20')
                sleep_mock.assert_has_calls([call(5), call(5)])

    def test_activate_maintenance_timeout(self):
        with patch('cloudify_cli.commands.maintenance_mode._is_timeout',
                   new=mock_is_timeout):
            self.invoke(
                'cfy maintenance-mode activate --wait',
                err_str_segment='Timed out while entering maintenance mode')

    def test_activate_maintenance_timeout_no_wait(self):
        self.invoke('cfy maintenance-mode activate --timeout 5',
                       "'--timeout' was used without '--wait'.",
                       # TODO: put back
                       # possible_solutions=["Add the '--wait' flag to "
                       #                     "the command in order to wait."]
                       )

    def test_deactivate_maintenance(self):
        self.invoke('cfy maintenance-mode deactivate')