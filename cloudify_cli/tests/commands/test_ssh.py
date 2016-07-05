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
Tests 'cfy ssh'
"""

import platform
import os

from distutils import spawn

from cloudify_cli.commands.ssh import _validate_env
from cloudify_cli import utils
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest
from cloudify_cli.exceptions import CloudifyCliError


class SshTest(CliCommandTest):

    def setUp(self):
        super(SshTest, self).setUp()
        self.settings = utils.CloudifyWorkingDirectorySettings()

    def test_ssh_no_prior_init(self):
        self._assert_ex('cfy ssh', 'Cannot find .cloudify')

    def test_ssh_with_empty_config(self):
        self._create_cosmo_wd_settings(self.settings)
        self._assert_ex('cfy ssh',
                        'Management User is not set '
                        'in working directory settings')

    def test_ssh_with_no_key(self):
        self.settings.set_management_user('test')
        self.settings.set_management_server('127.0.0.1')
        self.settings.set_management_port('22')
        self._create_cosmo_wd_settings(self.settings)
        self._assert_ex('cfy ssh',
                        'Management Key is not set '
                        'in working directory settings')

    def test_ssh_with_no_port(self):
        self.settings.set_management_user('test')
        self.settings.set_management_server('127.0.0.1')
        self.settings.set_management_key('/tmp/test.pem')
        self._create_cosmo_wd_settings(self.settings)
        self._assert_ex('cfy ssh',
                        'Management Port is not set '
                        'in working directory settings')

    def test_ssh_with_no_user(self):
        self.settings.set_management_server('127.0.0.1')
        self.settings.set_management_key('/tmp/test.pem')
        self._create_cosmo_wd_settings(self.settings)
        self._assert_ex('cfy ssh',
                        'Management User is not set '
                        'in working directory settings')

    def test_ssh_with_no_server(self):
        self.settings.set_management_user('test')
        self.settings.set_management_key('/tmp/test.pem')
        self._create_cosmo_wd_settings(self.settings)
        self._assert_ex('cfy ssh', 'Must either first run')

    def test_ssh_without_ssh_windows(self):
        platform.system = lambda: 'Windows'
        if os.name != 'nt':
            self.skipTest('Irrelevant on Linux')
        self.settings.set_management_user('test')
        self.settings.set_management_key('/tmp/test.pem')
        self.settings.set_management_server('127.0.0.1')
        self._create_cosmo_wd_settings(self.settings)
        spawn.find_executable = lambda x: None
        self._assert_ex('cfy ssh', 'ssh.exe not found')

    def test_ssh_without_ssh_linux(self):
        platform.system = lambda: 'Linux'
        if os.name == 'nt':
            self.skipTest('Irrelevant on Windows')
        self.settings.set_management_user('test')
        self.settings.set_management_key('/tmp/test.pem')
        self.settings.set_management_server('127.0.0.1')
        self._create_cosmo_wd_settings(self.settings)
        spawn.find_executable = lambda x: None
        self._assert_ex('cfy ssh', 'ssh not found')

    def test_ssh_bad_args(self):
        ssh_args = [
            {
                'ssh_command': {},
                'host_session': True,
                'sid': '',
                'list_sessions': '',
            },
            {
                'ssh_command': '',
                'host_session': {},
                'sid': '',
                'list_sessions': '',
            },
            {
                'ssh_command': '',
                'host_session': True,
                'sid': {},
                'list_sessions': '',
            },
            {
                'ssh_command': '',
                'host_session': True,
                'sid': '',
                'list_sessions': {},
            },
        ]

        for arg_set in ssh_args:
            self.assertRaises(
                CloudifyCliError,
                _validate_env,
                **arg_set
            )

    def test_host_list_conflicts(self):
        self.assertRaises(
            CloudifyCliError,
            _validate_env,
            ssh_command='',
            host_session=True,
            sid='',
            list_sessions=True
        )
