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

"""
Tests all commands that start with 'cfy blueprints'
"""

from mock import MagicMock, patch

from cloudify_cli.exceptions import SuppressedCloudifyCliError
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest
from cloudify_cli.tests.commands.test_cli_command import BLUEPRINTS_DIR


class DeploymentUpdatesTest(CliCommandTest):

    def setUp(self):
        super(DeploymentUpdatesTest, self).setUp()
        self._create_cosmo_wd_settings()

        self._is_update_execution_error = False

        def wait_for_execution_mock(*args, **kwargs):
            return MagicMock(error=self._is_update_execution_error)

        self.client.deployment_updates.update = MagicMock()
        self.client.executions = MagicMock()

        patcher = patch(
            'cloudify_cli.commands.deployments.wait_for_execution',
            wait_for_execution_mock)
        self.addCleanup(patcher.stop)
        patcher.start()

        patcher = patch('cloudify_cli.utils.inputs_to_dict', MagicMock())
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_deployment_update_successful(self):
        output = cli_runner.run_cli(
            'cfy deployments update -p '
            '{0}/helloworld/blueprint.yaml '
            '-d my_deployment'.format(BLUEPRINTS_DIR))
        self.assertIn('Updating deployment my_deployment', output)
        self.assertIn('Finished executing workflow', output)
        self.assertIn('Successfully updated deployment my_deployment', output)

    def test_deployment_update_failure(self):
        self._is_update_execution_error = True

        with self.assertRaises(SuppressedCloudifyCliError):
            output = cli_runner.run_cli(
                'cfy deployments update -p '
                '{0}/helloworld/blueprint.yaml '
                '-d my_deployment'.format(BLUEPRINTS_DIR))
            self.assertIn('Updating deployment my_deployment', output)
            self.assertIn('Finished executing workflow', output)
            self.assertIn('Failed updating deployment my_deployment', output)

    def test_deployment_update_json_parameter(self):
        cli_runner.run_cli(
            'cfy deployments update -p '
            '{0}/helloworld/blueprint.yaml '
            '-d my_deployment --json'.format(BLUEPRINTS_DIR))

    def test_deployment_update_include_logs_parameter(self):
        cli_runner.run_cli(
            'cfy deployments update -p '
            '{0}/helloworld/blueprint.yaml '
            '-d my_deployment --include-logs'.format(BLUEPRINTS_DIR))

    def test_deployment_update_skip_install_flag(self):
        cli_runner.run_cli(
            'cfy deployments update -p '
            '{0}/helloworld/blueprint.yaml '
            '-d my_deployment --skip-install'.format(BLUEPRINTS_DIR))

    def test_deployment_update_skip_uninstall_flag(self):
        cli_runner.run_cli(
            'cfy deployments update -p '
            '{0}/helloworld/blueprint.yaml '
            '-d my_deployment --skip-uninstall'.format(BLUEPRINTS_DIR))

    def test_deployment_update_override_workflow_parameter(self):
        cli_runner.run_cli(
            'cfy deployments update -p '
            '{0}/helloworld/blueprint.yaml '
            '-d my_deployment -w override-wf'.format(BLUEPRINTS_DIR))

    def test_deployment_update_archive_location_parameter(self):
        cli_runner.run_cli(
            'cfy deployments update -l '
            '{0}/helloworld/blueprint.tar.gz '
            '-d my_deployment'.format(BLUEPRINTS_DIR))

    def test_dep_update_archive_loc_and_bp_path_parameters_exclusion(self):
        with self.assertRaises(SystemExit) as sys_exit:
            cli_runner.run_cli(
                'cfy deployments update -l '
                '{0}/helloworld/blueprint.tar.gz -p {0}/helloworld/'
                'blueprint.yaml -d my_deployment'.format(BLUEPRINTS_DIR))
            self.assertNotEquals(sys_exit.exception.code, 0)

    def test_deployment_update_blueprint_filename_parameter(self):
        cli_runner.run_cli(
            'cfy deployments update -l '
            '{0}/helloworld/blueprint.tar.gz -n my-blueprint.yaml '
            '-d my_deployment'.format(BLUEPRINTS_DIR))

    def test_deployment_update_inputs_parameter(self):
        cli_runner.run_cli(
            'cfy deployments update -l '
            '{0}/helloworld/blueprint.tar.gz -i inputs.yaml '
            '-d my_deployment'.format(BLUEPRINTS_DIR))

    def test_deployment_update_multiple_inputs_parameter(self):
        cli_runner.run_cli(
            'cfy deployments update -l '
            '{0}/helloworld/blueprint.tar.gz -i inputs1.yaml -i inputs2.yaml '
            '-d my_deployment'.format(BLUEPRINTS_DIR))

    def test_deployment_update_no_deployment_id_parameter(self):
        with self.assertRaises(SystemExit) as sys_exit:
            cli_runner.run_cli(
                'cfy deployments update -p '
                '{0}/helloworld/blueprint.tar.gz'.format(BLUEPRINTS_DIR))
        self.assertNotEquals(sys_exit.exception.code, 0)

    def test_deployment_update_no_bp_path_nor_archive_loc_parameters(self):
        with self.assertRaises(SystemExit) as sys_exit:
            cli_runner.run_cli(
                'cfy deployments update -d my_deployment'.format(
                    BLUEPRINTS_DIR))
        self.assertNotEquals(sys_exit.exception.code, 0)
