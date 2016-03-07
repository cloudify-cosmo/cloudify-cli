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
Tests 'cfy install'
"""

import os

from mock import patch

from cloudify_cli import commands
from cloudify_cli import utils

from cloudify_cli.constants import DEFAULT_BLUEPRINT_FILE_NAME
from cloudify_cli.constants import DEFAULT_BLUEPRINT_PATH
from cloudify_cli.constants import DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND
from cloudify_cli.constants import DEFAULT_TIMEOUT
from cloudify_cli.constants import DEFAULT_INSTALL_WORKFLOW
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest
from cloudify_cli.tests.commands.test_cli_command import BLUEPRINTS_DIR


SAMPLE_BLUEPRINT_PATH = os.path.join(BLUEPRINTS_DIR,
                                     'helloworld',
                                     'blueprint.yaml')
SAMPLE_ARCHIVE_PATH = os.path.join(BLUEPRINTS_DIR,
                                   'helloworld.zip')
SAMPLE_ARCHIVE_URL = 'http://example.com/path/archive.zip'
STUB_BLUEPRINT_FILENAME = 'my_blueprint.yaml'
STUB_ARCHIVE_LOCATION = 'archive.zip'
STUB_BLUEPRINT_ID = 'blueprint_id'
STUB_INPUTS = 'inputs.yaml'
STUB_DEPLOYMENT_ID = 'deployment_id'
STUB_WORKFLOW = 'my_workflow'
STUB_TIMEOUT = 900
STUB_FORCE = False
STUB_ALLOW_CUSTOM_PARAMETERS = False
STUB_INCLUDE_LOGS = False
STUB_PARAMETERS = 'key=value'


class InstallTest(CliCommandTest):

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.create')
    @patch('cloudify_cli.commands.blueprints.publish_archive')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_use_blueprints_upload_mode(
            self,
            blueprints_upload_mock,
            blueprints_publish_archive_mock,
            deployments_create_mock,
            executions_start_mock):

        upload_mode_install_cmd = 'cfy install -p {0}' \
            .format(SAMPLE_BLUEPRINT_PATH)

        cli_runner.run_cli(upload_mode_install_cmd)

        self.assertTrue(blueprints_upload_mock.called)
        self.assertTrue(deployments_create_mock.called)
        self.assertTrue(executions_start_mock.called)
        self.assertFalse(blueprints_publish_archive_mock.called)

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.create')
    @patch('cloudify_cli.commands.blueprints.publish_archive')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_use_blueprints_publish_archive_mode(
            self,
            blueprints_upload_mock,
            blueprints_publish_archive_mock,
            deployments_create_mock,
            executions_start_mock):

        publish_archive_command = \
            'cfy install -n {0} --archive-location={1}'\
            .format(STUB_BLUEPRINT_FILENAME, SAMPLE_ARCHIVE_PATH)

        cli_runner.run_cli(publish_archive_command)

        self.assertTrue(blueprints_publish_archive_mock.called)
        self.assertTrue(deployments_create_mock.called)
        self.assertTrue(executions_start_mock.called)
        self.assertFalse(blueprints_upload_mock.called)

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.create')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_blueprint_filename_default_value(self, *_):
        publish_archive_command = \
            'cfy install --archive-location={0} --blueprint-id={1}'\
            .format(STUB_ARCHIVE_LOCATION, STUB_BLUEPRINT_ID)

        self.assert_method_called(
            cli_command=publish_archive_command,
            module=commands.blueprints,
            function_name='publish_archive',
            args=[STUB_ARCHIVE_LOCATION, DEFAULT_BLUEPRINT_FILE_NAME,
                  STUB_BLUEPRINT_ID
                  ]
        )

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.create')
    @patch('cloudify_cli.commands.blueprints.publish_archive')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_blueprint_path_default_value(self, blueprints_upload_mock, *_):

        install_upload_mode_command = \
            'cfy install --blueprint-id={0}'.format(STUB_BLUEPRINT_ID)

        tmp_blueprint_path = os.path.join(self.original_utils_get_cwd(),
                                          DEFAULT_BLUEPRINT_PATH)

        # create a tmp file representing a blueprint to upload
        open(tmp_blueprint_path, 'w+').close()

        cli_runner.run_cli(install_upload_mode_command)

        blueprint_path_argument_from_upload = \
            blueprints_upload_mock.call_args_list[0][0][0]

        # check that the blueprint path value that was assigned in `install`
        # is indeed the default blueprint file path
        self.assertEqual(blueprint_path_argument_from_upload.name,
                         tmp_blueprint_path
                         )

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.create')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_blueprint_id_default_publish_archive_mode_local_path(self, *_):

        publish_archive_command = \
            'cfy install -n {0} --archive-location={1}'\
            .format(STUB_BLUEPRINT_FILENAME, SAMPLE_ARCHIVE_PATH)

        archive_name = 'helloworld'

        self.assert_method_called(
            cli_command=publish_archive_command,
            module=commands.blueprints,
            function_name='publish_archive',
            args=[SAMPLE_ARCHIVE_PATH,
                  STUB_BLUEPRINT_FILENAME,
                  archive_name]
        )

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.create')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_blueprint_id_default_publish_archive_mode_url(self, *_):

        publish_archive_command = \
            'cfy install -n {0} --archive-location={1}' \
            .format(STUB_BLUEPRINT_FILENAME, SAMPLE_ARCHIVE_URL)

        archive_name = 'archive'

        self.assert_method_called(
            cli_command=publish_archive_command,
            module=commands.blueprints,
            function_name='publish_archive',
            args=[SAMPLE_ARCHIVE_URL,
                  STUB_BLUEPRINT_FILENAME,
                  archive_name]
        )

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.create')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_blueprint_id_default_upload_mode(self, blueprints_upload_mock,
                                              *_):

        install_upload_mode_command = \
            'cfy install -p {0}'.format(SAMPLE_BLUEPRINT_PATH)

        directory_name = 'helloworld'

        cli_runner.run_cli(install_upload_mode_command)

        blueprint_id_argument_from_upload = \
            blueprints_upload_mock.call_args_list[0][0][1]

        # check that the blueprint id value that was assigned in `install`
        # is indeed the default blueprint id (that is, the name of the dir
        # that contains the blueprint file)
        self.assertEqual(blueprint_id_argument_from_upload,
                         directory_name
                         )

    @patch('cloudify_cli.commands.blueprints.publish_archive')
    @patch('cloudify_cli.commands.executions.start')
    def test_default_deployment_id(self, *_):

        command = \
            'cfy install -n {0} --archive-location={1} --inputs={2} -b {3}'\
            .format(STUB_BLUEPRINT_FILENAME, STUB_ARCHIVE_LOCATION,
                    STUB_INPUTS, STUB_BLUEPRINT_ID)

        self.assert_method_called(
            cli_command=command,
            module=commands.deployments,
            function_name='create',
            args=[STUB_BLUEPRINT_ID, STUB_BLUEPRINT_ID, [STUB_INPUTS]]
        )

    @patch('cloudify_cli.commands.blueprints.publish_archive')
    @patch('cloudify_cli.commands.executions.start')
    def test_custom_deployment_id(self, *_):

        command = \
            'cfy install -n {0} --archive-location={1} ' \
            '--inputs={2} -b {3} -d {4}' \
            .format(STUB_BLUEPRINT_FILENAME, STUB_ARCHIVE_LOCATION,
                    STUB_INPUTS, STUB_BLUEPRINT_ID,
                    STUB_DEPLOYMENT_ID)

        self.assert_method_called(
            cli_command=command,
            module=commands.deployments,
            function_name='create',
            args=[STUB_BLUEPRINT_ID, STUB_DEPLOYMENT_ID, [STUB_INPUTS]]
        )

    @patch('cloudify_cli.commands.blueprints.publish_archive')
    @patch('cloudify_cli.commands.executions.start')
    def test_default_inputs_file_path(self, *_):

        # create an `inputs.yaml` file in the cwd.
        inputs_path = os.path.join(utils.get_cwd(), 'inputs.yaml')
        os.mknod(inputs_path)

        command = \
            'cfy install -n {0} --archive-location={1} ' \
            '-b {2} -d {3}' \
            .format(STUB_BLUEPRINT_FILENAME, STUB_ARCHIVE_LOCATION,
                    STUB_BLUEPRINT_ID, STUB_DEPLOYMENT_ID)

        self.assert_method_called(
            cli_command=command,
            module=commands.deployments,
            function_name='create',
            args=[STUB_BLUEPRINT_ID,
                  STUB_DEPLOYMENT_ID,
                  DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND]
        )

    @patch('cloudify_cli.commands.blueprints.publish_archive')
    @patch('cloudify_cli.commands.deployments.create')
    def test_default_workflow_name(self, *_):

        command = \
            'cfy install -n {0} --archive-location={1} ' \
            '--inputs={2} -d {3} --parameters {4}' \
            .format(STUB_BLUEPRINT_FILENAME, SAMPLE_ARCHIVE_PATH,
                    STUB_INPUTS, STUB_DEPLOYMENT_ID, STUB_PARAMETERS)

        self.assert_method_called(
            cli_command=command,
            module=commands.executions,
            function_name='start',
            kwargs={'workflow_id': DEFAULT_INSTALL_WORKFLOW,
                    'deployment_id': STUB_DEPLOYMENT_ID,
                    'timeout': STUB_TIMEOUT,
                    'force': STUB_FORCE,
                    'allow_custom_parameters':
                        STUB_ALLOW_CUSTOM_PARAMETERS,
                    'include_logs': STUB_INCLUDE_LOGS,
                    'parameters': [STUB_PARAMETERS],
                    'json': False
                    }
        )

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.create')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_blueprints_upload_custom_arguments(self,
                                                blueprints_upload_mock,
                                                *_):
        command = \
            'cfy install -p {0} -b {1} --validate'\
            .format(SAMPLE_BLUEPRINT_PATH,
                    STUB_BLUEPRINT_ID)

        cli_runner.run_cli(command)

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

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.create')
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

        cli_runner.run_cli(command)

        blueprints_publish_archive_mock.assert_called_with(
            STUB_ARCHIVE_LOCATION,
            STUB_BLUEPRINT_FILENAME,
            STUB_BLUEPRINT_ID
        )

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.blueprints.publish_archive')
    @patch('cloudify_cli.commands.deployments.create')
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
                    STUB_INPUTS)

        cli_runner.run_cli(command)

        deployments_create_mock.assert_called_with(
            STUB_BLUEPRINT_ID,
            STUB_DEPLOYMENT_ID,
            [STUB_INPUTS]
        )

    @patch('cloudify_cli.commands.deployments.create')
    @patch('cloudify_cli.commands.blueprints.publish_archive')
    @patch('cloudify_cli.commands.executions.start')
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

        cli_runner.run_cli(command)

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

        cli_runner.run_cli(install_command)

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

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.create')
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

        self.assertRaises(CloudifyCliError,
                          cli_runner.run_cli,
                          path_and_filename_cmd
                          )
        self.assertRaises(CloudifyCliError,
                          cli_runner.run_cli,
                          path_and_archive_cmd
                          )
        self.assertRaises(CloudifyCliError,
                          cli_runner.run_cli,
                          path_and_filename_and_archive_cmd
                          )

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.create')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_auto_generate_ids_generates_suffixed_ids_in_upload_mode(
            self,
            blueprints_upload_mock,
            deployments_create_mock,
            *_):

        upload_mode_command = 'cfy install -b bid -d did -g'

        tmp_blueprint_path = os.path.join(self.original_utils_get_cwd(),
                                          DEFAULT_BLUEPRINT_PATH)

        # create a tmp file representing a blueprint to upload
        open(tmp_blueprint_path, 'w+').close()

        cli_runner.run_cli(upload_mode_command)

        blueprints_upload_blueprint_id_argument = \
            blueprints_upload_mock.call_args_list[0][0][1]

        deployments_create_deployment_id_argument = \
            deployments_create_mock.call_args_list[0][0][1]

        self.assertTrue(blueprints_upload_blueprint_id_argument
                        .startswith('bid_'))
        self.assertTrue(deployments_create_deployment_id_argument
                        .startswith('did_'))

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.create')
    @patch('cloudify_cli.commands.blueprints.publish_archive')
    def test_auto_generate_ids_generates_suffixed_ids_in_publish_archive_mode(
            self,
            blueprints_publish_archive_mock,
            deployments_create_mock,
            *_):

        publish_archive_mode_command = \
            'cfy install -b bid -d did -g -l {0}'.format(STUB_ARCHIVE_LOCATION)

        cli_runner.run_cli(publish_archive_mode_command)

        blueprints_publish_archive_blueprint_id_argument = \
            blueprints_publish_archive_mock.call_args_list[0][0][2]

        deployments_create_deployment_id_argument = \
            deployments_create_mock.call_args_list[0][0][1]

        self.assertTrue(blueprints_publish_archive_blueprint_id_argument
                        .startswith('bid_'))
        self.assertTrue(deployments_create_deployment_id_argument
                        .startswith('did_'))

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.create')
    @patch('cloudify_cli.commands.blueprints.publish_archive')
    @patch('cloudify_cli.commands.install_module._generate_suffixed_id')
    @patch('cloudify_cli.utils.is_auto_generate_ids')
    def test_auto_generate_ids_in_install(self,
                                          mock_is_auto_generate_ids,
                                          mock_generate_suffixed_id,
                                          *_):
        auto_generate_ids_command = \
            'cfy install -l {0} -g'.format(SAMPLE_ARCHIVE_PATH)

        dont_auto_generate_ids_command = \
            'cfy install -l {0}'.format(SAMPLE_ARCHIVE_PATH)

        mock_is_auto_generate_ids.return_value = False

        cli_runner.run_cli(auto_generate_ids_command)
        self.assertEqual(mock_generate_suffixed_id.call_count, 2)

        cli_runner.run_cli(dont_auto_generate_ids_command)
        self.assertEqual(mock_generate_suffixed_id.call_count, 2)

        mock_is_auto_generate_ids.return_value = True

        cli_runner.run_cli(auto_generate_ids_command)
        self.assertEqual(mock_generate_suffixed_id.call_count, 4)

        cli_runner.run_cli(dont_auto_generate_ids_command)
        self.assertEqual(mock_generate_suffixed_id.call_count, 6)

    @patch('cloudify_cli.utils.is_auto_generate_ids')
    def test_auto_generate_ids_return_value(self, mock_is_auto_generate_ids):

        mock_is_auto_generate_ids.return_value = False
        self.assertFalse(commands.install_module._auto_generate_ids(False))
        self.assertTrue(commands.install_module._auto_generate_ids(True))

        mock_is_auto_generate_ids.return_value = True
        self.assertTrue(commands.install_module._auto_generate_ids(False))
        self.assertTrue(commands.install_module._auto_generate_ids(True))

    @patch('cloudify_cli.commands.executions.start')
    @patch('cloudify_cli.commands.deployments.create')
    def test_default_blueprint_path_does_not_exist(self, *_):

        start_of_file_does_not_exist_message = \
            'Your blueprint was not found in the path:'

        self.assertRaisesRegexp(CloudifyCliError,
                                start_of_file_does_not_exist_message,
                                cli_runner.run_cli,
                                'cfy install')

        tmp_blueprint_path = os.path.join(utils.get_cwd(),
                                          DEFAULT_BLUEPRINT_PATH)

        start_of_permission_denied_message = \
            'A problem was encountered while trying to open the path'

        open(tmp_blueprint_path, 'w').close()
        os.chmod(tmp_blueprint_path, 0)

        self.assertRaisesRegexp(CloudifyCliError,
                                start_of_permission_denied_message,
                                cli_runner.run_cli,
                                'cfy install')
