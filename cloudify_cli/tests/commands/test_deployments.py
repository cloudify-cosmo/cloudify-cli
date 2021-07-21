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

from __future__ import unicode_literals


import json
import inspect
import datetime
import warnings
from uuid import UUID

from mock import patch, MagicMock, PropertyMock, Mock

from cloudify_rest_client import (
    deployments,
    executions,
    blueprints,
    deployment_updates,
    execution_schedules
)
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.exceptions import (
    CloudifyClientError,
    UnknownDeploymentInputError,
    MissingRequiredDeploymentInputError
)
from cloudify_rest_client.deployment_modifications import (
    DeploymentModification
)
from cloudify_rest_client.responses import ListResponse, Metadata

from cloudify_cli.constants import DEFAULT_TENANT_NAME
from cloudify_cli.exceptions import CloudifyCliError, CloudifyValidationError

from ... import exceptions
from .mocks import MockListResponse
from .test_base import CliCommandTest
from .constants import (BLUEPRINTS_DIR,
                        SAMPLE_BLUEPRINT_PATH,
                        SAMPLE_INPUTS_PATH,
                        UPDATED_BLUEPRINT_ID)


class DeploymentUpdatesTest(CliCommandTest):
    def _mock_wait_for_executions(self, value):
        patcher = patch(
            'cloudify_cli.execution_events_fetcher.wait_for_execution',
            MagicMock(return_value=PropertyMock(error=value))
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    def _mock_wait_for_blueprint_upload(self, value):
        patcher = patch(
            'cloudify_cli.utils.wait_for_blueprint_upload',
            MagicMock(return_value=PropertyMock(error=value))
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    def _upload_update_blueprint(self):
        self.invoke('cfy blueprints upload -b {0} {1}'
                    .format(UPDATED_BLUEPRINT_ID, SAMPLE_BLUEPRINT_PATH))

    def setUp(self):
        super(DeploymentUpdatesTest, self).setUp()
        self.client.license.check = Mock()
        self.use_manager()

        self.client.deployment_updates.update = MagicMock()
        self.client.blueprints.upload = MagicMock()
        self.client.executions = MagicMock()
        self.client.deployment_updates.update_with_existing_blueprint = \
            MagicMock()

        self._mock_wait_for_executions(False)
        self._mock_wait_for_blueprint_upload(False)

        patcher = patch('cloudify_cli.inputs.inputs_to_dict', MagicMock())
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_deployment_update_get(self):
        old_value = 'old value 1'
        new_value = 'new value 1'
        steps = [{'entity_id': 'step1'}, {'entity_id': 'step2'}]
        self.client.deployment_updates.get = Mock(return_value={
            'id': 'update-id-1',
            'old_inputs': {'inp1': old_value},
            'new_inputs': {'inp1': new_value},
            'steps': steps,
            'recursive_dependencies': {}
        })
        outcome = self.invoke('deployments get-update update-id-1')

        self.assertIn(old_value, outcome.output)
        self.assertIn(new_value, outcome.output)

        for d in steps:
            for k, v in d.items():
                self.assertIn(str(k), outcome.output)
                self.assertIn(str(v), outcome.output)

    def test_deployment_update_preview(self):
        old_value = 'old value 1'
        new_value = 'new value 1'
        steps = [
            {'entity_id': 'nodes:step1', 'action': 'add'},
            {'entity_id': 'nodes:step2', 'action': 'remove'},
        ]
        self.client.deployment_updates.update_with_existing_blueprint = Mock(
            return_value={
                'id': 'update-id-1',
                'old_inputs': {'inp1': old_value},
                'new_inputs': {'inp1': new_value},
                'steps': steps,
                'recursive_dependencies': {'deployment': 'dependent_dep'}
            })
        outcome = self.invoke(
            'deployments update dep-1 -b b2 --preview --json')
        output = json.loads(outcome.output)

        self.assertEqual(output['installed_nodes'], ['step1'])
        self.assertEqual(output['uninstalled_nodes'], ['step2'])
        self.assertEqual(output['recursive_dependencies'],
                         {'deployment': 'dependent_dep'})

        # find out if the preview=True argument has been set. It might have
        # been passed positionally or by name into the rest-client method,
        # so let's use inspect to find out which argument value was actually
        # the preview arg
        calls = self.client.deployment_updates\
            .update_with_existing_blueprint.mock_calls
        self.assertEqual(len(calls), 1)
        _, args, kwargs = calls[0]
        call_args = inspect.getcallargs(
            deployment_updates.DeploymentUpdatesClient(None)
            .update_with_existing_blueprint,
            *args, **kwargs)
        self.assertTrue(call_args['preview'])

    def test_deployment_update_update_plugins_is_false(self):
        update_client_mock = Mock()
        self.client.deployment_updates.update_with_existing_blueprint = \
            update_client_mock
        self.invoke('deployments update dep-1 -b b2 --dont-update-plugins')

        calls = self.client.deployment_updates\
            .update_with_existing_blueprint.mock_calls
        self.assertEqual(len(calls), 1)
        _, args, kwargs = calls[0]
        call_args = inspect.getcallargs(
            deployment_updates.DeploymentUpdatesClient(None)
            .update_with_existing_blueprint,
            *args, **kwargs)

        self.assertIn('update_plugins', call_args)
        self.assertFalse(call_args['update_plugins'])

    def test_deployment_update_update_plugins_is_true(self):
        update_client_mock = Mock()
        self.client.deployment_updates.update_with_existing_blueprint = \
            update_client_mock
        self.invoke('deployments update dep-1 -b b2')

        calls = self.client.deployment_updates\
            .update_with_existing_blueprint.mock_calls
        self.assertEqual(len(calls), 1)
        _, args, kwargs = calls[0]
        call_args = inspect.getcallargs(
            deployment_updates.DeploymentUpdatesClient(None)
            .update_with_existing_blueprint,
            *args, **kwargs)

        self.assertIn('update_plugins', call_args)
        self.assertTrue(call_args['update_plugins'])

    def test_deployment_update_get_json(self):
        old_value = 'old value 1'
        new_value = 'new value 1'
        steps = [{'entity_id': 'step1'}, {'entity_id': 'step2'}]
        self.client.deployment_updates.get = Mock(return_value={
            'id': 'update-id-1',
            'old_inputs': {'inp1': old_value},
            'new_inputs': {'inp1': new_value},
            'steps': steps
        })
        outcome = self.invoke('deployments get-update update-id-1 --json')
        parsed = json.loads(outcome.output)
        self.assertEqual(parsed['old_inputs'], {'inp1': old_value})
        self.assertEqual(parsed['new_inputs'], {'inp1': new_value})

    def test_deployment_update_successful(self):
        self._upload_update_blueprint()
        outcome = self.invoke(
            'cfy deployments update -b {0} my_deployment'
            .format(UPDATED_BLUEPRINT_ID))
        self.assertIn('Updating deployment my_deployment', outcome.logs)
        self.assertIn('Finished executing workflow', outcome.logs)
        self.assertIn(
            'Successfully updated deployment my_deployment', outcome.logs)

    def test_deployment_update_failure(self):
        self._mock_wait_for_executions(True)
        self._upload_update_blueprint()
        outcome = self.invoke(
            'cfy deployments update -b {0} my_deployment'
            .format(UPDATED_BLUEPRINT_ID),
            err_str_segment='',
            exception=exceptions.SuppressedCloudifyCliError)

        logs = outcome.logs.split('\n')
        self.assertIn('Updating deployment my_deployment', logs[-3])
        self.assertIn('Execution of workflow', logs[-2])
        self.assertIn('failed', logs[-2])
        self.assertIn(
            'Failed updating deployment my_deployment', logs[-1])

    def test_deployment_update_json_parameter(self):
        self._upload_update_blueprint()
        with warnings.catch_warnings(record=True) as warns:
            self.invoke(
                'cfy deployments update my_deployment '
                '-b {0} --json-output'
                .format(UPDATED_BLUEPRINT_ID))
        # catch_warnings sometimes gets the same thing more than once,
        # depending on how are the tests run. I don't know why.
        self.assertTrue(warns)
        self.assertIn('use the global', str(warns[0]))

    def test_deployment_update_include_logs_parameter(self):
        self._upload_update_blueprint()
        self.invoke(
            'cfy deployments update my_deployment '
            '-b {0} --include-logs'
            .format(UPDATED_BLUEPRINT_ID))

    def test_deployment_update_skip_install_flag(self):
        self._upload_update_blueprint()
        self.invoke(
            'cfy deployments update my_deployment '
            '-b {0}  --skip-install'
            .format(UPDATED_BLUEPRINT_ID))

    def test_deployment_update_skip_uninstall_flag(self):
        self._upload_update_blueprint()
        self.invoke(
            'cfy deployments update my_deployment '
            '-b {0} --skip-uninstall'
            .format(UPDATED_BLUEPRINT_ID))

    def test_deployment_update_force_flag(self):
        self.invoke(
            'cfy deployments update my_deployment '
            '-b {0} --force'
            .format(UPDATED_BLUEPRINT_ID))

    def test_deployment_update_override_workflow_parameter(self):
        self._upload_update_blueprint()
        self.invoke(
            'cfy deployments update my_deployment '
            '-b {0}  -w override-wf'
            .format(UPDATED_BLUEPRINT_ID))

    def test_deployment_update_blueprint_id_parameter(self):
        self._upload_update_blueprint()
        self.invoke(
            'cfy deployments update -b {0} my_deployment'
            .format(UPDATED_BLUEPRINT_ID))

    def test_dep_update_blueprint_id_and_bp_path_parameters_exclusion(self):
        self._upload_update_blueprint()
        self.invoke(
            'cfy deployments update my_deployment '
            '-b {0} -n {1}/helloworld/blueprint2.yaml'
            .format(UPDATED_BLUEPRINT_ID, BLUEPRINTS_DIR),
            err_str_segment='param should be passed only when updating'
                            ' from an archive'
        )

    def test_deployment_update_blueprint_filename_parameter(self):
        self._upload_update_blueprint()
        self.invoke(
            'cfy deployments update my_deployment '
            '-b {0} -n blueprint.yaml '
            .format(UPDATED_BLUEPRINT_ID))

    def test_deployment_update_inputs_parameter(self):
        self._upload_update_blueprint()
        self.invoke(
            'cfy deployments update my_deployment '
            '-b {0} -i {1} '
            .format(UPDATED_BLUEPRINT_ID, SAMPLE_INPUTS_PATH))

    def test_deployment_update_multiple_inputs_parameter(self):
        self._upload_update_blueprint()
        self.invoke(
            'cfy deployments update my_deployment '
            '-b {0} -i {1} -i {1} '
            .format(UPDATED_BLUEPRINT_ID, SAMPLE_INPUTS_PATH))

    def test_deployment_update_no_deployment_id_parameter(self):
        self._upload_update_blueprint()
        outcome = self.invoke(
            'cfy deployments update -b '
            '{0}'.format(UPDATED_BLUEPRINT_ID),
            err_str_segment='2',  # Exit code
            exception=SystemExit)
        self.assertIn('missing argument', outcome.output.lower())
        self.assertIn('DEPLOYMENT_ID', outcome.output)

    def test_deployment_update_no_bp_path_nor_archive_loc_parameters(self):
        self.invoke(
            'cfy deployments update my_deployment',
            err_str_segment='Must supply either a blueprint '
                            '(by id of an existing blueprint, or a path to a '
                            'new blueprint), or new inputs',
            exception=CloudifyCliError)

    def test_deployment_update_inputs_correct(self):
        self._upload_update_blueprint()
        self.invoke(
            'cfy deployments update my_deployment '
            '-b {0} -i {1} --auto-correct-types'
            .format(UPDATED_BLUEPRINT_ID, SAMPLE_INPUTS_PATH))


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

    def test_deployment_create_with_site_name(self):
        deployment = deployments.Deployment({'deployment_id': 'deployment_id'})
        self.client.deployments.create = MagicMock(return_value=deployment)
        self.invoke('cfy deployments create deployment -b a --site-name site')
        call_args = list(self.client.deployments.create.call_args)
        self.assertEqual(call_args[1]['site_name'], 'site')

    def test_deployment_create_invalid_site_name(self):
        error_msg = 'The `site_name` argument contains illegal characters'
        self.invoke('cfy deployments create deployment -b a --site-name :site',
                    err_str_segment=error_msg,
                    exception=CloudifyValidationError)

    def test_deployment_create_without_site_name(self):
        deployment = deployments.Deployment({'deployment_id': 'deployment_id'})
        self.client.deployments.create = MagicMock(return_value=deployment)
        self.invoke('cfy deployments create deployment -b a')
        call_args = list(self.client.deployments.create.call_args)
        self.assertIsNone(call_args[1]['site_name'])

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
            'source_id': None,
            'target_id': None,
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
        self.invoke('cfy deployments set-visibility a-deployment-id -l '
                    'global')

    def test_deployments_set_visibility_invalid_argument(self):
        self.invoke(
            'cfy deployments set-visibility a-deployment-id -l private',
            err_str_segment='Invalid visibility: `private`',
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
        self.assertIn('missing option', outcome.output.lower())
        self.assertIn('--visibility', outcome.output)

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
            'cfy deployments create deployment -b a-blueprint-id -l bla',
            err_str_segment='Invalid visibility: `bla`',
            exception=CloudifyCliError
        )

    def test_deployments_create_with_visibility(self):
        self.client.deployments.create = MagicMock()
        self.invoke('cfy deployments create deployment -b a-blueprint-id '
                    '-l private')

    def test_deployments_set_site_with_site_name(self):
        self.client.deployments.set_site = MagicMock()
        self.invoke('cfy deployments set-site deployment_1 --site-name site')
        call_args = list(self.client.deployments.set_site.call_args)
        self.assertEqual(call_args[0][0], 'deployment_1')
        self.assertEqual(call_args[1]['site_name'], 'site')
        self.assertFalse(call_args[1]['detach_site'])

    def test_deployments_set_site_without_options(self):
        error_msg = 'Must provide either a `--site-name` of a valid site ' \
                    'or `--detach-site`'
        self.invoke('cfy deployments set-site deployment_1',
                    err_str_segment=error_msg,
                    exception=CloudifyCliError)

    def test_deployments_set_site_with_detach(self):
        self.client.deployments.set_site = MagicMock()
        self.invoke('cfy deployments set-site deployment_1 --detach-site')
        call_args = list(self.client.deployments.set_site.call_args)
        self.assertEqual(call_args[0][0], 'deployment_1')
        self.assertIsNone(call_args[1]['site_name'])
        self.assertTrue(call_args[1]['detach_site'])

    def test_deployments_set_site_mutually_exclusive(self):
        outcome = self.invoke(
            'cfy deployments set-site deployment_1 -s site --detach-site',
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        error_msg = 'Error: Illegal usage: `detach_site` is ' \
                    'mutually exclusive with arguments: [site_name]'
        self.assertIn(error_msg, outcome.output)

    def test_deployment_set_site_no_deployment_id(self):
        outcome = self.invoke('cfy deployments set-site',
                              err_str_segment='2',  # Exit code
                              exception=SystemExit)

        self.assertIn('missing argument', outcome.output.lower())
        self.assertIn('DEPLOYMENT_ID', outcome.output)

    def test_deployment_set_site_invalid_site_name(self):
        error_msg = 'The `site_name` argument contains illegal characters'
        self.invoke('cfy deployments set-site deployment_1 --site-name :site',
                    err_str_segment=error_msg,
                    exception=CloudifyValidationError)

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
             key, value in inputs.items()])

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

    def test_create_deployment_with_display_name(self):
        dep_display_name = 'Depl\xf3yment'
        self.client.deployments.create = Mock()
        self.invoke('cfy deployments create -b bp1 -n {0} '
                    'dep1'.format(dep_display_name))
        call_args = list(self.client.deployments.create.call_args)
        self.assertEqual(call_args[1]['display_name'], dep_display_name)

    def test_create_deployment_display_name_defaults_to_id(self):
        dep_id = 'dep1'
        self.client.deployments.create = Mock()
        self.invoke('cfy deployments create -b bp1 {0}'.format(dep_id))
        call_args = list(self.client.deployments.create.call_args)
        self.assertEqual(call_args[1]['display_name'], dep_id)

    def test_create_deployment_with_generated_id(self):
        self.client.deployments.create = Mock()
        self.invoke('cfy deployments create -b bp1 --generate-id')
        call_args = list(self.client.deployments.create.call_args)
        try:
            UUID(call_args[0][1], version=4)
        except ValueError:
            raise Exception('The deployment was not created with a valid UUID')

    def test_create_deployment_with_id_and_generate_id_fails(self):
        self.invoke('cfy deployments create -b bp1 --generate-id dep1',
                    err_str_segment='cannot be provided',
                    exception=CloudifyCliError)

    def test_list_deployments_with_search_name(self):
        search_name_pattern = 'De#pl\xf3yment 1'
        self.client.deployments.list = Mock(return_value=MockListResponse())
        self.invoke('cfy deployments list --search-name '
                    '"{0}"'.format(search_name_pattern))
        call_args = list(self.client.deployments.list.call_args)
        self.assertEqual(call_args[1].get('_search_name'), search_name_pattern)


class DeploymentModificationsTest(CliCommandTest):
    def _mock_wait_for_executions(self, value):
        patcher = patch(
            'cloudify_cli.execution_events_fetcher.wait_for_execution',
            MagicMock(return_value=PropertyMock(error=value))
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    def setUp(self):
        super(DeploymentModificationsTest, self).setUp()
        self.use_manager()
        self._deployment_modifications = [
            DeploymentModification({
                'id': '0229a7d4-0bef-4d95-910d-a341663172e1',
                'deployment_id': 'dep1',
                'context': {
                    'workflow_id': 'scale',
                    'execution_id': '842686d6-e960-48a6-95b5-250fc26a7ed4',
                },
                'status': 'finished',
                'tenant_name': 'default_tenant',
                'created_at': datetime.datetime(2019, 8, 27, 16, 5, 24),
                'visibility': 'tenant'
            }),
            DeploymentModification({
                'id': 'e8962cbd-6645-4c60-9d6d-ee3215b39808',
                'deployment_id': 'dep1',
                'context': {
                    'workflow_id': 'scale',
                    'execution_id': 'c6bfc3de-ca19-4335-be77-b12edccba582',
                },
                'status': 'started',
                'tenant_name': 'default_tenant',
                'created_at': datetime.datetime(2019, 8, 27, 16, 35, 24),
                'visibility': 'tenant'
            }),
        ]

    def test_deployment_modifications_list(self):
        self.client.deployment_modifications.list = Mock(
            return_value=ListResponse(
                items=self._deployment_modifications,
                metadata=Metadata({'pagination': {'total': 2}})
            )
        )
        dps = self.invoke('cfy deployments modifications list dep1')
        assert dps.logs == """Listing modifications of the deployment dep1...
Showing 2 of 2 deployment modifications"""
        output_lines = dps.output.split('\n')
        deployment_modification_found = 0
        for line in output_lines:
            if '0229a7d4-0bef-4d95-910d-a341663172e1' in line:
                deployment_modification_found += 1
                assert 'scale' in line
                assert '842686d6-e960-48a6-95b5-250fc26a7ed4' in line
                assert 'finished' in line
                assert 'default_tenant' in line
                assert '2019-08-27 16:05:24' in line
            if 'e8962cbd-6645-4c60-9d6d-ee3215b39808' in line:
                deployment_modification_found += 1
                assert 'scale' in line
                assert 'c6bfc3de-ca19-4335-be77-b12edccba582' in line
                assert 'started' in line
                assert 'default_tenant' in line
                assert '2019-08-27 16:35:24' in line
        assert deployment_modification_found == 2

    def test_deployment_modifications_no_context(self):
        deployment_modification = self._deployment_modifications[0]
        deployment_modification.pop('context')
        self.client.deployment_modifications.list = Mock(
            return_value=ListResponse(
                items=[deployment_modification],
                metadata=Metadata({'pagination': {'total': 1}})
            )
        )
        dps = self.invoke('cfy deployments modifications list dep1')
        assert dps.logs == """Listing modifications of the deployment dep1...
Showing 1 of 1 deployment modifications"""
        output_lines = dps.output.split('\n')
        deployment_modification_found = 0
        for line in output_lines:
            if '0229a7d4-0bef-4d95-910d-a341663172e1' in line:
                deployment_modification_found += 1
                assert 'N/A' in line
                assert 'finished' in line
                assert 'default_tenant' in line
                assert '2019-08-27 16:05:24' in line
        assert deployment_modification_found == 1

    def test_deployment_modifications_get(self):
        deployment_modification = self._deployment_modifications[0]
        deployment_modification.update(
            {
                'modified_nodes': {
                    'node1': []
                },
                'node_instances': {
                    'before_modification': [
                        {'id': 'node1_18fda8', 'node_id': 'node1'},
                        {'id': 'node2_z3t4uc', 'node_id': 'node2'},
                    ],
                    'added_and_related': [
                        {'id': 'node2_z3t4uc', 'node_id': 'node2'},
                        {'id': 'node1_olbbe0', 'node_id': 'node1',
                         'modification': 'added'},
                    ]
                },
            }
        )
        self.client.deployment_modifications.get = Mock(
            return_value=deployment_modification
        )
        dps = self.invoke('cfy deployments modifications get '
                          '0229a7d4-0bef-4d95-910d-a341663172e1')
        assert dps.logs == 'Retrieving deployment modification ' \
                           '0229a7d4-0bef-4d95-910d-a341663172e1...'
        output_lines = dps.output.split('\n')
        assert 'Modified nodes:' in output_lines
        assert 'Node instances before modifications:' in output_lines
        assert 'Added node instances:' in output_lines
        assert 'Node instances before rollback:' not in output_lines
        assert 'Removed node instances:' not in output_lines
        added_title_idx = output_lines.index('Added node instances:')
        assert 'node1_olbbe0 (node1)' in output_lines[added_title_idx + 1]


class DeploymentScheduleTest(CliCommandTest):
    def setUp(self):
        super(DeploymentScheduleTest, self).setUp()
        self.use_manager()

    def test_deployment_schedule_create(self):
        self.client.execution_schedules.create = MagicMock(
            return_value=execution_schedules.ExecutionSchedule({}))
        self.invoke('cfy deployments schedule create dep1 backup '
                    '-s "12:00" -u "+1w +1d" -r 2d --tz EST')

        now = datetime.datetime.utcnow()
        expected_since = now.replace(
            hour=17, minute=0, second=0, microsecond=0)
        expected_until = now.replace(second=0, microsecond=0) + \
            datetime.timedelta(days=8)

        call_args = list(self.client.execution_schedules.create.call_args)
        assert call_args[0][0] == 'backup'
        assert call_args[1]['since'] == expected_since
        assert call_args[1]['until'] == expected_until
        assert call_args[1]['recurrence'] == '2d'

    def test_deployment_schedule_create_with_schedule_name(self):
        self.client.execution_schedules.create = MagicMock(
            return_value=execution_schedules.ExecutionSchedule({}))
        self.invoke('cfy deployments schedule create dep1 backup '
                    '-n back_me_up -s "1905-6-13 12:00" --tz GMT')

        expected_since = \
            datetime.datetime.strptime('1905-6-13 12:00', '%Y-%m-%d %H:%M')

        call_args = list(self.client.execution_schedules.create.call_args)
        assert call_args[0][0] == 'back_me_up'
        assert call_args[1]['since'] == expected_since
        assert not call_args[1]['recurrence']
        assert not call_args[1]['until']

    def test_deployment_schedule_create_missing_since(self):
        outcome = self.invoke(
            'cfy deployments schedule create dep1 backup',
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        self.assertIn("Missing option '-s' / '--since'", outcome.output)

    def test_deployment_schedule_create_missing_workflow_id(self):
        outcome = self.invoke(
            'cfy deployments schedule create dep1 -s "12:33"',
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        self.assertIn("Missing argument 'WORKFLOW_ID'", outcome.output)

    def test_deployment_schedule_create_bad_time_expressions(self):
        self.client.execution_schedules.create = MagicMock(
            return_value=execution_schedules.ExecutionSchedule({}))
        command = 'cfy deployments schedule create dep1 install -s "{}"'
        error_msg = '{} is not a legal time format. accepted formats are ' \
                    'YYYY-MM-DD HH:MM | HH:MM'

        illegal_time_formats = ['blah', '15:33:18', '99:99',
                                '2000/1/1 09:17', '-1 min']
        for time_format in illegal_time_formats:
            self.invoke(
                command.format(time_format),
                err_str_segment=error_msg.format(time_format),
                exception=NonRecoverableError)

        illegal_time_deltas = ['+10 dobosh', '+rez']
        for delta in illegal_time_deltas:
            self.invoke(
                command.format(delta),
                err_str_segment='{} is not a legal time delta'.format(
                    delta.strip('+')),
                exception=NonRecoverableError)

    def test_deployment_schedule_create_bad_timezone(self):
        self.invoke('cfy deployments schedule create dep1 install '
                    '-s "7:15" --tz Mars/SpaceX',
                    err_str_segment='Mars/SpaceX is not a recognized timezone',
                    exception=NonRecoverableError)

    def test_deployment_schedule_create_months_delta(self):
        self.client.execution_schedules.create = MagicMock(
            return_value=execution_schedules.ExecutionSchedule({}))
        self.invoke('cfy deployments schedule create dep backup -s "+13mo"')
        call_args = list(self.client.execution_schedules.create.call_args)

        now = datetime.datetime.utcnow()
        current_month = now.month
        current_year = now.year
        current_day = now.day
        expected_month = 1 if current_month == 12 else current_month + 1
        expected_year = current_year + (2 if current_month == 12 else 1)
        expected_since = now.replace(
            second=0, microsecond=0,
            year=expected_year, month=expected_month, day=1)
        expected_since += datetime.timedelta(days=current_day - 1)
        assert call_args[1]['since'] == expected_since

    def test_deployment_schedule_create_years_delta(self):
        self.client.execution_schedules.create = MagicMock(
            return_value=execution_schedules.ExecutionSchedule({}))
        self.invoke('cfy deployments schedule create dep backup -s "+2y"')
        call_args = list(self.client.execution_schedules.create.call_args)
        now = datetime.datetime.utcnow()
        expected_since = now.replace(second=0, microsecond=0, year=now.year+2)
        assert call_args[1]['since'] == expected_since

    def test_deployment_schedule_create_hours_minutes_delta(self):
        self.client.execution_schedules.create = MagicMock(
            return_value=execution_schedules.ExecutionSchedule({}))
        self.invoke('cfy deployments schedule create dep backup '
                    '-s "+25 hours+119min"')
        call_args = list(self.client.execution_schedules.create.call_args)
        expected_since = \
            (datetime.datetime.utcnow().replace(second=0, microsecond=0) +
             datetime.timedelta(days=1, hours=2, minutes=59))
        assert call_args[1]['since'] == expected_since

    def test_deployment_schedule_update(self):
        self.client.execution_schedules.update = MagicMock(
            return_value=execution_schedules.ExecutionSchedule({}))
        self.invoke('cfy deployments schedule update dep sched-1 -r "3 weeks" '
                    '-u "22:00" --tz "Asia/Shanghai"')
        expected_until = datetime.datetime.utcnow().replace(
            hour=14, minute=0, second=0, microsecond=0)
        call_args = list(self.client.execution_schedules.update.call_args)
        assert call_args[0][0] == 'sched-1'
        assert call_args[1]['recurrence'] == '3 weeks'
        assert call_args[1]['until'] == expected_until

    def test_deployment_schedule_enable(self):
        mock_schedule = MagicMock()
        mock_schedule.enabled = False
        self.client.execution_schedules.get = MagicMock(
            return_value=mock_schedule)
        self.client.execution_schedules.update = MagicMock(
            return_value=execution_schedules.ExecutionSchedule({}))
        self.invoke('cfy deployments schedule enable dep sched-1')
        call_args = list(self.client.execution_schedules.update.call_args)
        assert call_args[1]['enabled']

    def test_deployment_schedule_enable_already_enabled(self):
        mock_schedule = MagicMock()
        mock_schedule.enabled = True
        self.client.execution_schedules.get = MagicMock(
            return_value=mock_schedule)
        self.invoke(
            'cfy deployments schedule enable dep sched-1',
            err_str_segment='Schedule `sched-1` on deployment `dep` is '
                            'already enabled',
            exception=CloudifyCliError)

    def test_deployment_schedule_disable(self):
        mock_schedule = MagicMock()
        mock_schedule.enabled = True
        self.client.execution_schedules.get = MagicMock(
            return_value=mock_schedule)
        self.client.execution_schedules.update = MagicMock(
            return_value=execution_schedules.ExecutionSchedule({}))
        self.invoke('cfy deployments schedule disable dep sched-1')
        call_args = list(self.client.execution_schedules.update.call_args)
        assert not call_args[1]['enabled']

    def test_deployment_schedule_disable_already_disabled(self):
        mock_schedule = MagicMock()
        mock_schedule.enabled = False
        self.client.execution_schedules.get = MagicMock(
            return_value=mock_schedule)
        self.invoke(
            'cfy deployments schedule disable dep sched-1',
            err_str_segment='Schedule `sched-1` on deployment `dep` is '
                            'already disabled',
            exception=CloudifyCliError)

    def test_deployment_schedule_delete(self):
        self.client.execution_schedules.delete = MagicMock(
            return_value=execution_schedules.ExecutionSchedule({}))
        self.invoke('cfy deployments schedule delete dep sched-1')

    def test_deployment_schedule_list(self):
        self.client.execution_schedules.list = \
            self._get_deployment_schedules_list()
        output = json.loads(
            self.invoke('cfy deployments schedule list --json').output)
        assert len(output) == 3

    def test_deployment_schedule_list_filter_since(self):
        self.client.execution_schedules.list = \
            self._get_deployment_schedules_list()
        # jan1 will be excluded: has no occurrences at/after Jan 2nd
        output = json.loads(
            self.invoke('cfy deployments schedule list -s "1900-1-2 0:00" '
                        '--tz GMT --json').output)
        assert len(output) == 2

    def test_deployment_schedule_list_filter_until(self):
        self.client.execution_schedules.list = \
            self._get_deployment_schedules_list()
        # jan2_jan3 will be excluded: has no occurrences before Jan 2nd
        output = json.loads(
            self.invoke('cfy deployments schedule list -u "1900-1-2 0:00" '
                        '--tz GMT --json').output)
        assert len(output) == 2

    @staticmethod
    def _get_deployment_schedules_list():
        schedules = [
            {
                'id': 'jan1_jan2',
                'deployment_id': 'dep1',
                'all_next_occurrences': ['1900-1-1 12:00:00',
                                         '1900-1-2 12:00:00'],
            },
            {
                'id': 'jan2_jan3',
                'deployment_id': 'dep1',
                'all_next_occurrences': ['1900-1-2 12:00:00',
                                         '1900-1-3 12:00:00'],
            },
            {
                'id': 'jan1',
                'deployment_id': 'dep2',
                'all_next_occurrences': ['1900-1-1 12:00:00'],
            }
        ]
        return MagicMock(return_value=MockListResponse(items=schedules))

    @staticmethod
    def _get_deployment_schedule_detailed(enabled=True):
        return MagicMock(
            return_value=execution_schedules.ExecutionSchedule({
                'id': 'sched_get',
                'deployment_id': 'dep3',
                'rule': {},
                'execution_arguments': {},
                'parameters': {},
                'enabled': enabled,
                'all_next_occurrences': ['1900-1-1 12:00:00',
                                         '1900-1-2 12:00:00',
                                         '1900-1-3 12:00:00']

            }))

    def test_deployment_schedule_get(self):
        self.client.execution_schedules.get = \
            self._get_deployment_schedule_detailed()
        output = self.invoke('cfy deployments schedule get dep sched_get '
                             '--preview 2')
        self.assertIn('Computed 3 upcoming occurrences. Listing first 2:',
                      output.output)
        self.assertIn('| sched_get |      dep3     |', output.output)
        self.assertIn('1     1900-1-1 12:00:00', output.output)
        self.assertIn('2     1900-1-2 12:00:00', output.output)

    def test_deployment_schedule_get_no_preview(self):
        self.client.execution_schedules.get = \
            self._get_deployment_schedule_detailed()
        output = self.invoke('cfy deployments schedule get dep sched_get')
        self.assertIn('| sched_get |      dep3     |', output.output)
        self.assertNotIn('Computed 3 upcoming occurrences', output.output)

    def test_deployment_schedule_get_no_preview_because_disabled(self):
        self.client.execution_schedules.get = \
            self._get_deployment_schedule_detailed(enabled=False)
        output = self.invoke(
            'cfy deployments schedule get dep sched_get --preview 1',
            err_str_segment='Deployment schedule sched_get is disabled, '
                            'no upcoming occurrences',
            exception=CloudifyCliError)
        self.assertIn('| sched_get |      dep3     |', output.output)
