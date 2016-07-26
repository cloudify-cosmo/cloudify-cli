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

import os
import platform
from distutils import spawn

from ...commands.ssh import _validate_env
from ...exceptions import CloudifyCliError
from .test_cli_command import CliCommandTest


class SshTest(CliCommandTest):

    def test_ssh_no_manager(self):
        self.invoke(
            'cfy ssh',
            'This command is only available when using a manager'
        )

    def test_ssh_with_empty_config(self):
        self.use_manager(user=None)
        self.invoke('cfy ssh',
                    'Management User is not set '
                    'in working directory settings')

    def test_ssh_with_no_key(self):
        self.use_manager(user='test', host='127.0.0.1', key=None)
        self.invoke('cfy ssh',
                    'Management Key is not set '
                    'in working directory settings')

    def test_ssh_with_no_user(self):
        self.use_manager(key='/tmp/test.pem', host='127.0.0.1', user=None)
        self.invoke('cfy ssh',
                    'Management User is not set '
                    'in working directory settings')

    def test_ssh_with_no_server(self):
        self.use_manager(key='/tmp/test.pem', user='test', host=None)
        self.invoke(
            'cfy ssh',
            'This command is only available when using a manager'
        )

    def test_ssh_without_ssh_windows(self):
        platform.system = lambda: 'Windows'
        if os.name != 'nt':
            self.skipTest('Irrelevant on Linux')
        self.use_manager(key='/tmp/test.pem', user='test', host='127.0.0.1')
        spawn.find_executable = lambda x: None
        self.invoke('cfy ssh', 'ssh.exe not found')

    def test_ssh_without_ssh_linux(self):
        platform.system = lambda: 'Linux'
        if os.name == 'nt':
            self.skipTest('Irrelevant on Windows')
        self.use_manager(key='/tmp/test.pem', user='test', host='127.0.0.1')
        spawn.find_executable = lambda x: None
        self.invoke('cfy ssh', 'ssh not found')

    def test_host_list_conflicts(self):
        self.assertRaises(
            CloudifyCliError,
            _validate_env,
            command='',
            host=True,
            sid='',
            list_sessions=True
        )
