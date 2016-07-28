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

import os

from mock import patch

from ... import utils
from ...exceptions import CloudifyCliError

from ...constants import DEFAULT_TIMEOUT
from ...constants import DEFAULT_INSTALL_WORKFLOW
from ...constants import DEFAULT_BLUEPRINT_FILE_NAME
from ...constants import DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND

from .test_cli_command import CliCommandTest
from .test_cli_command import BLUEPRINTS_DIR


STUB_TIMEOUT = 900
STUB_FORCE = False
STUB_INCLUDE_LOGS = False
STUB_WORKFLOW = 'my_workflow'
STUB_PARAMETERS = 'key=value'
STUB_BLUEPRINT_ID = 'blueprint_id'
STUB_DIRECTORY_NAME = 'helloworld'
STUB_DEPLOYMENT_ID = 'deployment_id'
STUB_ALLOW_CUSTOM_PARAMETERS = False
STUB_ARCHIVE_LOCATION = 'archive.zip'
STUB_BLUEPRINT_FILENAME = 'my_blueprint.yaml'
SAMPLE_INPUTS_PATH = os.path.join(
    BLUEPRINTS_DIR, STUB_DIRECTORY_NAME, 'inputs.yaml')
SAMPLE_BLUEPRINT_PATH = os.path.join(
    BLUEPRINTS_DIR, STUB_DIRECTORY_NAME, DEFAULT_BLUEPRINT_FILE_NAME)
SAMPLE_ARCHIVE_URL = 'https://github.com/cloudify-cosmo/' \
                     'cloudify-hello-world-example/archive/master.zip'
SAMPLE_ARCHIVE_PATH = os.path.join(BLUEPRINTS_DIR, 'helloworld.zip')


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
    def test_blueprint_path_default_value(self, *_):

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
                    STUB_INPUTS)

        self.invoke(command, context='manager')

        deployments_create_mock.assert_called_with(
            STUB_BLUEPRINT_ID,
            STUB_DEPLOYMENT_ID,
            [STUB_INPUTS]
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

        self.assertRaises(CloudifyCliError,
                          self.invoke,
                          path_and_filename_cmd
                          )
        self.assertRaises(CloudifyCliError,
                          self.invoke,
                          path_and_archive_cmd
                          )
        self.assertRaises(CloudifyCliError,
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

        self.assertRaisesRegexp(CloudifyCliError,
                                start_of_file_does_not_exist_message,
                                self.invoke,
                                'cfy install')

        tmp_blueprint_path = os.path.join(utils.get_cwd(),
                                          DEFAULT_BLUEPRINT_FILE_NAME)

        start_of_permission_denied_message = \
            'A problem was encountered while trying to open'

        open(tmp_blueprint_path, 'w').close()
        os.chmod(tmp_blueprint_path, 0)

        self.assertRaisesRegexp(CloudifyCliError,
                                start_of_permission_denied_message,
                                self.invoke,
                                'cfy install')
