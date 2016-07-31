########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import json
import time
import yaml
import shutil
import datetime
import platform
import tempfile
from distutils import spawn
from StringIO import StringIO
from collections import namedtuple

import nose
import unittest
from mock import MagicMock, patch, PropertyMock, call

from cloudify_cli.bootstrap import bootstrap
from cloudify_cli.commands import executions
from cloudify_cli.commands.ssh import _validate_env
from cloudify_cli import env, common, utils, exceptions
from cloudify.exceptions import CommandExecutionException

from dsl_parser.constants import HOST_TYPE
from dsl_parser import exceptions as parser_exceptions
from cloudify_rest_client import CloudifyClient, deployments, \
    executions, plugins, snapshots
from cloudify_rest_client.exceptions import CloudifyClientError, \
    DeploymentEnvironmentCreationPendingError, \
    DeploymentEnvironmentCreationInProgressError, UserUnauthorizedError

from cloudify_cli.constants import DEFAULT_BLUEPRINT_FILE_NAME, \
    DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND, DEFAULT_TIMEOUT, \
    DEFAULT_BLUEPRINT_PATH, DEFAULT_INSTALL_WORKFLOW, DEFAULT_PARAMETERS, \
    DEFAULT_TASK_THREAD_POOL_SIZE, DEFAULT_UNINSTALL_WORKFLOW, API_VERSION

from .constants import SAMPLE_BLUEPRINT_PATH, \
    SAMPLE_ARCHIVE_PATH, STUB_BLUEPRINT_ID, STUB_DIRECTORY_NAME, \
    SAMPLE_ARCHIVE_URL, STUB_BLUEPRINT_FILENAME, SAMPLE_INPUTS_PATH, \
    STUB_DEPLOYMENT_ID, STUB_PARAMETERS, STUB_ARCHIVE_LOCATION, STUB_WORKFLOW, \
    STUB_TIMEOUT, SSL_PORT, TEST_WORK_DIR, BLUEPRINTS_DIR, SNAPSHOTS_DIR

from .mocks import mock_log_message_prefix, \
    mock_activated_status, mock_is_timeout, node_instance_get_mock, \
    node_get_mock, _make_tarfile, MockListResponse, execution_mock

from .. import cfy
from ... import execution_events_fetcher
from .test_base import CliCommandTest, BaseUpgradeTest


class BlueprintsTest(CliCommandTest):

    def setUp(self):
        super(BlueprintsTest, self).setUp()
        self.use_manager()

    def test_blueprints_list(self):
        self.client.blueprints.list = MagicMock(return_value=[])
        self.invoke('blueprints list')

    def test_blueprints_delete(self):
        self.client.blueprints.delete = MagicMock()
        self.invoke('blueprints delete a-blueprint-id')

    @patch('cloudify_cli.utils.table', autospec=True)
    @patch('cloudify_cli.common.print_table', autospec=True)
    def test_blueprints_get(self, *args):
        self.client.blueprints.get = MagicMock()
        self.client.deployments.list = MagicMock()
        self.invoke('blueprints get a-blueprint-id')

    def test_blueprints_upload(self):
        self.client.blueprints.upload = MagicMock()
        self.invoke(
            'blueprints upload {0}/helloworld/blueprint.yaml'.format(
                BLUEPRINTS_DIR))

    def test_blueprints_upload_invalid(self):
        self.client.blueprints.upload = MagicMock()
        self.invoke(
            'cfy blueprints upload {0}/bad_blueprint/blueprint.yaml '
            '-b my_blueprint_id'.format(BLUEPRINTS_DIR))

    def test_blueprints_upload_invalid_validate(self):
        self.client.blueprints.upload = MagicMock()
        self.invoke(
            'cfy blueprints upload {0}/bad_blueprint/blueprint.yaml '
            '-b my_blueprint_id --validate'.format(BLUEPRINTS_DIR),
            err_str_segment='Failed to validate blueprint',
            should_fail=True)

    def test_blueprints_publish_archive(self):
        self.client.blueprints.upload = MagicMock()
        self.invoke(
            'cfy blueprints upload {0}/helloworld.zip '
            '-b my_blueprint_id --blueprint-filename blueprint.yaml'
            .format(BLUEPRINTS_DIR))

    def test_blueprints_publish_unsupported_archive_type(self):
        self.client.blueprints.upload = MagicMock()
        # passing in a directory instead of a valid archive type
        self.invoke(
            'cfy blueprints upload {0}/helloworld -b my_blueprint_id'.format(
                BLUEPRINTS_DIR),
            'You must provide either a path to a local file')

    def test_blueprints_publish_archive_bad_file_path(self):
        self.client.blueprints.upload = MagicMock()
        self.invoke(
            'cfy blueprints upload {0}/helloworld.tar.gz -n blah'
            .format(BLUEPRINTS_DIR),
            err_str_segment="You must provide either a path to a local file")

    def test_blueprints_publish_archive_no_filename(self):
        # TODO: The error message here should be different - something to
        # do with the filename provided being incorrect
        self.client.blueprints.upload = MagicMock()
        self.invoke(
            'cfy blueprints upload {0}/helloworld.tar.gz -b my_blueprint_id'
            .format(BLUEPRINTS_DIR),
            err_str_segment="You must provide either a path to a local file")

    def test_blueprint_validate(self):
        self.invoke(
            'cfy blueprints validate {0}/helloworld/blueprint.yaml'.format(
                BLUEPRINTS_DIR))

    def test_blueprint_validate_definitions_version_false(self):
        with open(env.CLOUDIFY_CONFIG_PATH) as f:
            config = yaml.safe_load(f.read())
        with open(env.CLOUDIFY_CONFIG_PATH, 'w') as f:
            config['validate_definitions_version'] = False
            f.write(yaml.safe_dump(config))
        self.invoke(
            'cfy blueprints validate '
            '{0}/local/blueprint_validate_definitions_version.yaml'
            .format(BLUEPRINTS_DIR))

    def test_validate_bad_blueprint(self):
        self.invoke(
            'cfy blueprints validate {0}/bad_blueprint/blueprint.yaml'
            .format(BLUEPRINTS_DIR),
            err_str_segment='Failed to validate blueprint')

    def test_blueprint_inputs(self):

        blueprint_id = 'a-blueprint-id'
        name = 'test_input'
        type = 'string'
        description = 'Test input.'

        blueprint = {
            'plan': {
                'inputs': {
                    name: {
                        'type': type,
                        'description': description
                        # field 'default' intentionally omitted
                    }
                }
            }
        }

        assert_equal = self.assertEqual

        class RestClientMock(object):
            class BlueprintsClientMock(object):
                def __init__(self, blueprint_id, blueprint):
                    self.blueprint_id = blueprint_id
                    self.blueprint = blueprint

                def get(self, blueprint_id):
                    assert_equal(blueprint_id, self.blueprint_id)
                    return self.blueprint

            def __init__(self, blueprint_id, blueprint):
                self.blueprints = self.BlueprintsClientMock(blueprint_id,
                                                            blueprint)

        def get_rest_client_mock(*args, **kwargs):
            return RestClientMock(blueprint_id, blueprint)

        def table_mock(fields, data, *args, **kwargs):
            self.assertEqual(len(data), 1)
            input = data[0]
            self.assertIn('name', input)
            self.assertIn('type', input)
            self.assertIn('default', input)
            self.assertIn('description', input)

            self.assertEqual(input['name'], name)
            self.assertEqual(input['type'], type)
            self.assertEqual(input['default'], '-')
            self.assertEqual(input['description'], description)

        with patch('cloudify_cli.env.get_rest_client',
                   get_rest_client_mock),\
                patch('cloudify_cli.utils.table', table_mock):
            self.invoke('cfy blueprints inputs {0}'.format(blueprint_id))


# TODO: Test outputs
# TODO: Test profiles
class BootstrapTest(CliCommandTest):

    def test_bootstrap_install_plugins(self):
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint_with_plugins')
        command = 'cfy bootstrap --install-plugins {0}'.format(blueprint_path)

        with patch('cloudify_cli.bootstrap.bootstrap.'
                        'validate_manager_deployment_size'):
            self.assert_method_called(
                command=command,
                module=common,
                function_name='install_blueprint_plugins',
                kwargs=dict(blueprint_path=blueprint_path))

    def test_bootstrap_no_validations_install_plugins(self):
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint_with_plugins')
        command = ('cfy bootstrap --skip-validations '
                   '--install-plugins {0}'.format(blueprint_path))

        self.assert_method_called(
            command=command,
            module=common,
            function_name='install_blueprint_plugins',
            kwargs=dict(blueprint_path=blueprint_path)
        )

    def test_bootstrap_no_validations_add_ignore_bootstrap_validations(self):

        blueprint_path = '{0}/helloworld/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')
        command = ('cfy bootstrap --skip-validations {0} '
                   '-i "some_input=some_value"'.format(blueprint_path))

        self.assert_method_called(
            command=command,
            module=common,
            function_name='add_ignore_bootstrap_validations_input',
            args=[{u'some_input': u'some_value'}]
        )

    def test_viable_ignore_bootstrap_validations_input(self):
        inputs = dict()
        common.add_ignore_bootstrap_validations_input(inputs)
        self.assertTrue(inputs['ignore_bootstrap_validations'])

    def test_bootstrap_missing_plugin(self):

        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint_with_plugins')
        command = 'cfy bootstrap {0}'.format(blueprint_path)

        with patch('cloudify_cli.bootstrap.bootstrap.'
                        'validate_manager_deployment_size'):
            self.invoke(
                command=command,
                err_str_segment='No module named tasks',
                exception=ImportError
                # TODO: put back
                # possible_solutions=[
                #     "Run 'cfy local install-plugins {0}'".format(
                #         blueprint_path),
                #     "Run 'cfy bootstrap --install-plugins {0}'".format(
                #         blueprint_path)]
            )

    def test_bootstrap_no_validation_missing_plugin(self):

        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint_with_plugins')
        command = 'cfy bootstrap --skip-validations {0}'.format(
            blueprint_path)

        self.invoke(
            command=command,
            err_str_segment='No module named tasks',
            exception=ImportError
            # TODO: put back
            # possible_solutions=[
            #     "Run 'cfy local install-plugins -p {0}'"
            #     .format(blueprint_path),
            #     "Run 'cfy bootstrap --install-plugins -p {0}'"
            #     .format(blueprint_path)
            # ]
        )

    def test_bootstrap_validate_manager_deployment_size(self):
        # verifying validation over manager deployment size is called before
        # calling bootstrap
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')
        command = 'cfy bootstrap --validate-only {0}'.format(blueprint_path)

        self.assert_method_called(
            command=command,
            module=bootstrap,
            function_name='validate_manager_deployment_size',
            kwargs=dict(blueprint_path=blueprint_path))

    def test_bootstrap_skip_validate_manager_deployment_size(self):
        # verifying validation over manager deployment size is not called
        # when the "--skip-validation" flag is used
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')
        command = ('cfy bootstrap --validate-only --skip-validations '
                   '{0}'.format(blueprint_path))

        self.assert_method_not_called(
            command=command,
            module=bootstrap,
            function_name='validate_manager_deployment_size')


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
            'cfy deployments create -b a-blueprint-id -d deployment')

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

        deployments = [
            {
                'blueprint_id': 'b1_blueprint',
                'created_at': 'now',
                'updated_at': 'now',
                'id': 'id'
            },
            {
                'blueprint_id': 'b1_blueprint',
                'created_at': 'now',
                'updated_at': 'now',
                'id': 'id'
            },
            {
                'blueprint_id': 'b2_blueprint',
                'created_at': 'now',
                'updated_at': 'now',
                'id': 'id'
            }
        ]

        self.client.deployments.list = MagicMock(return_value=deployments)
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


class EventsTest(CliCommandTest):

    def setUp(self):
        super(EventsTest, self).setUp()
        self.events = []
        self.use_manager()
        # Execution will terminate after 10 seconds
        self.execution_start_time = time.time()
        self.execution_termination_time = self.execution_start_time + 10
        self.events = self._generate_events(self.execution_start_time,
                                            self.execution_termination_time)
        self.executions_status = executions.Execution.STARTED

    def _generate_events(self, start_time, end_time):
        events = []
        event_time = start_time
        event_count = 0

        while event_time < end_time:
            deployment_id = 'deployment_id_{0}'.format(event_count % 2)  # 0/1
            event = {'event_name': 'test_event_{0}'.format(event_time),
                     'deployment_id': deployment_id}
            events.append((event_time, event))
            event_time += 0.3
            event_count += 1

        success_event = {
            'event_name': 'test_event_{0}'.format(end_time),
            'event_type': 'workflow_succeeded',
            'deployment_id': 'deployment_id_{0}'.format(event_count % 2)
        }
        events.append((end_time, success_event))
        return events

    def _get_events_before(self, end_time):
        return [event for event_time, event in self.events
                if event_time < end_time]

    def _mock_executions_get(self, execution_id):
        self.update_execution_status()
        if self.executions_status != executions.Execution.TERMINATED:
            execution = executions.Execution({'id': 'execution_id',
                                   'status': executions.Execution.STARTED})
        else:
            execution = executions.Execution({'id': 'execution_id',
                                   'status': executions.Execution.TERMINATED})

        return execution

    def _mock_deployments_get(self, deployment_id):
        return deployments.Deployment({'id': deployment_id})

    def _mock_events_list(self, include_logs=False, message=None,
                           from_datetime=None, to_datetime=None, _include=None,
                           sort='@timestamp', **kwargs):
        from_event = kwargs.get('_offset', 0)
        batch_size = kwargs.get('_size', 100)
        events = self._get_events_before(time.time())
        return MockListResponse(
            events[from_event:from_event+batch_size], len(events))

    def _mock_events_delete(self, deployment_id, **kwargs):
        events_before = len(self.events)
        self.events = [event for event in self.events if
                       event[1]['deployment_id'] != deployment_id]
        events_after = len(self.events)

        class DeletedEvents(object):
            def __init__(self, deleted_events_count):
                self.items = [deleted_events_count]

        return DeletedEvents(events_before - events_after)

    def update_execution_status(self):
        """Sets the execution status to TERMINATED when
        reaching execution_termination_time
        """
        if time.time() > self.execution_termination_time:
            self.executions_status = executions.Execution.TERMINATED

    def _assert_events_displayed(self, events, output):
        expected_event_logs = []
        for event in events:
            expected_event_logs.append(event['event_name'])

        missing_events_error_message = (
            'Command output does not contain all expected values.'
            '\nOutput: \n{0}\n'
            '\nExpected: \n{1}\n'
            .format(output, '\n'.join(expected_event_logs)))

        self.assertTrue(
            all(event_log in output for event_log in expected_event_logs),
            missing_events_error_message)

    @patch('cloudify_cli.logger.logs.create_event_message_prefix',
           new=mock_log_message_prefix)
    def test_events_tail(self):
        self.client.executions.get = self._mock_executions_get
        self.client.events.list = self._mock_events_list

        # Since we're tailing stdout here, we have to patch it.
        # Can't just read the output once.
        stdout = StringIO()
        with patch('sys.stdout', stdout):
            self.invoke('cfy events list execution-id --tail')
        output = stdout.getvalue()
        expected_events = self._get_events_before(
            self.execution_termination_time)

        self._assert_events_displayed(expected_events, output)

    @patch('cloudify_cli.logger.logs.create_event_message_prefix',
           new=mock_log_message_prefix)
    def test_events(self):
        output = self._test_events()
        expected_events = self._get_events_before(time.time())
        self._assert_events_displayed(expected_events, output)

    def test_event_json(self):
        output = self._test_events(flag='--json')
        expected_events = self._get_events_before(time.time())
        self._assert_events_displayed(expected_events, output)
        for event in expected_events:
            self.assertIn(json.dumps(event), output)

    def _test_events(self, flag=''):
        self.client.executions.get = self._mock_executions_get
        self.client.events.list = self._mock_events_list
        outcome = self.invoke('cfy events list execution-id {0}'.format(
            flag))
        return outcome.output if flag else outcome.logs

    def _patch_clients_for_deletion(self):
        self.client.deployments.get = self._mock_deployments_get
        self.client.events.delete = self._mock_events_delete

    def test_delete_events(self):
        self._patch_clients_for_deletion()
        self.assertEqual(len(self.events), 35)

        outcome = self.invoke('cfy events delete deployment_id_1')
        self.assertEqual(outcome.logs.split('\n')[-1], 'Deleted 17 events')
        self.assertEqual(len(self.events), 18)

        outcome = self.invoke('cfy events delete deployment_id_0')
        self.assertEqual(outcome.logs.split('\n')[-1], 'Deleted 18 events')
        self.assertEqual(len(self.events), 0)

        outcome = self.invoke('cfy events delete deployment_id_0')
        self.assertEqual(outcome.logs.split('\n')[-1], 'No events to delete')
        self.assertEqual(len(self.events), 0)


class ExecutionsTest(CliCommandTest):

    def setUp(self):
        super(ExecutionsTest, self).setUp()
        self.use_manager()

    def test_executions_get(self):
        execution = execution_mock('terminated')
        self.client.executions.get = MagicMock(return_value=execution)
        self.invoke('cfy executions get execution-id')

    def test_executions_list(self):
        self.client.executions.list = MagicMock(return_value=[])
        self.invoke('cfy executions list -d deployment-id')

    def test_executions_cancel(self):
        self.client.executions.cancel = MagicMock()
        self.invoke('cfy executions cancel e_id')

    @patch('cloudify_cli.logger.get_events_logger')
    def test_executions_start_json(self, get_events_logger_mock):
        execution = execution_mock('started')
        original = self.client.executions.start
        try:
            self.client.executions.start = MagicMock(return_value=execution)
            with patch('cloudify_cli.execution_events_fetcher.wait_for_execution',
                       return_value=execution):
                self.invoke('cfy executions start mock_wf -d dep --json')
            get_events_logger_mock.assert_called_with(True)
        finally:
            self.client.executions.start = original

    def test_executions_start_dep_env_pending(self):
        self._test_executions_start_dep_env(
            ex=DeploymentEnvironmentCreationPendingError('m'))

    def test_executions_start_dep_env_in_progress(self):
        self._test_executions_start_dep_env(
            ex=DeploymentEnvironmentCreationInProgressError('m'))

    def test_executions_start_dep_other_ex_sanity(self):
        try:
            self._test_executions_start_dep_env(ex=RuntimeError)
        except cfy.ClickInvocationException, e:
            self.assertEqual(str(RuntimeError), e.exception)

    def _test_executions_start_dep_env(self, ex):
        start_mock = MagicMock(side_effect=[ex, execution_mock('started')])
        self.client.executions.start = start_mock

        list_mock = MagicMock(return_value=[
            execution_mock('terminated', 'create_deployment_environment')])
        self.client.executions.list = list_mock

        wait_for_mock = MagicMock(return_value=execution_mock('terminated'))
        original_wait_for = execution_events_fetcher.wait_for_execution
        try:
            execution_events_fetcher.wait_for_execution = wait_for_mock
            self.invoke('cfy executions start mock_wf -d dep')
            self.assertEqual(wait_for_mock.mock_calls[0][1][1].workflow_id,
                             'create_deployment_environment')
            self.assertEqual(wait_for_mock.mock_calls[1][1][1].workflow_id,
                             'mock_wf')
        finally:
            execution_events_fetcher.wait_for_execution = original_wait_for


class GroupsTest(CliCommandTest):

    def setUp(self):
        super(GroupsTest, self).setUp()
        self.use_manager()

    def test_groups_list(self):
        deployment = deployments.Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'groups': {
                'group1': {
                    'members': ['node1', 'node2'],
                    'policies': {
                        'policy1': {
                            'type': 'cloudify.policies.threshold'
                        }
                    }
                },
                'group2': {
                    'members': ['node1', 'node2'],
                    'policies': {
                        'policy2': {
                            'type': 'cloudify.policies.host_failure'
                        }
                    }
                },
                'group3': {
                    'members': ['group1', 'node3']
                }
            },
            'scaling_groups': {
                'group2': {
                    'members': ['node1', 'node2'],
                    'properties': {

                    }
                },
                'group3': {
                    'members': ['group1', 'node3'],
                    'properties': {

                    }
                }
            }
        })
        self.client.deployments.get = MagicMock(return_value=deployment)
        self.invoke('cfy groups list -d a-deployment-id')

    def test_groups_sort_list(self):
        deployment = deployments.Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'groups': {
                'group2': {
                    'members': ['node1', 'node2'],
                    'policies': {
                        'policy1': {
                            'type': 'cloudify.policies.threshold'
                        }
                    }
                },
                'group3': {
                    'members': ['node1', 'node2'],
                    'policies': {
                        'policy2': {
                            'type': 'cloudify.policies.host_failure'
                        }
                    }
                },
                'group1': {
                    'members': ['node2', 'node3']
                }
            }
        })
        self.client.deployments.get = MagicMock(return_value=deployment)
        output = self.invoke('cfy groups list -d a-deployment-id').logs
        first = output.find('group1')
        second = output.find('group2')
        third = output.find('group3')
        self.assertTrue(0 < first < second < third)

    def test_groups_list_nonexistent_deployment(self):
        expected_message = ('Deployment nonexistent-dep not found')
        error = CloudifyClientError('')
        error.status_code = 404
        self.client.deployments.get = MagicMock(side_effect=error)
        self.invoke("cfy groups list -d nonexistent-dep", expected_message)


class InitTest(CliCommandTest):

    def test_init_initialized_directory(self):
        self.use_manager()
        self.invoke(
            'cfy init',
            err_str_segment='Environment is already initialized')

    def test_init_overwrite(self):
        # Ensuring the init with overwrite command works
        self.invoke('cfy init -r')

    def test_init_overwrite_on_initial_init(self):
        # Simply verifying the overwrite flag doesn't break the first init
        cfy.purge_dot_cloudify()
        self.invoke('cfy init -r')

    def test_no_init(self):
        cfy.purge_dot_cloudify()
        self.invoke('cfy profiles list',
                    err_str_segment='Cloudify environment is not initalized',
                    # TODO: put back
                    # possible_solutions=[
                    #     "Run 'cfy init' in this directory"
                    # ]
                    )


# TODO: Add local tests
class InstallTest(CliCommandTest):

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.blueprints.upload')
    @patch('cloudify_cli.commands.deployments.manager_create')
    def test_use_blueprints_upload_mode(self,
                                        executions_start_mock,
                                        blueprints_upload_mock,
                                        deployments_create_mock):
        self.invoke('cfy install {0}'.format(SAMPLE_BLUEPRINT_PATH), context='manager')

        self.assertTrue(executions_start_mock.called)
        self.assertTrue(blueprints_upload_mock.called)
        self.assertTrue(deployments_create_mock.called)

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_blueprint_filename_default_value(self, blueprints_upload_mock, *_):
        install_command = \
            'cfy install --blueprint-id={1} {0}'\
            .format(SAMPLE_ARCHIVE_PATH, STUB_BLUEPRINT_ID)

        self.invoke(install_command, context='manager')
        blueprint_upload_args = blueprints_upload_mock.call_args_list[0][1]

        self.assertEqual(
            blueprint_upload_args['blueprint_filename'],
            unicode(DEFAULT_BLUEPRINT_FILE_NAME)
        )
        self.assertEqual(
            blueprint_upload_args['blueprint_id'],
            unicode(STUB_BLUEPRINT_ID)
        )

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_blueprint_path_default_value(
            self, blueprints_upload_mock,
            *_):

        install_upload_mode_command = \
            'cfy install -n {0}'.format(DEFAULT_BLUEPRINT_FILE_NAME)

        tmp_blueprint_path = os.path.join('/tmp',
                                          DEFAULT_BLUEPRINT_FILE_NAME)

        try:
            # create a tmp file representing a blueprint to upload
            open(tmp_blueprint_path, 'w+').close()

            self.invoke(install_upload_mode_command, context='manager')

            blueprint_path_argument_from_upload = \
                blueprints_upload_mock.call_args_list[0][0][0]

            # check that the blueprint path value that was assigned in `install`
            # is indeed the default blueprint file path
            self.assertEqual(blueprint_path_argument_from_upload.name,
                             tmp_blueprint_path
                             )
        finally:
            print tmp_blueprint_path
            # os.remove(tmp_blueprint_path)

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_default_blueprint_id(
            self,
            blueprints_upload_mock,
            *_):

        install_command = 'cfy install -n {0} {1}'\
            .format(DEFAULT_BLUEPRINT_FILE_NAME, SAMPLE_ARCHIVE_PATH)

        self.invoke(install_command, context='manager')

        blueprint_upload_args = blueprints_upload_mock.call_args_list[0][1]

        self.assertEqual(
            blueprint_upload_args['blueprint_filename'],
            unicode(DEFAULT_BLUEPRINT_FILE_NAME)
        )
        self.assertEqual(
            blueprint_upload_args['blueprint_id'],
            unicode(STUB_DIRECTORY_NAME)
        )

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_blueprint_id_default_publish_archive_mode_url(
            self,
            blueprints_upload_mock,
            *_):

        install_command = 'cfy install -n {0} {1}' \
            .format(DEFAULT_BLUEPRINT_FILE_NAME, SAMPLE_ARCHIVE_URL)

        self.invoke(install_command, context='manager')

        blueprint_upload_args = blueprints_upload_mock.call_args_list[0][1]

        self.assertEqual(
            blueprint_upload_args['blueprint_filename'],
            unicode(DEFAULT_BLUEPRINT_FILE_NAME)
        )
        self.assertEqual(
            blueprint_upload_args['blueprint_id'],
            u'cloudify-hello-world-example-master'
        )

    @patch('cloudify_cli.commands.blueprints.upload')
    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    def test_default_deployment_id(self, deployment_create_mock, *_):

        install_command = \
            'cfy install -n {0} {1} --inputs={2} -b {3}'\
            .format(STUB_BLUEPRINT_FILENAME, SAMPLE_BLUEPRINT_PATH,
                    SAMPLE_INPUTS_PATH, STUB_BLUEPRINT_ID)

        self.invoke(install_command, context='manager')
        deployment_create_args = deployment_create_mock.call_args_list[0][1]

        self.assertDictEqual(deployment_create_args,
                             {
                                 'blueprint_id': unicode(STUB_BLUEPRINT_ID),
                                 'deployment_id': unicode(STUB_BLUEPRINT_ID),
                                 'inputs':
                                     {'key1': 'val1', 'key2': 'val2'}}
                             )

    @patch('cloudify_cli.commands.blueprints.upload')
    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    def test_custom_deployment_id(self, deployment_create_mock, *_):

        command = 'cfy install -n {0} {1} --inputs={2} -b {3} -d {4}' \
                .format(
            STUB_BLUEPRINT_FILENAME,
            SAMPLE_BLUEPRINT_PATH,
            SAMPLE_INPUTS_PATH,
            STUB_BLUEPRINT_ID,
            STUB_DEPLOYMENT_ID
                )

        self.invoke(command, context='manager')
        deployment_create_args = deployment_create_mock.call_args_list[0][1]

        self.assertDictEqual(deployment_create_args,
                             {
                                 'blueprint_id': unicode(STUB_BLUEPRINT_ID),
                                 'deployment_id': unicode(STUB_DEPLOYMENT_ID),
                                 'inputs':
                                     {'key1': 'val1', 'key2': 'val2'}}
                             )

    @patch('cloudify_cli.commands.blueprints.upload')
    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    def test_default_inputs_file_path(self, deployment_create_mock, *_):

        # create an `inputs.yaml` file in the cwd.
        inputs_path = os.path.join(utils.get_cwd(), 'inputs.yaml')
        open(inputs_path, 'w').close()

        command = 'cfy install -n {0} {1} -b {2} -d {3}'\
            .format(
                DEFAULT_BLUEPRINT_FILE_NAME,
            SAMPLE_ARCHIVE_PATH,
            STUB_BLUEPRINT_ID,
            STUB_DEPLOYMENT_ID
            )

        self.invoke(command, context='manager')
        deployment_create_args = deployment_create_mock.call_args_list[0][1]

        self.assertDictEqual(
            deployment_create_args,
            {
                'blueprint_id': unicode(STUB_BLUEPRINT_ID),
                'deployment_id': unicode(STUB_DEPLOYMENT_ID),
                'inputs': DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND
            }
        )

    @patch('cloudify_cli.commands.blueprints.upload')
    @patch('cloudify_cli.commands.deployments.manager_create')
    @patch('cloudify_cli.commands.executions.manager_start')
    def test_default_workflow_name(self, executions_start_mock, *_):

        command = 'cfy install -n {0} {1} --inputs={2} ' \
                  '-d {3} --parameters {4}'\
            .format(
                DEFAULT_BLUEPRINT_FILE_NAME,
            SAMPLE_ARCHIVE_PATH,
            SAMPLE_INPUTS_PATH,
            STUB_DEPLOYMENT_ID,
            STUB_PARAMETERS
            )

        self.invoke(command, context='manager')
        executions_start_args = executions_start_mock.call_args_list[0][1]

        self.assertDictEqual(
            executions_start_args,
            {
                'allow_custom_parameters': False,
                'deployment_id': unicode(STUB_DEPLOYMENT_ID),
                'force': False,
                'include_logs': True,
                'json': False,
                'parameters': {u'key': u'value'},
                'workflow_id': u'install',
                'timeout': 900
            }
        )

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_blueprints_upload_custom_arguments(self,
                                                blueprints_upload_mock,
                                                *_):
        command = \
            'cfy install -p {0} -b {1} --validate'\
            .format(SAMPLE_BLUEPRINT_PATH,
                    STUB_BLUEPRINT_ID)

        self.invoke(command, context='manager')

        blueprint_path_argument_from_upload = \
            blueprints_upload_mock.call_args_list[0][0][0]
        blueprint_id_argument_from_upload = \
            blueprints_upload_mock.call_args_list[0][0][1]
        validate_argument_from_upload = \
            blueprints_upload_mock.call_args_list[0][0][2]

        self.assertEqual(
            [blueprint_path_argument_from_upload.name,
             blueprint_id_argument_from_upload,
             validate_argument_from_upload],

            [SAMPLE_BLUEPRINT_PATH,
             STUB_BLUEPRINT_ID,
             True]
        )

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    @patch('cloudify_cli.commands.blueprints.publish_archive')
    def test_blueprints_publish_archive_custom_arguments(
            self,
            blueprints_publish_archive_mock,
            *_):

        command = \
            'cfy install --archive-location {0} -n {1} -b {2}' \
            .format(STUB_ARCHIVE_LOCATION,
                    STUB_BLUEPRINT_FILENAME,
                    STUB_BLUEPRINT_ID)

        self.invoke(command, context='manager')

        blueprints_publish_archive_mock.assert_called_with(
            STUB_ARCHIVE_LOCATION,
            STUB_BLUEPRINT_FILENAME,
            STUB_BLUEPRINT_ID
        )

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.blueprints.publish_archive')
    @patch('cloudify_cli.commands.deployments.manager_create')
    def test_deployments_create_custom_arguments(self,
                                                 deployments_create_mock,
                                                 *_):
        # 'blueprints archive location mode' is used to prevent from dealing
        # with the fact that 'upload mode' needs the blueprint_path argument
        # to lead to an existing file
        command = \
            'cfy install --archive-location {0} -b {1} -d {2} -i {3}' \
            .format(SAMPLE_ARCHIVE_PATH,
                    STUB_BLUEPRINT_ID,
                    STUB_DEPLOYMENT_ID,
                    SAMPLE_INPUTS_PATH)

        self.invoke(command, context='manager')

        deployments_create_mock.assert_called_with(
            STUB_BLUEPRINT_ID,
            STUB_DEPLOYMENT_ID,
            [SAMPLE_INPUTS_PATH]
        )

    @patch('cloudify_cli.commands.deployments.manager_create')
    @patch('cloudify_cli.commands.blueprints.publish_archive')
    @patch('cloudify_cli.commands.executions.manager_start')
    def test_executions_start_custom_parameters(self,
                                                executions_start_mock,
                                                *_):
        # 'blueprints archive location mode' is used to prevent from dealing
        # with the fact that 'upload mode' needs the blueprint_path argument
        # to lead to an existing file
        command = \
            'cfy install --archive-location {0} ' \
            '-w {1} ' \
            '-d {2} ' \
            '--timeout {3} ' \
            '--parameters {4} ' \
            '--allow-custom-parameters ' \
            '--include-logs ' \
            '--json' \
            .format(SAMPLE_ARCHIVE_PATH,
                    STUB_WORKFLOW,
                    STUB_DEPLOYMENT_ID,
                    STUB_TIMEOUT,
                    STUB_PARAMETERS
                    )

        self.invoke(command, context='manager')

        executions_start_mock.assert_called_with(
            workflow_id=STUB_WORKFLOW,
            deployment_id=STUB_DEPLOYMENT_ID,
            force=False,
            timeout=STUB_TIMEOUT,
            allow_custom_parameters=True,
            include_logs=True,
            parameters=[STUB_PARAMETERS],
            json=True
        )

    @patch('cloudify_cli.commands.install')
    def test_parser_config_passes_expected_values(self, install_mock):

        install_command = 'cfy install'

        self.invoke(install_command, context='manager')

        install_command_arguments = \
            install_mock.call_args_list[0][1]

        expected_install_command_arguments = \
            {'blueprint_path': None,
             'blueprint_id': None,
             'validate_blueprint': False,
             'archive_location': None,
             'blueprint_filename': None,
             'deployment_id': None,
             'inputs': None,
             'workflow_id': None,
             'parameters': None,
             'allow_custom_parameters': False,
             'timeout': DEFAULT_TIMEOUT,
             'include_logs': False,
             'auto_generate_ids': False,
             'json': False
             }

        self.assertEqual(install_command_arguments,
                         expected_install_command_arguments)

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    @patch('cloudify_cli.commands.blueprints.publish_archive')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_mutually_exclusive_arguments(self, *_):

        path_and_filename_cmd = \
            'cfy install -p {0} -n {1}'.format(SAMPLE_BLUEPRINT_PATH,
                                               STUB_BLUEPRINT_FILENAME)

        path_and_archive_cmd = \
            'cfy install -p {0} --archive-location={1}' \
            .format(SAMPLE_BLUEPRINT_PATH,
                    STUB_ARCHIVE_LOCATION)

        path_and_filename_and_archive_cmd = \
            'cfy install -p {0} -n {1} --archive-location={2}' \
            .format(SAMPLE_BLUEPRINT_PATH,
                    STUB_BLUEPRINT_FILENAME,
                    STUB_ARCHIVE_LOCATION)

        self.assertRaises(exceptions.CloudifyCliError,
                          self.invoke,
                          path_and_filename_cmd
                          )
        self.assertRaises(exceptions.CloudifyCliError,
                          self.invoke,
                          path_and_archive_cmd
                          )
        self.assertRaises(exceptions.CloudifyCliError,
                          self.invoke,
                          path_and_filename_and_archive_cmd
                          )

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_auto_generated_ids(
            self,
            blueprints_upload_mock,
            deployments_create_mock,
            *_):

        # Not explicitly passing the blueprint and deployment IDs should
        # auto generate them - currently using the folder of the archive
        publish_archive_mode_command = \
            'cfy install {0}'.format(SAMPLE_BLUEPRINT_PATH)

        self.invoke(publish_archive_mode_command, context='manager')

        self.assertEqual(
            blueprints_upload_mock.call_args_list[0][1]['blueprint_id'],
            STUB_DIRECTORY_NAME
        )
        self.assertEqual(
            deployments_create_mock.call_args_list[0][1]['deployment_id'],
            STUB_DIRECTORY_NAME
        )

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    def test_default_blueprint_path_does_not_exist(self, *_):

        start_of_file_does_not_exist_message = \
            'Your blueprint was not found in the path:'

        self.assertRaisesRegexp(exceptions.CloudifyCliError,
                                start_of_file_does_not_exist_message,
                                self.invoke,
                                'cfy install')

        tmp_blueprint_path = os.path.join(utils.get_cwd(),
                                          DEFAULT_BLUEPRINT_FILE_NAME)

        start_of_permission_denied_message = \
            'A problem was encountered while trying to open'

        open(tmp_blueprint_path, 'w').close()
        os.chmod(tmp_blueprint_path, 0)

        self.assertRaisesRegexp(exceptions.CloudifyCliError,
                                start_of_permission_denied_message,
                                self.invoke,
                                'cfy install')


class ListSortTest(CliCommandTest):
    _resource = namedtuple('Resource', 'name,class_type,sort_order,context')

    def setUp(self):
        super(ListSortTest, self).setUp()
        self.use_manager()
        self.resources = [
            ListSortTest._resource(
                'plugins',
                self.client.plugins,
                'uploaded_at',
                None
            ),
            ListSortTest._resource(
                'deployments',
                self.client.deployments,
                'created_at',
                None
            ),
            ListSortTest._resource(
                'nodes',
                self.client.nodes,
                'deployment_id',
                None
            ),
            ListSortTest._resource(
                'node-instances',
                self.client.node_instances,
                'node_id',
                'manager'
            ),
            ListSortTest._resource(
                'blueprints',
                self.client.blueprints,
                'created_at',
                None
            ),
            ListSortTest._resource(
                'snapshots',
                self.client.snapshots,
                'created_at',
                None
            ),
            ListSortTest._resource(
                'executions',
                self.client.executions,
                'created_at',
                None
            ),
        ]

        self.count_mock_calls = 0

        self.original_lists = {}
        for r in self.resources:
            self.original_lists[r.name] = r.class_type.list

    def tearDown(self):
        for r in self.resources:
            r.class_type.list= self.original_lists[r.name]
        super(ListSortTest, self).tearDown()

    def test_list_sort(self):
        for r in self.resources:
            self._set_mock_list(r, 'order')
            self.invoke(
                'cfy {0} list --sort-by order'
                .format(r.name), context=r.context
            )
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def test_list_sort_reverse(self):
        for r in self.resources:
            self._set_mock_list(r, 'order', descending=True)
            self.invoke(
                'cfy {0} list --sort-by order --descending'
                .format(r.name), context=r.context
            )
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def test_list_sort_default(self):
        for r in self.resources:
            self._set_mock_list(r, r.sort_order)
            self.invoke('cfy {0} list'.format(r.name), context=r.context)
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def test_list_sort_default_reverse(self):
        for r in self.resources:
            self._set_mock_list(r, r.sort_order, descending=True)
            self.invoke('cfy {0} list --descending'
                        .format(r.name), context=r.context)
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def _set_mock_list(self, resource, sort, descending=False):
        def _mock_list(*_, **kwargs):
            self.count_mock_calls += 1
            self.assertEqual(sort, kwargs['sort'])
            self.assertEqual(descending, kwargs['is_descending'])
            return []

        resource.class_type.list = _mock_list


@unittest.skip('Local')
class LocalTest(CliCommandTest):

    def setUp(self):
        super(LocalTest, self).setUp()

    def test_local_init_missing_blueprint_path(self):
        self.invoke(
            'cfy local init', 2)

    def test_local_init_invalid_blueprint_path(self):
        self._assert_ex(
            'cfy local init -p idonotexist.yaml',
            'No such file or directory')

    def test_local_init(self):
        self._local_init()
        output = self.invoke('cfy local outputs')
        self.assertIn('"param": null', output)
        self.assertIn('"custom_param": null', output)
        self.assertIn('"input1": "default_input1"', output)

    def _assert_multiple_outputs(self):
        output = self.invoke('cfy local outputs')
        self.assertIn('"input1": "new_input1"', output)
        self.assertIn('"input2": "new_input2"', output)
        self.assertIn('"input3": "new_input3"', output)

    def _generate_multiple_input_files(self):
        input_files_directory = tempfile.mkdtemp()
        with open(os.path.join(input_files_directory, 'f1.yaml'), 'w') as f:
            f.write('input1: new_input1\ninput2: new_input2')
        with open(os.path.join(input_files_directory, 'f2.yaml'), 'w') as f:
            f.write('input3: new_input3')
        return input_files_directory

    def test_local_init_with_inputs(self):
        fd, inputs_file = tempfile.mkstemp()
        os.close(fd)
        with open(inputs_file, 'w') as f:
            f.write('input3: new_input3')
        try:
            self._local_init(
                inputs=['input1=new_input1;input2=new_input2', inputs_file])
            self._assert_multiple_outputs()
        finally:
            os.remove(inputs_file)

    def test_local_init_with_directory_inputs(self):
        input_files_directory = self._generate_multiple_input_files()
        try:
            self._local_init(inputs=[input_files_directory])
            self._assert_multiple_outputs()
        finally:
            shutil.rmtree(input_files_directory)

    def test_local_init_with_wildcard_inputs(self):
        input_files_directory = self._generate_multiple_input_files()
        try:
            self._local_init(
                inputs=[os.path.join(input_files_directory, 'f*.yaml')])
            self._assert_multiple_outputs()
        finally:
            shutil.rmtree(input_files_directory)

    def test_local_execute(self):
        self._local_init()
        self._local_execute()
        output = self.invoke('cfy local outputs')
        self.assertIn('"param": "default_param"', output)

    def test_local_provider_context(self):
        self._init()
        with open(utils.get_configuration_path()) as f:
            config = yaml.safe_load(f.read())
        with open(utils.get_configuration_path(), 'w') as f:
            config['local_provider_context'] = {
                'stub1': 'value1'
            }
            f.write(yaml.safe_dump(config))
        self._local_init()
        self._local_execute()
        output = self.invoke('cfy local outputs')
        self.assertIn('"provider_context":', output)
        self.assertIn('stub1', output)
        self.assertIn('value1', output)

    def test_validate_definitions_version(self):
        blueprint = 'blueprint_validate_definitions_version'
        self._init()
        self.assertRaises(
            parser_exceptions.DSLParsingLogicException,
            self._local_init, blueprint=blueprint)
        with open(utils.get_configuration_path()) as f:
            config = yaml.safe_load(f.read())
        with open(utils.get_configuration_path(), 'w') as f:
            config['validate_definitions_version'] = False
            f.write(yaml.safe_dump(config))
        # Parsing occurs during init
        self._local_init(blueprint=blueprint)

    def test_local_init_install_plugins(self):

        blueprint_path = '{0}/local/{1}.yaml' \
            .format(BLUEPRINTS_DIR,
                    'blueprint_with_plugins')

        self.assert_method_called(
            command='cfy local init --install-plugins -p {0}'
                        .format(blueprint_path),
            module=common,
            function_name='install_blueprint_plugins',
            kwargs={'blueprint_path': blueprint_path}
        )

    def test_empty_requirements(self):
        blueprint = 'blueprint_without_plugins'
        blueprint_path = '{0}/local/{1}.yaml'.format(BLUEPRINTS_DIR,
                                                     blueprint)
        self.invoke('cfy local init --install-plugins -p {0}'
                           .format(blueprint_path))

    def test_local_init_missing_plugin(self):

        blueprint = 'blueprint_with_plugins'
        blueprint_path = '{0}/local/{1}.yaml'.format(BLUEPRINTS_DIR,
                                                     blueprint)

        expected_possible_solutions = [
            "Run `cfy local init --install-plugins -p {0}`"
            .format(blueprint_path),
            "Run `cfy local install-plugins -p {0}`"
            .format(blueprint_path)
        ]
        try:
            self._local_init(blueprint=blueprint)
            self.fail('Excepted ImportError')
        except ImportError as e:
            actual_possible_solutions = e.possible_solutions
            self.assertEqual(actual_possible_solutions,
                             expected_possible_solutions)

    def test_local_execute_with_params(self):
        self._local_init()
        self._local_execute(parameters={'param': 'new_param'})
        output = self.invoke('cfy local outputs')
        self.assertIn('"param": "new_param"', output)

    def test_local_execute_with_params_allow_custom_false(self):
        self._local_init()
        self._local_execute(parameters={'custom_param': 'custom_param_value'},
                            allow_custom=False)

    def test_local_execute_with_params_allow_custom_true(self):
        self._local_init()
        self._local_execute(parameters={'custom_param': 'custom_param_value'},
                            allow_custom=True)
        output = self.invoke('cfy local outputs')
        self.assertIn('"custom_param": "custom_param_value"', output)

    def test_local_instances(self):
        self._local_init()
        self._local_execute()
        output = self.invoke('cfy local instances')
        self.assertIn('"node_id": "node"', output)

    def test_local_instances_with_existing_node_id(self):
        self._local_init()
        self._local_execute()
        output = self.invoke('cfy local instances --node-id node')
        self.assertIn('"node_id": "node"', output)

    def test_local_instances_with_non_existing_node_id(self):
        self._local_init()
        self._local_execute()
        self._assert_ex('cfy local instances --node-id no_node',
                        'Could not find node no_node')

    def test_execute_with_no_init(self):
        self._assert_ex('cfy local execute -w run_test_op_on_nodes',
                        'has not been initialized',
                        possible_solutions=[
                            "Run `cfy local init` in this directory"
                        ])

    def test_outputs_with_no_init(self):
        self._assert_ex('cfy local outputs',
                        'has not been initialized',
                        possible_solutions=[
                            "Run `cfy local init` in this directory"
                        ])

    def test_instances_with_no_init(self):
        self._assert_ex('cfy local instances',
                        'has not been initialized',
                        possible_solutions=[
                            "Run `cfy local init` in this directory"
                        ])

    def test_create_requirements(self):

        from cloudify_cli.tests.resources.blueprints import local

        expected_requirements = {
            'http://localhost/plugin.zip',
            os.path.join(
                os.path.dirname(local.__file__),
                'plugins',
                'local_plugin'),
            'http://localhost/host_plugin.zip'}
        requirements_file_path = os.path.join(TEST_WORK_DIR,
                                              'requirements.txt')

        self.invoke('cfy local create-requirements -p '
                           '{0}/local/blueprint_with_plugins.yaml -o {1}'
                           .format(BLUEPRINTS_DIR, requirements_file_path))

        with open(requirements_file_path, 'r') as f:
            actual_requirements = set(f.read().split())
            self.assertEqual(actual_requirements, expected_requirements)

    def test_create_requirements_existing_output_file(self):
        blueprint_path = '{0}/local/blueprint_with_plugins.yaml'\
            .format(BLUEPRINTS_DIR)
        file_path = tempfile.mktemp()
        with open(file_path, 'w') as f:
            f.write('')
        self._assert_ex(
            cli_cmd='cfy local create-requirements -p {0} -o {1}'
                    .format(blueprint_path, file_path),
            err_str_segment='Output path {0} already exists'.format(file_path)
        )

    def test_create_requirements_no_output(self):

        from cloudify_cli.tests.resources.blueprints import local

        expected_requirements = {
            'http://localhost/plugin.zip',
            os.path.join(
                os.path.dirname(local.__file__),
                'plugins',
                'local_plugin'),
            'http://localhost/host_plugin.zip'}
        output = self.invoke(
            'cfy local create-requirements -p '
            '{0}/local/blueprint_with_plugins.yaml'
            .format(BLUEPRINTS_DIR))
        for requirement in expected_requirements:
            self.assertIn(requirement, output)

    def test_install_agent(self):
        blueprint_path = '{0}/local/install-agent-blueprint.yaml' \
            .format(BLUEPRINTS_DIR)
        try:
            self.invoke('cfy local init -p {0}'.format(blueprint_path))
            self.fail('ValueError was expected')
        except ValueError as e:
            self.assertIn("'install_agent': true is not supported "
                          "(it is True by default) "
                          "when executing local workflows. "
                          "The 'install_agent' property must be set to false "
                          "for each node of type {0}.".format(HOST_TYPE),
                          e.message)

    def test_install_plugins(self):

        blueprint_path = '{0}/local/blueprint_with_plugins.yaml'\
            .format(BLUEPRINTS_DIR)
        try:
            self.invoke('cfy local install-plugins -p {0}'
                               .format(blueprint_path))
        except CommandExecutionException as e:
            # Expected pip install to start
            self.assertIn('pip install -r /tmp/requirements_',
                          e.message)

    def test_install_plugins_missing_windows_agent_installer(self):
        blueprint_path = '{0}/local/windows_installers_blueprint.yaml'\
            .format(BLUEPRINTS_DIR)
        self.invoke('cfy local init -p {0}'.format(blueprint_path))

    @patch('cloudify_cli.commands.local.execute')
    @patch('cloudify_cli.commands.local.init')
    def test_install_command_default_init_arguments(self, local_init_mock, *_):

        local_install_command = 'cfy local install'
        self.invoke(local_install_command)

        local_init_mock.assert_called_with(
            blueprint_path=DEFAULT_BLUEPRINT_PATH,
            inputs=None,
            install_plugins=False
        )

    @patch('cloudify_cli.commands.local.execute')
    @patch('cloudify_cli.commands.local.init')
    def test_install_command_custom_init_arguments(self, local_init_mock, *_):

        local_install_command = \
            'cfy local install -p blueprint_path.yaml -i key=value ' \
            '--install-plugins'

        self.invoke(local_install_command)

        local_init_mock.assert_called_with(
            blueprint_path='blueprint_path.yaml',
            inputs=["key=value"],
            install_plugins=True
        )

    @patch('cloudify_cli.commands.local.init')
    @patch('cloudify_cli.commands.local.execute')
    def test_install_command_default_execute_arguments(self,
                                                       local_execute_mock,
                                                       *_):
        local_install_command = 'cfy local install'
        self.invoke(local_install_command)

        local_execute_mock.assert_called_with(
            workflow_id=DEFAULT_INSTALL_WORKFLOW,
            parameters=DEFAULT_PARAMETERS,
            allow_custom_parameters=False,
            task_retries=0,
            task_retry_interval=1,
            task_thread_pool_size=DEFAULT_TASK_THREAD_POOL_SIZE
        )

    @patch('cloudify_cli.commands.local.init')
    @patch('cloudify_cli.commands.local.execute')
    def test_install_command_custom_execute_arguments(self,
                                                      local_execute_mock,
                                                      *_):

        local_install_command = 'cfy local install ' \
                                '-w my-install ' \
                                '--parameters key=value ' \
                                '--allow-custom-parameters ' \
                                '--task-retries 14 ' \
                                '--task-retry-interval 7 ' \
                                '--task-thread-pool-size 87'
        self.invoke(local_install_command)

        local_execute_mock.assert_called_with(workflow_id='my-install',
                                              parameters=["key=value"],
                                              allow_custom_parameters=True,
                                              task_retries=14,
                                              task_retry_interval=7,
                                              task_thread_pool_size=87
                                              )

    @patch('cloudify_cli.commands.local.execute')
    def test_uninstall_command_execute_default_arguments(self,
                                                         local_execute_mock
                                                         ):
        local_uninstall_command = 'cfy local uninstall'

        self.invoke(local_uninstall_command)

        local_execute_mock.assert_called_with(
            workflow_id=DEFAULT_UNINSTALL_WORKFLOW,
            parameters=DEFAULT_PARAMETERS,
            allow_custom_parameters=False,
            task_retries=0,
            task_retry_interval=1,
            task_thread_pool_size=DEFAULT_TASK_THREAD_POOL_SIZE)

    @patch('cloudify_cli.commands.local.execute')
    def test_uninstall_command_execute_custom_arguments(self,
                                                        local_execute_mock
                                                        ):
        local_uninstall_command = 'cfy local uninstall ' \
                                  '-w my-uninstall ' \
                                  '--parameters key=value ' \
                                  '--allow-custom-parameters ' \
                                  '--task-retries 14 ' \
                                  '--task-retry-interval 7 ' \
                                  '--task-thread-pool-size 87'

        self.invoke(local_uninstall_command)

        local_execute_mock.assert_called_with(
            workflow_id='my-uninstall',
            parameters=['key=value'],
            allow_custom_parameters=True,
            task_retries=14,
            task_retry_interval=7,
            task_thread_pool_size=87)

    def test_uninstall_command_removes_local_storage_dir(self):

        sample_blueprint_path = os.path.join(BLUEPRINTS_DIR,
                                             'local',
                                             'blueprint.yaml')

        # a custom workflow is used because the sample blueprint path does not
        # have an 'install' workflow
        self.invoke('cfy local install '
                           '-w run_test_op_on_nodes '
                           '-p {0}'
                           .format(sample_blueprint_path)
                           )
        self.assertTrue(os.path.isdir(local._storage_dir()))

        # a custom workflow is used because the sample blueprint path does not
        # have an 'uninstall' workflow
        self.invoke('cfy local uninstall '
                           '-w run_test_op_on_nodes '
                           .format(sample_blueprint_path)
                           )

        self.assertFalse(os.path.isdir(local._storage_dir()))

    @nose.tools.nottest
    def test_local_outputs(self):
        # tested extensively by the other tests
        self.fail()

    def test_verbose_logging(self):
        def run(level=None, message=None, error=None, user_cause=None,
                verbose_flag=''):
            params = {}
            if level is not None:
                params['level'] = level
            if message is not None:
                params['message'] = message
            if error is not None:
                params['error'] = error
            if user_cause is not None:
                params['user_cause'] = user_cause
            params_path = os.path.join(utils.get_cwd(), 'parameters.json')
            with open(params_path, 'w') as f:
                f.write(json.dumps(params))
            with cloudify_cli.tests.commands.mocks.mock_stdout() as output:
                self.invoke('cfy local execute -w logging_workflow '
                                   '-p {0} {1}'.format(params_path,
                                                       verbose_flag))
            return output.getvalue()

        blueprint_path = '{0}/logging/blueprint.yaml'.format(BLUEPRINTS_DIR)
        self.invoke('cfy local init -p {0}'.format(blueprint_path))

        message = 'MESSAGE'

        def assert_output(verbosity,
                          expect_debug=False,
                          expect_traceback=False):
            output = run(level='INFO', message=message, verbose_flag=verbosity)
            self.assertIn('INFO: {0}'.format(message), output)
            output = run(level='DEBUG', message=message,
                         verbose_flag=verbosity)
            if expect_debug:
                self.assertIn('DEBUG: {0}'.format(message), output)
            else:
                self.assertNotIn(message, output)
            output = run(message=message, error=True, verbose_flag=verbosity)
            self.assertIn('Task failed', output)
            self.assertIn(message, output)
            if expect_traceback:
                self.assertIn('Traceback', output)
                self.assertNotIn('Causes', output)
            else:
                self.assertNotIn('Traceback', output)
            output = run(message=message, error=True, user_cause=True,
                         verbose_flag=verbosity)
            self.assertIn('Task failed', output)
            self.assertIn(message, output)
            if expect_traceback:
                if expect_traceback:
                    self.assertIn('Traceback', output)
                    self.assertIn('Causes', output)
                else:
                    self.assertNotIn('Traceback', output)
        assert_output(verbosity='')
        assert_output(verbosity='-v', expect_traceback=True)
        assert_output(verbosity='-vv', expect_traceback=True,
                      expect_debug=True)
        assert_output(verbosity='-vvv', expect_traceback=True,
                      expect_debug=True)

    def _init(self):
        self.invoke('cfy init')

    def _local_init(self,
                    inputs=None,
                    blueprint='blueprint',
                    install_plugins=False):

        blueprint_path = '{0}/local/{1}.yaml'.format(BLUEPRINTS_DIR,
                                                     blueprint)
        flags = '--install-plugins' if install_plugins else ''
        command = 'cfy local init {0} -p {1}'.format(flags,
                                                     blueprint_path)
        inputs = inputs or []
        for inputs_instance in inputs:
            command += ' -i {0}'.format(inputs_instance)
        self.invoke(command)

    def _local_execute(self, parameters=None,
                       allow_custom=None,
                       workflow_name='run_test_op_on_nodes'):
        if parameters:
            parameters_path = os.path.join(TEST_WORK_DIR,
                                           'temp_parameters.json')
            with open(parameters_path, 'w') as f:
                f.write(json.dumps(parameters))
            command = 'cfy local execute -w {0} -p {1}'\
                      .format(workflow_name,
                              parameters_path)
            if allow_custom is True:
                self.invoke('{0} --allow-custom-parameters'
                                   .format(command))
            elif allow_custom is False:
                self._assert_ex(command, 'does not have the following')
            else:
                self.invoke(command)
        else:
            self.invoke('cfy local execute -w {0}'
                               .format(workflow_name))


class LogsTest(CliCommandTest):
    def test_with_empty_config(self):
        self.use_manager(user=None, port=None, key=None)
        self.invoke('cfy logs download',
                    'Manager User is not set '
                    'in working directory settings')

    def test_with_no_key(self):
        self.use_manager(user='test', port='22', host='127.0.0.1', key=None)
        self.invoke('cfy logs download',
                    'Manager Key is not set '
                    'in working directory settings')

    def test_with_no_user(self):
        self.use_manager(port='22', key='/tmp/test.pem', user=None)
        self.invoke('cfy logs download',
                    'Manager User is not set '
                    'in working directory settings')

    def test_with_no_port(self):
        self.use_manager(user='test', key='/tmp/test.pem', host='127.0.0.1', port=None)
        self.invoke('cfy logs download',
                    'Manager Port is not set '
                    'in working directory settings')

    def test_with_no_server(self):
        self.use_manager(user='test', key='/tmp/test.pem', host=None)
        self.invoke(
            'cfy logs download',
            err_str_segment='command is only available when using a manager')

    def test_purge_no_force(self):
        self.use_manager()
        # unlike the other tests, this drops on argparse raising
        # that the `-f` flag is required for purge, which is why
        # the exception message is actually the returncode from argparse.
        self.invoke('cfy logs purge', 'You must supply the `-f, --force`')


class MaintenanceModeTest(CliCommandTest):

    def setUp(self):
        super(MaintenanceModeTest, self).setUp()
        self.use_manager()
        self.client.maintenance_mode.deactivate = MagicMock()
        self.client.maintenance_mode.activate = MagicMock()

    def test_maintenance_status(self):
        self.client.maintenance_mode.status = MagicMock()
        self.invoke('cfy maintenance-mode status')

    def test_activate_maintenance(self):
        self.invoke('cfy maintenance-mode activate')

    def test_activate_maintenance_with_wait(self):
        with patch('cloudify_rest_client.maintenance.'
                   'MaintenanceModeClient.status',
                   new=mock_activated_status):
            with patch('time.sleep') as sleep_mock:
                self.invoke('cfy maintenance-mode activate --wait')
                self.invoke('cfy maintenance-mode '
                               'activate --wait --timeout 20')
                sleep_mock.assert_has_calls([call(5), call(5)])

    def test_activate_maintenance_timeout(self):
        with patch('cloudify_cli.commands.maintenance_mode._is_timeout',
                   new=mock_is_timeout):
            self.invoke(
                'cfy maintenance-mode activate --wait',
                err_str_segment='Timed out while entering maintenance mode')

    def test_activate_maintenance_timeout_no_wait(self):
        self.invoke('cfy maintenance-mode activate --timeout 5',
                       "'--timeout' was used without '--wait'.",
                       # TODO: put back
                       # possible_solutions=["Add the '--wait' flag to "
                       #                     "the command in order to wait."]
                       )

    def test_deactivate_maintenance(self):
        self.invoke('cfy maintenance-mode deactivate')


class InstancesTest(CliCommandTest):

    def setUp(self):
        super(InstancesTest, self).setUp()
        self.use_manager()

    def test_instances_get(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        self.invoke('cfy node-instances get instance_id', context='manager')

    def test_instance_get_no_instance_id(self):
        self.invoke(
            'cfy node-instances get', should_fail=True, context='manager')

    def test_instances_list(self):
        self.client.node_instances.list = MagicMock(
            return_value=[node_instance_get_mock(), node_instance_get_mock()])
        self.invoke('cfy node-instances list', context='manager')
        self.invoke('cfy node-instances list -d nodecellar', context='manager')


class NodesTest(CliCommandTest):

    def setUp(self):
        super(NodesTest, self).setUp()
        self.use_manager()

    def test_nodes_get(self):
        self.client.nodes.get = MagicMock(return_value=node_get_mock())
        self.client.node_instances.list = MagicMock(
            return_value=[node_instance_get_mock()])
        self.invoke('cfy nodes get mongod -d nodecellar')

    def test_node_get_no_node_id(self):
        self.invoke('cfy nodes get -d nodecellar', should_fail=True)

    def test_node_get_no_deployment_id(self):
        self.invoke('cfy nodes get --node-id mongod', should_fail=True)

    def test_nodes_list(self):
        self.client.nodes.list = MagicMock(
            return_value=[node_get_mock(), node_get_mock()])
        self.invoke('cfy nodes list')
        self.invoke('cfy nodes list -d nodecellar')


class PluginsTest(CliCommandTest):

    def setUp(self):
        super(PluginsTest, self).setUp()
        self.use_manager()

    def test_plugins_list(self):
        self.client.plugins.list = MagicMock(return_value=[])
        self.invoke('cfy plugins list')

    def test_plugin_get(self):
        self.client.plugins.get = MagicMock(
            return_value=plugins.Plugin({'id': 'id',
                                         'package_name': 'dummy',
                                         'package_version': '1.2',
                                         'supported_platform': 'any',
                                         'distribution_release': 'trusty',
                                         'distribution': 'ubuntu',
                                         'uploaded_at': 'now'}))

        self.invoke('cfy plugins get some_id')

    def test_plugins_delete(self):
        self.client.plugins.delete = MagicMock()
        self.invoke('cfy plugins delete a-plugin-id')

    def test_plugins_delete_force(self):
        for flag in ['--force', '-f']:
            mock = MagicMock()
            self.client.plugins.delete = mock
            self.invoke('cfy plugins delete a-plugin-id {0}'.format(
                flag))
            mock.assert_called_once_with(plugin_id='a-plugin-id', force=True)

    def test_plugins_upload(self):
        self.client.plugins.upload = MagicMock()
        plugin_dest = os.path.join(tempfile.gettempdir(), 'plugin.tar.gz')
        try:
            self.make_sample_plugin(plugin_dest)
            self.invoke('cfy plugins upload {0}'.format(plugin_dest))
        finally:
            shutil.rmtree(plugin_dest, ignore_errors=True)

    def test_plugins_download(self):
        self.client.plugins.download = MagicMock(return_value='some_file')
        self.invoke('cfy plugins download a-plugin-id')

    def make_sample_plugin(self, plugin_dest):
        temp_folder = tempfile.mkdtemp()
        with open(os.path.join(temp_folder, 'package.json'), 'w') as f:
            f.write('{}')
        _make_tarfile(plugin_dest, temp_folder)


class RecoverTest(CliCommandTest):

    def test_recover_no_force(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        fake_snapshot_path = os.path.join(TEST_WORK_DIR, 'sn.zip')
        open(fake_snapshot_path, 'w').close()

        self.client.deployments.list = MagicMock(return_value=[])
        self.invoke('cfy use 10.0.0.1')
        self.invoke('cfy recover {0}'.format(fake_snapshot_path),
                    'This action requires additional confirmation.')

    @patch('cloudify_cli.bootstrap.bootstrap'
           '.read_manager_deployment_dump_if_needed')
    @patch('cloudify_cli.bootstrap.bootstrap.recover')
    def test_recover_from_same_directory_as_bootstrap(self, *_):
        # mock bootstrap behavior by setting the manager key path
        # in the local context
        key_path = os.path.join(TEST_WORK_DIR, 'key.pem')
        open(key_path, 'w').close()

        self.use_manager(key=key_path, provider_context={})

        # now run recovery and make sure no exception was raised
        self.invoke('cfy recover -f {0}'.format(key_path))

    @patch('cloudify_cli.bootstrap.bootstrap'
           '.read_manager_deployment_dump_if_needed')
    @patch('cloudify_cli.bootstrap.bootstrap.recover')
    def test_recover_without_snapshot_flag(self, *_):
        self.invoke('cfy recover -f', should_fail=True)

    @patch('cloudify_cli.bootstrap.bootstrap'
           '.read_manager_deployment_dump_if_needed')
    @patch('cloudify_cli.bootstrap.bootstrap.recover')
    def test_recover_from_same_directory_as_bootstrap_missing_key(self, *_):

        # mock bootstrap behavior by setting the manager key path
        # in the local context. however, don't actually create the key file
        key_path = os.path.join(TEST_WORK_DIR, 'key.pem')
        fake_snapshot_path = os.path.join(TEST_WORK_DIR, 'sn.zip')
        open(fake_snapshot_path, 'w').close()

        self.use_manager(key=key_path, provider_context={})

        # recovery command should not fail because the key file specified in
        # the context file does not exist
        self.invoke('cfy recover -f {0}'.format(fake_snapshot_path),
                    'Cannot perform recovery. manager key '
                    'file does not exist',
                    exception=exceptions.CloudifyValidationError)

    @patch('cloudify_cli.bootstrap.bootstrap'
           '.read_manager_deployment_dump_if_needed')
    @patch('cloudify_cli.bootstrap.bootstrap.recover')
    def test_recover_missing_key_with_env(self, *_):

        key_path = os.path.join(TEST_WORK_DIR, 'key.pem')
        fake_snapshot_path = os.path.join(TEST_WORK_DIR, 'sn.zip')
        open(fake_snapshot_path, 'w').close()
        try:
            os.environ['CLOUDIFY_MANAGER_PRIVATE_KEY_PATH'] = key_path

            # recovery command should not fail because the key file
            # specified in the context file does not exist
            self.invoke('cfy recover -f {0}'.format(fake_snapshot_path),
                        'Cannot perform recovery. manager private '
                        'key file defined in '
                        'CLOUDIFY_MANAGER_PRIVATE_KEY_PATH '
                        'environment variable does not exist: '
                        '{0}'.format(key_path),
                        exception=exceptions.CloudifyValidationError)
        finally:
            del os.environ['CLOUDIFY_MANAGER_PRIVATE_KEY_PATH']

    @patch('cloudify_cli.bootstrap.bootstrap'
           '.read_manager_deployment_dump_if_needed')
    @patch('cloudify_cli.bootstrap.bootstrap.recover')
    def test_recover_from_different_directory_than_bootstrap(self, *_):
        # recovery command should not fail because we do not have a manager
        # key path in the local context, and the environment variable is not
        # set
        fake_snapshot_path = os.path.join(TEST_WORK_DIR, 'sn.zip')
        open(fake_snapshot_path, 'w').close()
        self.invoke('cfy recover -f {0}'.format(fake_snapshot_path),
                    'Cannot perform recovery. manager key file not found. '
                    'Set the manager private key path via the '
                    'CLOUDIFY_MANAGER_PRIVATE_KEY_PATH environment '
                    'variable',
                    exception=exceptions.CloudifyValidationError)

    @patch('cloudify_cli.bootstrap.bootstrap'
           '.read_manager_deployment_dump_if_needed')
    @patch('cloudify_cli.bootstrap.bootstrap.recover')
    def test_recover_from_different_directory_than_bootstrap_with_env_variable(self, *_):  # NOQA

        key_path = os.path.join(TEST_WORK_DIR, 'key.pem')
        open(key_path, 'w').close()

        self.use_manager(key=key_path, provider_context={})

        try:
            os.environ['CLOUDIFY_MANAGER_PRIVATE_KEY_PATH'] = key_path
            self.invoke('cfy recover -f {0}'.format(key_path))
        finally:
            del os.environ['CLOUDIFY_MANAGER_PRIVATE_KEY_PATH']


class ManagerRollbackTest(BaseUpgradeTest):

    def setUp(self):
        super(ManagerRollbackTest, self).setUp()
        self.use_manager()

    def test_not_in_maintenance_rollback(self):
        self._test_not_in_maintenance(action='rollback')

    def test_rollback_no_bp(self):
        self._test_no_bp(action='rollback')

    def test_rollback_no_private_ip(self):
        self._test_no_private_ip(action='rollback')

    def test_rollback_no_inputs(self):
        self._test_no_inputs(action='rollback')


class SnapshotsTest(CliCommandTest):

    def setUp(self):
        super(SnapshotsTest, self).setUp()
        self.use_manager()

    def test_snapshots_list(self):
        self.client.snapshots.list = MagicMock(return_value=[])
        self.invoke('cfy snapshots list')

    def test_snapshots_delete(self):
        self.client.snapshots.delete = MagicMock()
        self.invoke('cfy snapshots delete a-snapshot-id')

    def test_snapshots_upload(self):
        self.client.snapshots.upload = MagicMock(
            return_value=snapshots.Snapshot({'id': 'some_id'}))
        self.invoke('cfy snapshots upload {0}/snapshot.zip '
                    '-s my_snapshot_id'.format(SNAPSHOTS_DIR))

    def test_snapshots_create(self):
        self.client.snapshots.create = MagicMock(
            return_value=executions.Execution({'id': 'some_id'}))
        self.invoke('cfy snapshots create a-snapshot-id')

    def test_snapshots_restore(self):
        self.client.snapshots.restore = MagicMock()
        self.invoke('cfy snapshots restore a-snapshot-id')
        self.invoke('cfy snapshots restore a-snapshot-id'
                    '--without-deployments-envs')

    def test_snapshots_download(self):
        self.client.snapshots.download = MagicMock(return_value='some_file')
        self.invoke('cfy snapshots download a-snapshot-id')


class SshTest(CliCommandTest):

    def test_ssh_no_manager(self):
        self.invoke(
            'cfy ssh',
            'This command is only available when using a manager'
        )

    def test_ssh_with_empty_config(self):
        self.use_manager(user=None)
        self.invoke('cfy ssh',
                    'Manager User is not set '
                    'in working directory settings')

    def test_ssh_with_no_key(self):
        self.use_manager(user='test', host='127.0.0.1', key=None)
        self.invoke('cfy ssh',
                    'Manager Key is not set '
                    'in working directory settings')

    def test_ssh_with_no_user(self):
        self.use_manager(key='/tmp/test.pem', host='127.0.0.1', user=None)
        self.invoke('cfy ssh',
                    'Manager User is not set '
                    'in working directory settings')

    def test_ssh_with_no_server(self):
        self.use_manager(key='/tmp/test.pem', user='test', host=None)
        self.invoke(
            'cfy ssh',
            'This command is only available when using a manager'
        )

    def test_ssh_without_ssh_windows(self):
        platform.system = lambda: 'Windows'
        if os.name != 'nt':
            self.skipTest('Irrelevant on Linux')
        self.use_manager(key='/tmp/test.pem', user='test', host='127.0.0.1')
        spawn.find_executable = lambda x: None
        self.invoke('cfy ssh', 'ssh.exe not found')

    def test_ssh_without_ssh_linux(self):
        platform.system = lambda: 'Linux'
        if os.name == 'nt':
            self.skipTest('Irrelevant on Windows')
        self.use_manager(key='/tmp/test.pem', user='test', host='127.0.0.1')
        spawn.find_executable = lambda x: None
        self.invoke('cfy ssh', 'ssh not found')

    def test_host_list_conflicts(self):
        self.assertRaises(
            exceptions.CloudifyCliError,
            _validate_env,
            command='',
            host=True,
            sid='',
            list_sessions=True
        )


class StatusTest(CliCommandTest):

    def setUp(self):
        super(StatusTest, self).setUp()
        self.client.manager.get_status = MagicMock()
        self.client.maintenance_mode.status = MagicMock()

    def test_status_command(self):
        self.use_manager()
        self.invoke('cfy status')

    def test_status_no_manager_server_defined(self):
        # Running a command which requires a target manager server without
        # first calling "cfy use" or providing a target server explicitly
        self.invoke(
            'cfy status',
            'This command is only available when using a manager'
        )

    def test_status_by_unauthorized_user(self):
        self.use_manager()
        with patch('cloudify_cli.env.get_rest_host'):
            with patch.object(self.client.manager, 'get_status') as mock:
                mock.side_effect = UserUnauthorizedError('Unauthorized user')
                outcome = self.invoke('cfy status')
                self.assertIn('User is unauthorized', outcome.logs)


class TeardownTest(CliCommandTest):

    def test_teardown_no_force(self):
        self.invoke('cfy teardown',
                    'This action requires additional confirmation.')

    @patch('cloudify_cli.bootstrap.bootstrap.teardown')
    def test_teardown_has_existing_deployments_ignore_deployments(self, mock_teardown):  # NOQA
        self.client.manager.get_status = MagicMock()
        self.client.deployments.list = MagicMock(return_value=[{}])
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        self.invoke('cfy use 10.0.0.1')
        self.invoke('cfy teardown -f --ignore-deployments')
        # TODO: The values are the values of the task-retry flags.
        # These should be retrieved from somewhere else.
        mock_teardown.assert_called_once_with(
            task_retries=0,
            task_retry_interval=1,
            task_thread_pool_size=1
        )

    def test_teardown_has_existing_deployments_dont_ignore_deployments(self):
        self.client.manager.get_status = MagicMock()
        self.client.deployments.list = MagicMock(return_value=[{}])
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        self.invoke('cfy use 10.0.0.1')
        self.invoke('cfy teardown -f',
                    'has existing deployments')

    def test_teardown_manager_down_dont_ignore_deployments(self):
        self.client.manager.get_status = MagicMock()

        def raise_client_error():
            raise CloudifyClientError('CloudifyClientError')

        self.client.deployments.list = raise_client_error
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        self.invoke('cfy use 10.0.0.1')
        self.invoke('cfy teardown -f',
                    'The manager may be down')

    @patch('cloudify_cli.bootstrap.bootstrap.teardown')
    def test_teardown_manager_down_ignore_deployments(self, mock_teardown):
        def raise_client_error():
            raise CloudifyClientError('this is an IOError')

        self.client.deployments.list = raise_client_error
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )

        self.use_manager(host='10.0.0.1')

        self.invoke('cfy teardown -f --ignore-deployments')
        mock_teardown.assert_called_once_with(
            task_retries=0,
            task_retry_interval=1,
            task_thread_pool_size=1
        )

    # TODO: Not sure we're checking the right things here
    @patch('cloudify_cli.bootstrap.bootstrap.teardown')
    def test_teardown_no_manager_ip_in_context_right_directory(
            self, mock_teardown):  # NOQA

        def mock_client_list():
            return list()

        self.client.deployments.list = mock_client_list

        self.use_manager(host='10.0.0.1')

        self.invoke('cfy teardown -f')
        mock_teardown.assert_called_once_with(
            task_retries=0,
            task_retry_interval=1,
            task_thread_pool_size=1
        )


class UninstallTest(CliCommandTest):
    def setUp(self):
        super(UninstallTest, self).setUp()
        self.use_manager()

    @patch('cloudify_cli.commands.blueprints.delete')
    @patch('cloudify_cli.commands.deployments.manager_delete')
    @patch('cloudify_cli.env.get_rest_client')
    @patch('cloudify_cli.commands.executions.manager_start')
    def test_default_executions_start_arguments(self, executions_start_mock,
                                                *_):
        self.invoke('cfy uninstall did', context='manager')

        executions_start_mock.assert_called_with(
            workflow_id=DEFAULT_UNINSTALL_WORKFLOW,
            deployment_id=u'did',
            timeout=DEFAULT_TIMEOUT,
            force=False,
            include_logs=True,
            allow_custom_parameters=False,
            parameters=DEFAULT_PARAMETERS,
            json=False
        )

    @patch('cloudify_cli.commands.blueprints.delete')
    @patch('cloudify_cli.commands.deployments.manager_delete')
    @patch('cloudify_cli.env.get_rest_client')
    @patch('cloudify_cli.commands.executions.manager_start')
    def test_custom_executions_start_arguments(self,
                                               executions_start_mock, *_
                                               ):
        uninstall_command = 'cfy uninstall ' \
                            '-w my_uninstall ' \
                            'did ' \
                            '--timeout 1987 ' \
                            '--allow-custom-parameters ' \
                            '--include-logs ' \
                            '--parameters key=value ' \
                            '--json'

        self.invoke(uninstall_command, context='manager')

        executions_start_mock.assert_called_with(
            workflow_id=u'my_uninstall',
            deployment_id=u'did',
            timeout=1987,
            force=False,
            include_logs=True,
            allow_custom_parameters=True,
            parameters={'key': 'value'},
            json=True
        )

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_delete')
    @patch('cloudify_cli.commands.blueprints.delete')
    def test_getting_blueprint_id_from_deployment(self,
                                                  mock_blueprints_delete,
                                                  *_):

        def mock_deployments_get(*args, **kwargs):
            return deployments.Deployment({'blueprint_id': 'bid'})

        self.client.deployments.get = mock_deployments_get

        self.invoke('cfy uninstall did', context='manager')
        mock_blueprints_delete.assert_called_with(blueprint_id=u'bid')

    @patch('cloudify_cli.commands.blueprints.delete')
    @patch('cloudify_cli.env.get_rest_client')
    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_delete')
    def test_deployments_delete_arguments(self, deployments_delete_mock, *_):

        self.invoke('cfy uninstall did', context='manager')

        deployments_delete_mock.assert_called_with(
            deployment_id=u'did',
            ignore_live_nodes=False
        )

    @patch('cloudify_cli.env.get_rest_client')
    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_delete')
    @patch('cloudify_cli.commands.blueprints.delete')
    def test_blueprint_is_deleted(self, blueprints_delete_mock, *_):

        self.invoke('cfy uninstall did', context='manager')
        self.assertTrue(blueprints_delete_mock.called)


class ManagerUpgradeTest(BaseUpgradeTest):

    def setUp(self):
        super(ManagerUpgradeTest, self).setUp()
        self.use_manager()

    def test_not_in_maintenance_upgrade(self):
        self._test_not_in_maintenance(action='upgrade')

    def test_upgrade_no_bp(self):
        self._test_no_bp(action='upgrade')

    def _test_upgrade_no_private_ip(self):
        self._test_no_private_ip(action='upgrade')

    def _test_upgrade_no_inputs(self):
        self._test_no_inputs(action='upgrade')


class UseTest(CliCommandTest):

    def test_use_command(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={
                'name': 'name',
                'context': {}}
        )
        self.invoke('cfy use 127.0.0.1')
        context = self._read_context()
        self.assertEquals("127.0.0.1", context.get_manager_ip())

    def test_use_attempt_by_unauthorized_user(self):
        with patch.object(self.client.manager, 'get_status') as mock:
            mock.side_effect = UserUnauthorizedError('Unauthorized user')
            self.invoke('cfy use 127.0.0.1',
                        err_str_segment='User is unauthorized')

    def test_use_command_no_prior_init(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={
                'name': 'name', 'context': {}
            }
        )
        self.invoke('cfy use 127.0.0.1')
        context = self._read_context()
        self.assertEquals('127.0.0.1', context.get_manager_ip())

    def test_use_with_authorization(self):
        host = '127.0.0.1'
        auth_header = env.get_auth_header('test_username', 'test_password')
        self.client = CloudifyClient(host=host, headers=auth_header)

        self._test_use()

        # assert Authorization in headers
        eventual_request_headers = self.client._client.headers
        self.assertEqual(self.do_request_headers, eventual_request_headers)

    def test_use_with_verify(self):
        host = 'localhost'
        self.client = CloudifyClient(host=host, protocol='https')
        self._test_use()
        self.assertEqual(self.request_url,
                         'https://{0}:{1}/api/{2}/status'.format(host,
                                                                 SSL_PORT,
                                                                 API_VERSION))
        self.assertTrue(self.verify)

    def test_use_trust_all(self):
        host = 'localhost'
        self.client = CloudifyClient(host=host,
                                     protocol='https', trust_all=True)
        self._test_use()
        self.assertEqual(self.request_url,
                         'https://{0}:{1}/api/{2}/status'.format(host,
                                                                 SSL_PORT,
                                                                 API_VERSION))
        self.assertFalse(self.verify)

    def _test_use(self):
        host = 'localhost'
        self.client.manager.get_context = MagicMock(
            return_value={
                'name': 'name',
                'context': {}
            }
        )

        self.headers = None
        self.request_url = None
        self.verify = None

        def mock_do_request(*_, **kwargs):
            self.do_request_headers = kwargs.get('headers')
            self.request_url = kwargs.get('request_url')
            self.verify = kwargs.get('verify')
            return 'success'

        with patch('cloudify_rest_client.client.HTTPClient._do_request',
                   new=mock_do_request):
            self.invoke('cfy use {0} --rest-port {1}'.format(
                host, self.client._client.port))


class VersionTest(CliCommandTest):

    def test_version(self):
        self.invoke('cfy --version')


class WorkflowsTest(CliCommandTest):
    def setUp(self):
        super(WorkflowsTest, self).setUp()
        self.use_manager()

    def test_workflows_list(self):
        deployment = deployments.Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'workflows': [
                {
                    'created_at': None,
                    'name': 'mock_workflow',
                    'parameters': {
                        'test-key': {
                            'default': 'test-value'
                        },
                        'test-mandatory-key': {},
                        'test-nested-key': {
                            'default': {
                                'key': 'val'
                            }
                        }
                    }
                }
            ]
        })

        self.client.deployments.get = MagicMock(return_value=deployment)
        self.invoke('cfy workflows list -d a-deployment-id')

    def test_workflows_sort_list(self):

        deployment = deployments.Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'workflows': [
                {
                    'created_at': None,
                    'name': 'my_workflow_1',
                    'parameters': {
                        'test-key': {
                            'default': 'test-value'
                        },
                        'test-mandatory-key': {},
                        'test-nested-key': {
                            'default': {
                                'key': 'val'
                            }
                        }
                    }
                },
                {
                    'created_at': None,
                    'name': 'my_workflow_0',
                    'parameters': {
                        'test-key': {
                            'default': 'test-value'
                        },
                        'test-mandatory-key': {},
                        'test-nested-key': {
                            'default': {
                                'key': 'val'
                            }
                        }
                    }
                }
            ]
        })

        self.client.deployments.get = MagicMock(return_value=deployment)

        output = self.invoke('cfy workflows list -d a-deployment-id').logs
        first = output.find('my_workflow_0')
        second = output.find('my_workflow_1')
        self.assertTrue(0 < first < second)

    def test_workflows_get(self):
        deployment = deployments.Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'workflows': [
                {
                    'created_at': None,
                    'name': 'mock_workflow',
                    'parameters': {
                        'test-key': {
                            'default': 'test-value'
                        },
                        'test-mandatory-key': {},
                        'test-nested-key': {
                            'default': {
                                'key': 'val'
                            }
                        }
                    }
                }
            ]
        })

        self.client.deployments.get = MagicMock(return_value=deployment)
        self.invoke('cfy workflows get mock_workflow -d dep_id')

    def test_workflows_get_nonexistent_workflow(self):

        expected_message = 'Workflow nonexistent_workflow not found'
        deployment = deployments.Deployment({
            'blueprint_id': 'mock_blueprint_id',
            'workflows': [
                {
                    'created_at': None,
                    'name': 'mock_workflow',
                    'parameters': {
                        'test-key': {
                            'default': 'test-value'
                        },
                        'test-mandatory-key': {},
                        'test-nested-key': {
                            'default': {
                                'key': 'val'
                            }
                        }
                    }
                }
            ]
        })

        self.client.deployments.get = MagicMock(return_value=deployment)
        self.invoke('cfy workflows get nonexistent_workflow -d dep_id',
                    expected_message)

    def test_workflows_get_nonexistent_deployment(self):

        expected_message = \
            "Deployment 'nonexistent-dep' not found on manager server"

        self.client.deployments.get = MagicMock(
            side_effect=CloudifyClientError(expected_message))
        self.invoke('cfy workflows get wf -d nonexistent-dep -v',
                    err_str_segment=expected_message,
                    exception=CloudifyClientError)