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
Tests 'cfy init'
"""
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class InitTest(CliCommandTest):

    def test_init_initialized_directory(self):
        self._create_cosmo_wd_settings()
        self._assert_ex('cfy init',
                        'Current directory is already initialized')

    def test_init_overwrite(self):
        # ensuring the init with overwrite command also works when the
        # directory already contains a ".cloudify" file
        cli_runner.run_cli('cfy init')
        cli_runner.run_cli('cfy init -r')

    def test_init_overwrite_on_initial_init(self):
        # simply verifying the overwrite flag doesn't break the first init
        cli_runner.run_cli('cfy init -r')

    def test_no_init(self):
        self._assert_ex('cfy bootstrap',
                        'Not initialized',
                        possible_solutions=[
                            "Run 'cfy init' in this directory"
                        ])
