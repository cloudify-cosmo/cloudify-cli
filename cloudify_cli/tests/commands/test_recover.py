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
Tests 'cfy recover'
"""

import os

from cloudify_cli.utils import update_wd_settings

from mock import MagicMock
from mock import patch
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest
from cloudify_cli.tests.commands.test_cli_command import TEST_WORK_DIR


class RecoverTest(CliCommandTest):

    def test_recover_no_force(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        fake_snapshot_path = os.path.join(TEST_WORK_DIR, 'sn.zip')
        open(fake_snapshot_path, 'w').close()

        self.client.deployments.list = MagicMock(return_value=[])
        cli_runner.run_cli('cfy init')
        cli_runner.run_cli('cfy use -t 10.0.0.1')
        self._assert_ex('cfy recover -s {0}'.format(fake_snapshot_path),
                        'This action requires additional confirmation.')

    @patch('cloudify_cli.bootstrap.bootstrap'
           '.read_manager_deployment_dump_if_needed')
    @patch('cloudify_cli.bootstrap.bootstrap.recover')
    def test_recover_from_same_directory_as_bootstrap(self, *_):
        cli_runner.run_cli('cfy init')

        # mock bootstrap behavior by setting the management key path
        # in the local context
        key_path = os.path.join(TEST_WORK_DIR, 'key.pem')
        open(key_path, 'w').close()

        with update_wd_settings() as wd:
            wd.set_management_key(key_path)
            wd.set_provider_context({})

        # now run recovery and make sure no exception was raised
        cli_runner.run_cli('cfy recover -f -s {0}'.format(key_path))

    @patch('cloudify_cli.bootstrap.bootstrap'
           '.read_manager_deployment_dump_if_needed')
    @patch('cloudify_cli.bootstrap.bootstrap.recover')
    def test_recover_without_snapshot_flag(self, *_):
        cli_runner.run_cli('cfy init')

        # recovery command should not fail because there
        # is no snapshot flag
        self._assert_ex('cfy recover -f',
                        'This action requires a valid snapshot path.')

    @patch('cloudify_cli.bootstrap.bootstrap'
           '.read_manager_deployment_dump_if_needed')
    @patch('cloudify_cli.bootstrap.bootstrap.recover')
    def test_recover_from_same_directory_as_bootstrap_missing_key(self, *_):
        cli_runner.run_cli('cfy init')

        # mock bootstrap behavior by setting the management key path
        # in the local context. however, don't actually create the key file
        key_path = os.path.join(TEST_WORK_DIR, 'key.pem')
        fake_snapshot_path = os.path.join(TEST_WORK_DIR, 'sn.zip')
        open(fake_snapshot_path, 'w').close()

        with update_wd_settings() as wd:
            wd.set_management_key(key_path)
            wd.set_provider_context({})

        # recovery command should not fail because the key file specified in
        # the context file does not exist
        self._assert_ex('cfy recover -f -s {0}'.format(fake_snapshot_path),
                        'Cannot perform recovery. manager key '
                        'file does not exist')

    @patch('cloudify_cli.bootstrap.bootstrap'
           '.read_manager_deployment_dump_if_needed')
    @patch('cloudify_cli.bootstrap.bootstrap.recover')
    def test_recover_missing_key_with_env(self, *_):
        cli_runner.run_cli('cfy init')

        key_path = os.path.join(TEST_WORK_DIR, 'key.pem')
        fake_snapshot_path = os.path.join(TEST_WORK_DIR, 'sn.zip')
        open(fake_snapshot_path, 'w').close()
        try:
            os.environ['CLOUDIFY_MANAGER_PRIVATE_KEY_PATH'] = key_path

            # recovery command should not fail because the key file
            # specified in the context file does not exist
            self._assert_ex('cfy recover -f -s {0}'.format(fake_snapshot_path),
                            'Cannot perform recovery. manager private '
                            'key file defined in '
                            'CLOUDIFY_MANAGER_PRIVATE_KEY_PATH '
                            'environment variable does not exist: '
                            '{0}'.format(key_path))
        finally:
            del os.environ['CLOUDIFY_MANAGER_PRIVATE_KEY_PATH']

    @patch('cloudify_cli.bootstrap.bootstrap'
           '.read_manager_deployment_dump_if_needed')
    @patch('cloudify_cli.bootstrap.bootstrap.recover')
    def test_recover_from_different_directory_than_bootstrap(self, *_):
        cli_runner.run_cli('cfy init')
        # recovery command should not fail because we do not have a manager
        # key path in the local context, and the environment variable is not
        # set
        fake_snapshot_path = os.path.join(TEST_WORK_DIR, 'sn.zip')
        open(fake_snapshot_path, 'w').close()
        self._assert_ex('cfy recover -f -s {0}'.format(fake_snapshot_path),
                        'Cannot perform recovery. manager key file not found. '
                        'Set the manager private key path via the '
                        'CLOUDIFY_MANAGER_PRIVATE_KEY_PATH environment '
                        'variable')

    @patch('cloudify_cli.bootstrap.bootstrap'
           '.read_manager_deployment_dump_if_needed')
    @patch('cloudify_cli.bootstrap.bootstrap.recover')
    def test_recover_from_different_directory_than_bootstrap_with_env_variable(self, *_):  # NOQA
        cli_runner.run_cli('cfy init')

        key_path = os.path.join(TEST_WORK_DIR, 'key.pem')
        open(key_path, 'w').close()

        # mock provider context
        with update_wd_settings() as wd:
            wd.set_provider_context({})

        try:
            os.environ['CLOUDIFY_MANAGER_PRIVATE_KEY_PATH'] = key_path
            cli_runner.run_cli('cfy recover -f -s {0}'.format(key_path))
        finally:
            del os.environ['CLOUDIFY_MANAGER_PRIVATE_KEY_PATH']
