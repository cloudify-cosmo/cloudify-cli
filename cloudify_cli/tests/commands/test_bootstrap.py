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
Tests 'cfy bootstrap'
"""
import os
import json
import shutil
import tempfile
import subprocess

import mock
import fabric.api as fabric

from cloudify_cli import common
from cloudify_cli.bootstrap import bootstrap
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import \
    CliCommandTest, BLUEPRINTS_DIR


def mock_fabric_sudo(command, *args, **kwargs):
    subprocess.check_call(command.split(' '))


def mock_fabric_put(local_path, remote_path, *args, **kwargs):
    shutil.copy(local_path, remote_path)


class BootstrapTest(CliCommandTest):

    def test_bootstrap_install_plugins(self):

        cli_runner.run_cli('cfy init')
        blueprint_path = '{0}/local/{1}.yaml'\
                         .format(BLUEPRINTS_DIR,
                                 'blueprint_with_plugins')
        with mock.patch('cloudify_cli.bootstrap.bootstrap.'
                        'validate_manager_deployment_size'):
            self.assert_method_called(
                cli_command='cfy bootstrap --install-plugins -p {0}'
                            .format(blueprint_path),
                module=common,
                function_name='install_blueprint_plugins',
                kwargs={'blueprint_path': blueprint_path})

    def test_bootstrap_no_validations_install_plugins(self):

        cli_runner.run_cli('cfy init')
        blueprint_path = '{0}/local/{1}.yaml' \
            .format(BLUEPRINTS_DIR,
                    'blueprint_with_plugins')
        self.assert_method_called(
            cli_command='cfy bootstrap --skip-validations '
                        '--install-plugins -p {0}'
            .format(blueprint_path),
            module=common,
            function_name='install_blueprint_plugins',
            kwargs={'blueprint_path': blueprint_path}
        )

    def test_bootstrap_no_validations_add_ignore_bootstrap_validations(self):

        cli_runner.run_cli('cfy init')
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')
        self.assert_method_called(
            cli_command='cfy bootstrap --skip-validations -p {0} '
                        '-i "some_input=some_value"'.format(blueprint_path),
            module=common,
            function_name='add_ignore_bootstrap_validations_input',
            args=[['"some_input=some_value"']]
        )

    def test_viable_ignore_bootstrap_validations_input(self):
        inputs = []
        inputs = common.add_ignore_bootstrap_validations_input(inputs)
        ignore_input = json.loads(inputs[0])
        self.assertTrue(ignore_input['ignore_bootstrap_validations'])

    def test_bootstrap_missing_plugin(self):

        cli_runner.run_cli('cfy init')
        blueprint_path = '{0}/local/{1}.yaml' \
            .format(BLUEPRINTS_DIR,
                    'blueprint_with_plugins')
        cli_command = 'cfy bootstrap -p {0}'.format(
            blueprint_path)

        with mock.patch('cloudify_cli.bootstrap.bootstrap.'
                        'validate_manager_deployment_size'):
            self._assert_ex(
                cli_cmd=cli_command,
                err_str_segment='No module named tasks',
                possible_solutions=[
                    "Run 'cfy local install-plugins -p {0}'"
                    .format(blueprint_path),
                    "Run 'cfy bootstrap --install-plugins -p {0}'"
                    .format(blueprint_path)])

    def test_bootstrap_no_validation_missing_plugin(self):

        cli_runner.run_cli('cfy init')
        blueprint_path = '{0}/local/{1}.yaml' \
            .format(BLUEPRINTS_DIR,
                    'blueprint_with_plugins')
        cli_command = 'cfy bootstrap --skip-validations -p {0}'.format(
            blueprint_path)

        self._assert_ex(
            cli_cmd=cli_command,
            err_str_segment='No module named tasks',
            possible_solutions=[
                "Run 'cfy local install-plugins -p {0}'"
                .format(blueprint_path),
                "Run 'cfy bootstrap --install-plugins -p {0}'"
                .format(blueprint_path)
            ]
        )

    def test_bootstrap_validate_manager_deployment_size(self):
        # verifying validation over manager deployment size is called before
        # calling bootstrap
        cli_runner.run_cli('cfy init')
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')
        self.assert_method_called(
            cli_command='cfy bootstrap --validate-only -p {0}'.format(
                blueprint_path),
            module=bootstrap,
            function_name='validate_manager_deployment_size',
            kwargs=dict(blueprint_path=blueprint_path))

    def test_bootstrap_skip_validate_manager_deployment_size(self):
        # verifying validation over manager deployment size is not called
        # when the "--skip-validation" flag is used
        cli_runner.run_cli('cfy init')
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')
        self.assert_method_not_called(
            cli_command='cfy bootstrap --validate-only --skip-validations '
                        '-p {0}'.format(blueprint_path),
            module=bootstrap,
            function_name='validate_manager_deployment_size')

    def test_copy_agent_key_no_target_dir(self):
        original_sudo = fabric.sudo
        fabric.sudo = mock_fabric_sudo
        original_put = fabric.put
        fabric.put = mock_fabric_put
        tmp_dir = tempfile.mkdtemp()
        local_path = os.path.join(tmp_dir, 'local')
        os.mkdir(local_path)
        local_path = os.path.join(local_path, 'key')
        with open(local_path, 'w') as key:
            key.write('key_content')
        remote_path = os.path.join(tmp_dir, 'remote', 'key')
        try:
            bootstrap._copy_agent_key(local_path, remote_path,
                                      fabric_env=bootstrap.build_fabric_env(
                                          'local', '', ''
                                      ))
            self.assertTrue(os.path.exists(remote_path))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            fabric.put = original_put
            fabric.sudo = original_sudo
