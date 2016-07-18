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
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

from functools import wraps

from mock import call, patch, MagicMock

from cloudify_rest_client.maintenance import Maintenance

from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class MaintenanceModeTest(CliCommandTest):

    def setUp(self):
        super(MaintenanceModeTest, self).setUp()
        self.create_cosmo_wd_settings()
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
                err_str_segment='Maintenance mode timed out while waiting')

    def test_activate_maintenance_timeout_no_wait(self):
        self.invoke('cfy maintenance-mode activate --timeout 5',
                       "'--timeout' was used without '--wait'.",
                       # TODO: put back
                       # possible_solutions=["Add the '--wait' flag to "
                       #                     "the command in order to wait."]
                       )

    def test_deactivate_maintenance(self):
        self.invoke('cfy maintenance-mode deactivate')


def counter(func):
    @wraps(func)
    def tmp(*_):
        tmp.count += 1
        return func()
    tmp.count = 0
    return tmp


@counter
def mock_activated_status():
    if mock_activated_status.count % 2 == 1:
        return Maintenance({'status': 'deactivated'})
    return Maintenance({'status': 'activated'})


def mock_is_timeout(*_):
    return True
