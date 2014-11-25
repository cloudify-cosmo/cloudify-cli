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
import os
import shutil

from cloudify_cli.constants import CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME
from cloudify_cli.constants import CLOUDIFY_WD_SETTINGS_FILE_NAME
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest
from cloudify_cli import utils


class InitTest(CliCommandTest):

    def test_init_explicit_provider_name(self):
        cli_runner.run_cli('cfy init -p mock_provider')
        self.assertEquals(
            'mock_provider',
            self._read_cosmo_wd_settings().get_provider())

    def test_init_implicit_provider_name(self):
        # the actual provider name
        # is 'cloudify_mock_provider_with_cloudify_prefix'
        cli_runner.run_cli('cfy init -p mock_provider_with_cloudify_prefix -v')
        self.assertEquals(
            'cloudify_mock_provider_with_cloudify_prefix',
            self._read_cosmo_wd_settings().get_provider())

    def test_init_nonexistent_provider(self):
        self._assert_ex('cfy init -p mock_provider3',
                        'Could not import module mock_provider3')

    def test_init_initialized_directory(self):
        self._create_cosmo_wd_settings()
        self._assert_ex('cfy init -p mock_provider',
                        'Current directory is already initialized')

    def test_init_existing_provider_config_no_overwrite(self):
        cli_runner.run_cli('cfy init -p mock_provider -v')
        os.remove(os.path.join(utils.get_cwd(),
                               CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME,
                               CLOUDIFY_WD_SETTINGS_FILE_NAME))
        self._assert_ex(
            'cfy init -p mock_provider',
            'already contains a provider configuration file')

    def test_init_overwrite_existing_provider_config(self):
        cli_runner.run_cli('cfy init -p mock_provider')
        shutil.rmtree(os.path.join(utils.get_cwd(),
                                   CLOUDIFY_WD_SETTINGS_DIRECTORY_NAME))
        cli_runner.run_cli('cfy init -p mock_provider -r')

    def test_init_overwrite_existing_provider_config_with_cloudify_file(self):
        # ensuring the init with overwrite command also works when the
        # directory already contains a ".cloudify" file
        cli_runner.run_cli('cfy init -p mock_provider')
        cli_runner.run_cli('cfy init -p mock_provider -r')

    def test_init_overwrite_on_initial_init(self):
        # simply verifying the overwrite flag doesn't break the first init
        cli_runner.run_cli('cfy init -p mock_provider -r')

    def test_no_init(self):
        self._assert_ex('cfy bootstrap',
                        'Not initialized',
                        possible_solutions=[
                            "Run 'cfy init' in this directory"
                        ])
