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

from mock import MagicMock, patch, PropertyMock

from .test_cli_command import CliCommandTest
from .test_cli_command import BLUEPRINTS_DIR
from ...exceptions import SuppressedCloudifyCliError


class DeploymentUpdatesTest(CliCommandTest):
    def _mock_wait_for_executions(self, value):
        patcher = patch(
            'cloudify_cli.execution_events_fetcher.wait_for_execution',
            MagicMock(return_value=PropertyMock(error=value))
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    def setUp(self):
        super(DeploymentUpdatesTest, self).setUp()
        self.use_manager()

        self.client.deployment_updates.update = MagicMock()
        self.client.executions = MagicMock()

        self._mock_wait_for_executions(False)

        patcher = patch('cloudify_cli.inputs.inputs_to_dict', MagicMock())
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_deployment_update_successful(self):
        outcome = self.invoke(
            'cfy deployments update -p {0}/helloworld/blueprint.yaml '
            'my_deployment'.format(BLUEPRINTS_DIR))
        self.assertIn('Updating deployment my_deployment', outcome.logs)
        self.assertIn('Finished executing workflow', outcome.logs)
        self.assertIn(
            'Successfully updated deployment my_deployment', outcome.logs)

    def test_deployment_update_failure(self):
        self._mock_wait_for_executions(True)

        outcome = self.invoke(
            'cfy deployments update -p '
            '{0}/helloworld/blueprint.yaml '
            'my_deployment'.format(BLUEPRINTS_DIR),
            should_fail=True,
            exception=SuppressedCloudifyCliError)

        logs = outcome.logs.split('\n')
        self.assertIn('Updating deployment my_deployment', logs[-3])
        self.assertIn('Execution of workflow', logs[-2])
        self.assertIn('failed', logs[-2])
        self.assertIn(
            'Failed updating deployment my_deployment', logs[-1])

    def test_deployment_update_json_parameter(self):
        self.invoke(
            'cfy deployments update -p '
            '{0}/helloworld/blueprint.yaml '
            'my_deployment --json'.format(BLUEPRINTS_DIR))

    def test_deployment_update_include_logs_parameter(self):
        self.invoke(
            'cfy deployments update -p '
            '{0}/helloworld/blueprint.yaml '
            'my_deployment --include-logs'.format(BLUEPRINTS_DIR))

    def test_deployment_update_skip_install_flag(self):
        self.invoke(
            'cfy deployments update -p '
            '{0}/helloworld/blueprint.yaml '
            'my_deployment --skip-install'.format(BLUEPRINTS_DIR))

    def test_deployment_update_skip_uninstall_flag(self):
        self.invoke(
            'cfy deployments update -p '
            '{0}/helloworld/blueprint.yaml '
            'my_deployment --skip-uninstall'.format(BLUEPRINTS_DIR))

    def test_deployment_update_force_flag(self):
        self.invoke(
            'cfy deployments update -p '
            '{0}/helloworld/blueprint.yaml '
            'my_deployment --force'.format(BLUEPRINTS_DIR))

    def test_deployment_update_override_workflow_parameter(self):
        self.invoke(
            'cfy deployments update -p '
            '{0}/helloworld/blueprint.yaml '
            'my_deployment -w override-wf'.format(BLUEPRINTS_DIR))

    def test_deployment_update_archive_location_parameter(self):
        self.invoke(
            'cfy deployments update -p '
            '{0}/helloworld.zip '
            'my_deployment'.format(BLUEPRINTS_DIR))

    def test_dep_update_archive_loc_and_bp_path_parameters_exclusion(self):
        self.invoke(
            'cfy deployments update -p '
            '{0}/helloworld/blueprint.yaml -n {0}/helloworld/'
            'blueprint2.yaml my_deployment'.format(BLUEPRINTS_DIR),
            should_fail=True)

    def test_deployment_update_blueprint_filename_parameter(self):
        self.invoke(
            'cfy deployments update -p '
            '{0}/helloworld.zip -n my-blueprint.yaml '
            'my_deployment'.format(BLUEPRINTS_DIR))

    def test_deployment_update_inputs_parameter(self):
        self.invoke(
            'cfy deployments update -p '
            '{0}/helloworld.zip -i {0}/helloworld/inputs.yaml '
            'my_deployment'.format(BLUEPRINTS_DIR))

    def test_deployment_update_multiple_inputs_parameter(self):
        self.invoke(
            'cfy deployments update -p '
            '{0}/helloworld.zip -i {0}/helloworld/inputs.yaml '
            '-i {0}/helloworld/inputs.yaml my_deployment'
            .format(BLUEPRINTS_DIR))

    def test_deployment_update_no_deployment_id_parameter(self):
        self.invoke(
            'cfy deployments update -p '
            '{0}/helloworld.zip'.format(BLUEPRINTS_DIR),
            should_fail=True,
            exception=SystemExit)

    def test_deployment_update_no_bp_path_nor_archive_loc_parameters(self):
        self.invoke(
            'cfy deployments update my_deployment'.format(
                BLUEPRINTS_DIR),
            should_fail=True,
            exception=SystemExit)
