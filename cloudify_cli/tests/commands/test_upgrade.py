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
from mock import MagicMock

from cloudify_rest_client.maintenance import Maintenance

from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class ManagerUpgradeTest(CliCommandTest):

    def setUp(self):
        super(ManagerUpgradeTest, self).setUp()
        self._create_cosmo_wd_settings()

    def test_not_in_maintenance(self):
        self.client.maintenance_mode.status = MagicMock(
                return_value=Maintenance({'status': 'deactivated'}))
        self._assert_ex('cfy upgrade --blueprint-path path '
                        '--inputs private_ip=localhost',
                        'Manager must be in maintenance mode for '
                        'upgrade to run.')

    def test_upgrade_no_bp(self):
        self.client.maintenance_mode.status = MagicMock(
                return_value=Maintenance({'status': 'active'}))
        self._assert_ex('cfy upgrade --blueprint-path path '
                        '--inputs private_ip=localhost',
                        'No such file or directory: \'path\'')

    def test_upgrade_no_private_ip(self):
        self.client.maintenance_mode.status = MagicMock(
                return_value=Maintenance({'status': 'active'}))
        self._assert_ex('cfy upgrade --blueprint-path path',
                        'Private IP must be provided for the upgrade process')

    def test_upgrade_no_inputs(self):
        self.client.maintenance_mode.status = MagicMock(
                return_value=Maintenance({'status': 'active'}))
        self._assert_ex('cfy upgrade '
                        '--blueprint-path path '
                        '--inputs inputs',
                        'Invalid input: inputs')
