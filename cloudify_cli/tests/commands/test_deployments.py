########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############


import json
import datetime

from mock import patch, MagicMock, PropertyMock, Mock

from cloudify_rest_client import deployments, executions, blueprints
from cloudify_rest_client.exceptions import CloudifyClientError, \
    MissingRequiredDeploymentInputError, UnknownDeploymentInputError

from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.constants import DEFAULT_TENANT_NAME

from ... import exceptions
from .mocks import MockListResponse
from .test_base import CliCommandTest
from .constants import (BLUEPRINTS_DIR,
                        SAMPLE_BLUEPRINT_PATH,
                        SAMPLE_ARCHIVE_PATH,
                        SAMPLE_INPUTS_PATH)


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
        self.client.blueprints.upload = MagicMock()
        self.client.executions = MagicMock()
        self.client.deployment_updates.update_with_existing_blueprint = \
            MagicMock()

        self._mock_wait_for_executions(False)

        patcher = patch('cloudify_cli.inputs.inputs_to_dict', MagicMock())
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_deployment_update_get(self):
        old_value = 'old value 1'
        new_value = 'new value 1'
        self.client.deployment_updates.get = Mock(return_value={
            'id': 'update-id-1',
            'old_inputs': {'inp1': old_value},
            'new_inputs': {'inp1': new_value},
        })
        outcome = self.invoke('deployments get-update update-id-1')
        self.assertIn(old_value, outcome.output)
        self.assertIn(new_value, outcome.output)

    def test_deployment_update_get_json(self):
        old_value = 'old value 1'
        new_value = 'new value 1'
        self.client.deployment_updates.get = Mock(return_value={
            'id': 'update-id-1',
            'old_inputs': {'inp1': old_value},
            'new_inputs': {'inp1': new_value},
        })
        outcome = self.invoke('deployments get-update update-id-1 --json')
        parsed = json.loads(outcome.output)
        self.assertEqual(parsed['old_inputs'], {'inp1': old_value})
        self.assertEqual(parsed['new_inputs'], {'inp1': new_value})

    def test_deployment_update_successful(self):
        outcome = self.invoke(
            'cfy deployments update -p {0} '
            'my_deployment'.format(SAMPLE_BLUEPRINT_PATH))
        self.assertIn('Updating deployment my_deployment', outcome.logs)
        self.assertIn('Finished executing workflow', outcome.logs)
        self.assertIn(
            'Successfully updated deployment my_deployment', outcome.logs)

    def test_deployment_update_failure(self):
        self._mock_wait_for_executions(True)

        outcome = self.invoke(
            'cfy deployments update -p {0} my_deployment'
            .format(SAMPLE_BLUEPRINT_PATH),
            err_str_segment='',
            exception=exceptions.SuppressedCloudifyCliError)

        logs = outcome.logs.split('\n')
        self.assertIn('Updating deployment my_deployment', logs[-3])
        self.assertIn('Execution of workflow', logs[-2])
        self.assertIn('failed', logs[-2])
        self.assertIn(
            'Failed updating deployment my_deployment', logs[-1])

    def test_deployment_update_json_parameter(self):
        self.invoke(
            'cfy deployments update -p '
            '{0} my_deployment --json-output'
            .format(SAMPLE_BLUEPRINT_PATH))

    def test_deployment_update_include_logs_parameter(self):
        self.invoke(
            'cfy deployments update -p '
            '{0} my_deployment --include-logs'
            .format(SAMPLE_BLUEPRINT_PATH))

    def test_deployment_update_skip_install_flag(self):
        self.invoke(
            'cfy deployments update -p '
            '{0} my_deployment --skip-install'
            .format(SAMPLE_BLUEPRINT_PATH))

    def test_deployment_update_skip_uninstall_flag(self):
        self.invoke(
            'cfy deployments update -p '
            '{0} my_deployment --skip-uninstall'
            .format(SAMPLE_BLUEPRINT_PATH))

    def test_deployment_update_force_flag(self):
        self.invoke(
            'cfy deployments update -p '
            '{0} my_deployment --force'
            .format(SAMPLE_BLUEPRINT_PATH))

    def test_deployment_update_override_workflow_parameter(self):
        self.invoke(
            'cfy deployments update -p '
            '{0} my_deployment -w override-wf'
            .format(SAMPLE_BLUEPRINT_PATH))

    def test_deployment_update_archive_location_parameter(self):
        self.invoke(
            'cfy deployments update -p {0} my_deployment'
            .format(SAMPLE_ARCHIVE_PATH))

    def test_dep_update_archive_loc_and_bp_path_parameters_exclusion(self):
        self.invoke(
            'cfy deployments update -p '
            '{0} -n {1}/helloworld/'
            'blueprint2.yaml my_deployment'
            .format(SAMPLE_BLUEPRINT_PATH, BLUEPRINTS_DIR),
            err_str_segment='param should be passed only when updating'
                            ' from an archive'
        )

    def test_deployment_update_blueprint_filename_parameter(self):
        self.invoke(
            'cfy deployments update -p '
            '{0} -n blueprint.yaml my_deployment'
            .format(SAMPLE_ARCHIVE_PATH))

    def test_deployment_update_inputs_parameter(self):
        self.invoke(
            'cfy deployments update -p '
            '{0} -i {1} my_deployment'
            .format(SAMPLE_ARCHIVE_PATH, SAMPLE_INPUTS_PATH))

    def test_deployment_update_multiple_inputs_parameter(self):
        self.invoke(
            'cfy deployments update -p '
            '{0} -i {1} -i {1} my_deployment'
            .format(SAMPLE_ARCHIVE_PATH, SAMPLE_INPUTS_PATH))

    def test_deployment_update_no_deployment_id_parameter(self):
        outcome = self.invoke(
            'cfy deployments update -p '
            '{0}'.format(SAMPLE_ARCHIVE_PATH),
            err_str_segment='2',  # Exit code
            exception=SystemExit)

        self.assertIn('Missing argument "deployment-id"', outcome.output)

    def test_deployment_update_no_bp_path_nor_archive_loc_parameters(self):
        self.invoke(
            'cfy deployments update my_deployment'.format(
                BLUEPRINTS_DIR),
            err_str_segment='Must supply either a blueprint '
                            '(by id of an existing blueprint, or a path to a '
                            'new blueprint), or new inputs',
            exception=CloudifyCliError)


class DeploymentsTest(CliCommandTest):

    def setUp(self):
        super(DeploymentsTest, self).setUp()
        self.use_manager()

    def test_deployment_create(self):

        deployment = deployments.Deployment({
            'deployment_id': 'deployment_id'
        })

        self.client.deployments.create = MagicMock(return_value=deployment)
        self.invoke(
            'cfy deployments create deployment -b a-blueprint-id')

    def test_deployment_create_with_skip_plugins_validation_flag(self):
        deployment = deployments.Deployment({
            'deployment_id': 'deployment_id'
        })
        self.client.deployments.create = MagicMock(return_value=deployment)
        self.invoke(
            'cfy deployments create deployment -b a --skip-plugins-validation')
        call_args = list(self.client.deployments.create.call_args)
        self.assertIn('skip_plugins_validation', call_args[1])
        self.assertEqual(call_args[1]['skip_plugins_validation'], True)

    def test_deployment_create_without_skip_plugins_validation_flag(self):
        deployment = deployments.Deployment({
            'deployment_id': 'deployment_id'
        })
        self.client.deployments.create = MagicMock(return_value=deployment)
        self.invoke(
            'cfy deployments create deployment -b aa')
        call_args = list(self.client.deployments.create.call_args)
        self.assertIn('skip_plugins_validation', call_args[1])
        self.assertEqual(call_args[1]['skip_plugins_validation'], False)

    def test_deployments_delete(self):
        self.client.deployments.delete = MagicMock()
        self.client.executions.list = MagicMock(
            side_effect=CloudifyClientError(
                '`Deployment` with ID `my-dep` was not found')
        )
        self.invoke('cfy deployments delete my-dep')

    def test_deployments_execute(self):
        execute_response = executions.Execution({'status': 'started'})
        get_execution_response = executions.Execution({
            'status': 'terminated',
            'workflow_id': 'mock_wf',
            'deployment_id': 'deployment-id',
            'blueprint_id': 'blueprint-id',
            'error': '',
            'id': 'id',
            'created_at': datetime.datetime.now(),
            'parameters': {}
        })
        success_event = {
            'event_type': 'workflow_succeeded',
            'type': 'foo',
            'timestamp': '12345678',
            'message': 'workflow execution succeeded',
            'error_causes': '<error_causes>',
            'deployment_id': 'deployment-id',
            'execution_id': '<execution_id>',
            'node_name': '<node_name>',
            'operation': '<operation>',
            'workflow_id': '<workflow_id>',
            'node_instance_id': '<node_instance_id>',
        }
        get_events_response = MockListResponse([success_event], 1)

        self.client.executions.start = MagicMock(
            return_value=execute_response)
        self.client.executions.get = MagicMock(
            return_value=get_execution_response)
        self.client.events.list = MagicMock(return_value=get_events_response)
        self.invoke('cfy executions start install -d a-deployment-id')

    def test_deployments_list_all(self):
        self.client.deployments.list = MagicMock(
            return_value=MockListResponse()
        )
        self.invoke('cfy deployments list')
        self.invoke('cfy deployments list -t dummy_tenant')
        self.invoke('cfy deployments list -a')

    def test_deployments_list_of_blueprint(self):
        deps = [
            {
                'blueprint_id': 'b1_blueprint',
                'created_at': 'now',
                'created_by': 'admin',
                'updated_at': 'now',
                'id': 'id',
                'visibility': 'private',
                'tenant_name': DEFAULT_TENANT_NAME
            },
            {
                'blueprint_id': 'b1_blueprint',
                'created_at': 'now',
                'created_by': 'admin',
                'updated_at': 'now',
                'id': 'id',
                'visibility': 'private',
                'tenant_name': DEFAULT_TENANT_NAME
            },
            {
                'blueprint_id': 'b2_blueprint',
                'created_at': 'now',
                'created_by': 'admin',
                'updated_at': 'now',
                'id': 'id',
                'visibility': 'private',
                'tenant_name': DEFAULT_TENANT_NAME
            }
        ]

        self.client.deployments.list = MagicMock(
            return_value=MockListResponse(items=deps)
        )
        outcome = self.invoke('cfy deployments list -b b1_blueprint -v')
        self.assertNotIn('b2_blueprint', outcome.logs)
        self.assertIn('b1_blueprint', outcome.logs)

    def test_deployments_execute_nonexistent_operation(self):
        # Verifying that the CLI allows for arbitrary operation names,
        # while also ensuring correct error-handling of nonexistent
        # operations

        expected_error = "operation nonexistent-operation doesn't exist"

        self.client.executions.start = MagicMock(
            side_effect=CloudifyClientError(expected_error))

        command = \
            'cfy executions start nonexistent-operation -d a-deployment-id'
        self.invoke(
            command,
            err_str_segment=expected_error,
            exception=CloudifyClientError)

    def test_deployments_outputs(self):

        outputs = deployments.DeploymentOutputs({
            'deployment_id': 'dep1',
            'outputs': {
                'port': 8080
            }
        })
        deployment = deployments.Deployment({
            'outputs': {
                'port': {
                    'description': 'Webserver port.',
                    'value': '...'
                }
            }
        })
        self.client.deployments.get = MagicMock(return_value=deployment)
        self.client.deployments.outputs.get = MagicMock(return_value=outputs)
        self.invoke('cfy deployments outputs dep1')

    def test_deployments_outputs_json(self):
        outputs = deployments.DeploymentOutputs({
            'deployment_id': 'dep1',
            'outputs': {
                'port': 8080
            }
        })
        deployment = deployments.Deployment({
            'outputs': {
                'port': {
                    'description': 'Webserver port.',
                    'value': '...'
                }
            }
        })
        self.client.deployments.get = MagicMock(return_value=deployment)
        self.client.deployments.outputs.get = MagicMock(return_value=outputs)
        outcome = self.invoke('cfy deployments outputs dep1 --json')
        parsed = json.loads(outcome.output)
        self.assertEqual(parsed, {
            'port': {
                'value': 8080,
                'description': 'Webserver port.'
            }
        })

    def test_deployments_inputs(self):
        deployment = deployments.Deployment({
            'deployment_id': 'deployment_id',
            'inputs': {'key1': 'val1', 'key2': 'val2'}
        })

        expected_outputs = [
            'Retrieving inputs for deployment deployment_id...',
            '- "key1":',
            'Value: val1',
            '- "key2":',
            'Value: val2',
        ]

        self.client.deployments.get = MagicMock(return_value=deployment)
        outcome = self.invoke('cfy deployments inputs deployment_id')
        outcome = [o.strip() for o in outcome.logs.split('\n')]

        for output in expected_outputs:
            self.assertIn(output, outcome)

    def test_deployments_inputs_json(self):
        deployment = deployments.Deployment({
            'deployment_id': 'deployment_id',
            'inputs': {'key1': 'val1', 'key2': 'val2'}
        })

        self.client.deployments.get = MagicMock(return_value=deployment)
        outcome = self.invoke('cfy deployments inputs deployment_id --json')
        parsed = json.loads(outcome.output)
        self.assertEqual(parsed, {'key1': 'val1', 'key2': 'val2'})

    def test_missing_required_inputs(self):
        self._test_deployment_inputs(
            MissingRequiredDeploymentInputError,
            {'input1': 'value1'},
            ['Unable to create deployment']
        )

    def test_invalid_input(self):
        self._test_deployment_inputs(
            UnknownDeploymentInputError,
            {'input1': 'value1',
             'input2': 'value2',
             'input3': 'value3'},
            ['Unable to create deployment']
        )

    def test_deployments_set_visibility(self):
        self.client.deployments.set_visibility = MagicMock()
        self.invoke('cfy deployments set-visibility a-deployment-id -l '
                    'tenant')

    def test_deployments_set_visibility_invalid_argument(self):
        self.invoke(
            'cfy deployments set-visibility a-deployment-id -l private',
            err_str_segment='Invalid visibility: `private`',
            exception=CloudifyCliError
        )
        self.invoke(
            'cfy deployments set-visibility a-deployment-id -l global',
            err_str_segment='Invalid visibility: `global`',
            exception=CloudifyCliError
        )
        self.invoke(
            'cfy deployments set-visibility a-deployment-id -l bla',
            err_str_segment='Invalid visibility: `bla`',
            exception=CloudifyCliError
        )

    def test_deployments_set_visibility_missing_argument(self):
        outcome = self.invoke(
            'cfy deployments set-visibility a-deployment-id',
            err_str_segment='2',
            exception=SystemExit
        )
        self.assertIn('Missing option "-l" / "--visibility"', outcome.output)

    def test_deployments_set_visibility_wrong_argument(self):
        outcome = self.invoke(
            'cfy deployments set-visibility a-deployment-id -g',
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        self.assertIn('Error: no such option: -g', outcome.output)

    def test_deployments_create_mutually_exclusive_arguments(self):
        outcome = self.invoke(
            'cfy deployments create deployment -b a-blueprint-id -l tenant '
            '--private-resource',
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        self.assertIn('mutually exclusive with arguments:', outcome.output)

    def test_deployments_create_invalid_argument(self):
        self.invoke(
            'cfy deployments create deployment -b a-blueprint-id -l bla'
            .format(BLUEPRINTS_DIR),
            err_str_segment='Invalid visibility: `bla`',
            exception=CloudifyCliError
        )

    def test_deployments_create_with_visibility(self):
        self.client.deployments.create = MagicMock()
        self.invoke('cfy deployments create deployment -b a-blueprint-id '
                    '-l private'
                    .format(SAMPLE_ARCHIVE_PATH))

    def _test_deployment_inputs(self, exception_type,
                                inputs, expected_outputs=None):
        def raise_error(*args, **kwargs):
            raise exception_type('no inputs')

        blueprint = blueprints.Blueprint({
            'plan': {
                'inputs': {
                    'input1': {'description': 'val1'},
                    'input2': {'description': 'val2'}
                }
            }
        })

        self.client.blueprints.get = MagicMock(return_value=blueprint)
        self.client.deployments.create = raise_error

        inputs_line = ' '.join(
            ['-i {0}={1}'.format(key, value) for
             key, value in inputs.iteritems()])

        outcome = self.invoke(
            'cfy deployments create deployment -b a-blueprint-id {0}'.format(
                inputs_line),
            exception=exceptions.SuppressedCloudifyCliError,
            err_str_segment='no inputs'
        )
        outcome = [o.strip() for o in outcome.logs.split('\n')]

        if not expected_outputs:
            expected_outputs = []

        for output in expected_outputs:
            found = False
            for outcome_line in outcome:
                if output in outcome_line:
                    found = True
                    break
            self.assertTrue(found, 'String ''{0}'' not found in outcome {1}'
                            .format(output, outcome))
