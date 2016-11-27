import datetime

from mock import patch, MagicMock, PropertyMock

from cloudify_rest_client import deployments, executions, blueprints
from cloudify_rest_client.exceptions import CloudifyClientError, \
    MissingRequiredDeploymentInputError, UnknownDeploymentInputError


from ... import exceptions
from .mocks import MockListResponse
from .test_base import CliCommandTest
from .constants import BLUEPRINTS_DIR, SAMPLE_BLUEPRINT_PATH, \
    SAMPLE_ARCHIVE_PATH, SAMPLE_INPUTS_PATH


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
            '{0} -n my-blueprint.yaml my_deployment'
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
        outcome = self.invoke(
            'cfy deployments update my_deployment'.format(
                BLUEPRINTS_DIR),
            err_str_segment='2',  # Exit code
            exception=SystemExit)

        self.assertIn(
            'Missing option "-p" / "--blueprint-path"',
            outcome.output
        )


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

    def test_deployments_delete(self):
        self.client.deployments.delete = MagicMock()
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
            'message': {
                'text': 'workflow execution succeeded'
            },
            'context': {
                'deployment_id': 'deployment-id'
            }
        }
        get_events_response = MockListResponse([success_event], 1)

        self.client.executions.start = MagicMock(
            return_value=execute_response)
        self.client.executions.get = MagicMock(
            return_value=get_execution_response)
        self.client.events.list = MagicMock(return_value=get_events_response)
        self.invoke('cfy executions start install -d a-deployment-id')

    def test_deployments_list_all(self):
        self.client.deployments.list = MagicMock(return_value=[])
        self.invoke('cfy deployments list')

    def test_deployments_list_of_blueprint(self):
        deps = [
            {
                'blueprint_id': 'b1_blueprint',
                'created_at': 'now',
                'updated_at': 'now',
                'id': 'id',
                'permission': 'creator',
                'tenant_name': 'default_tenant'
            },
            {
                'blueprint_id': 'b1_blueprint',
                'created_at': 'now',
                'updated_at': 'now',
                'id': 'id',
                'permission': 'creator',
                'tenant_name': 'default_tenant'
            },
            {
                'blueprint_id': 'b2_blueprint',
                'created_at': 'now',
                'updated_at': 'now',
                'id': 'id',
                'permission': 'creator',
                'tenant_name': 'default_tenant'
            }
        ]

        self.client.deployments.list = MagicMock(return_value=deps)
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

    def test_missing_required_inputs(self):
        self._test_deployment_inputs(
            MissingRequiredDeploymentInputError,
            'Unable to create deployment. Not all '
            'required inputs have been specified...'
        )

    def test_invalid_input(self):
        self._test_deployment_inputs(
            UnknownDeploymentInputError,
            'Unable to create deployment, an unknown input was specified...'
        )

    def _test_deployment_inputs(self, exception_type, error_msg):
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

        outcome = self.invoke(
            'cfy deployments create deployment -b a-blueprint-id',
            err_str_segment='no inputs'
        )
        outcome = [o.strip() for o in outcome.logs.split('\n')]

        expected_outputs = [
            'Deployment inputs:',
            'input1:',
            'description: val1',
            'input2:',
            'description: val2',
        ]

        for output in expected_outputs:
            self.assertIn(output, outcome)

        self.assertIn(error_msg, outcome)
