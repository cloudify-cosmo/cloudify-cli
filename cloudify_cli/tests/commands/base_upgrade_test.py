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


class BaseUpgradeTest(CliCommandTest):

    def _test_not_in_maintenance(self, action):
        self.client.maintenance_mode.status = MagicMock(
            return_value=Maintenance({'status': 'deactivated'}))
        self.invoke('cfy {0} path -i private_ip=localhost'.format(action),
                    'To perform an upgrade of a manager to a newer '
                    'version, the manager must be in maintenance mode')

    def _test_no_bp(self, action):
        self.client.maintenance_mode.status = MagicMock(
            return_value=Maintenance({'status': 'active'}))
        self.invoke('cfy {0} path -i private_ip=localhost '
                    '-i ssh_key_filename=key_path -i ssh_port=22'
                    .format(action),
                    "No such file or directory: u'path'",
                    exception=IOError)

    def _test_no_private_ip(self, action):
        self.client.maintenance_mode.status = MagicMock(
            return_value=Maintenance({'status': 'active'}))
        self.invoke('cfy {0} path'.format(action),
                    'Private IP must be provided for the '
                    'upgrade/rollback process')

    def _test_no_inputs(self, action):
        self.client.maintenance_mode.status = MagicMock(
            return_value=Maintenance({'status': 'active'}))
        self.invoke('cfy {0} path --inputs inputs'.format(action),
                    'Invalid input: inputs')
