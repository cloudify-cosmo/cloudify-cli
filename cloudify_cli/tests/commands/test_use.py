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

"""
Tests 'cfy use'
"""

from mock import MagicMock
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


def run_use_command(manager_ip, username=None, password=None, clear=False):
    command = 'cfy use -t {0}'.format(manager_ip)
    if username and password:
        command = '{0} --username {1} --password {2} --secured'\
            .format(command, username, password)
    elif clear:
        command = '{0} --clear'.format(command)
    cli_runner.run_cli(command)


class UseTest(CliCommandTest):

    def test_use_command(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={
                'name': 'name',
                'context': {}}
        )
        self._create_cosmo_wd_settings()
        run_use_command('127.0.0.1')
        cwds = self._read_cosmo_wd_settings()
        self.assertEquals("127.0.0.1",
                          cwds.get_management_server())

    def test_use_command_no_prior_init(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={
                'name': 'name', 'context': {}
            }
        )
        run_use_command('127.0.0.1')
        cwds = self._read_cosmo_wd_settings()
        self.assertEquals('127.0.0.1', cwds.get_management_server())

    def test_use_secured(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={
                'name': 'name',
                'context': {}
            }
        )
        run_use_command('127.0.0.1', 'test_username', 'test_password')
        cwds = self._read_cosmo_wd_settings()
        self.assertEquals('127.0.0.1', cwds.get_management_server())
        self.assertEquals('test_username', cwds.get_username())
        self.assertEquals('test_password', cwds.get_password())

    def test_use_clear(self):
        run_use_command('127.0.0.1', 'test_username', 'test_password')
        cwds = self._read_cosmo_wd_settings()
        self.assertEquals('test_username', cwds.get_username())
        self.assertEquals('test_password', cwds.get_password())
        run_use_command('127.0.0.1', clear=True)
        cwds = self._read_cosmo_wd_settings()
        self.assertEquals('127.0.0.1', cwds.get_management_server())
        self.assertIsNone(cwds.get_username())
        self.assertIsNone(cwds.get_password())