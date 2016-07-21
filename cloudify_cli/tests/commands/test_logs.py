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

from ... import utils

from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class LogsTest(CliCommandTest):

    def test_with_empty_config(self):
        settings = utils.CloudifyWorkingDirectorySettings()
        self.create_cosmo_wd_settings(settings)
        self.invoke('cfy logs download',
                    'Management User is not set '
                    'in working directory settings')

    def test_with_no_key(self):
        settings = utils.CloudifyWorkingDirectorySettings()
        settings.set_management_user('test')
        settings.set_management_server('127.0.0.1')
        self.create_cosmo_wd_settings(settings)
        self.invoke('cfy logs download',
                    'Management Key is not set '
                    'in working directory settings')

    def test_with_no_user(self):
        settings = utils.CloudifyWorkingDirectorySettings()
        settings.set_management_server('127.0.0.1')
        settings.set_management_key('/tmp/test.pem')
        self.create_cosmo_wd_settings(settings)
        self.invoke('cfy logs download',
                    'Management User is not set '
                    'in working directory settings')

    def test_with_no_server(self):
        settings = utils.CloudifyWorkingDirectorySettings()
        settings.set_management_user('test')
        settings.set_management_key('/tmp/test.pem')
        self.create_cosmo_wd_settings(settings)
        self.invoke(
            'cfy logs download',
            err_str_segment='You must being using a manager to perform this')

    def test_purge_no_force(self):
        # unlike the other tests, this drops on argparse raising
        # that the `-f` flag is required for purge, which is why
        # the exception message is actually the returncode from argparse.
        self.invoke('cfy logs purge', 'You must supply the `-f, --force`')
