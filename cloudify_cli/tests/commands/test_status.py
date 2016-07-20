########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

from mock import patch
from mock import MagicMock

from cloudify_rest_client.exceptions import UserUnauthorizedError

from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class StatusTest(CliCommandTest):

    def setUp(self):
        super(StatusTest, self).setUp()
        self.client.manager.get_status = MagicMock()
        self.client.maintenance_mode.status = MagicMock()

    def test_status_command(self):
        self.create_cosmo_wd_settings()
        self.invoke('cfy status')

    def test_status_no_management_server_defined(self):
        # Running a command which requires a target management server without
        # first calling "cfy use" or providing a target server explicitly
        self.invoke('cfy status', 'Cloudify environment is not initalized')

    def test_status_by_unauthorized_user(self):
        with patch('cloudify_cli.utils.get_management_server_ip'):
            with patch.object(self.client.manager, 'get_status') as mock:
                mock.side_effect = UserUnauthorizedError('Unauthorized user')
                outcome = self.invoke('cfy status')
                self.assertIn('User is unauthorized', outcome.logs)
