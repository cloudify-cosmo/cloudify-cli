import os
import yaml

from mock import MagicMock, patch

from ..test_base import CliCommandTest
from cloudify_rest_client import deployments
from cloudify_cli import env, utils, exceptions
from cloudify_cli.constants import DEFAULT_BLUEPRINT_FILE_NAME, \
    DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND, DEFAULT_TIMEOUT, \
    DEFAULT_UNINSTALL_WORKFLOW, DEFAULT_PARAMETERS
from ..constants import BLUEPRINTS_DIR, \
    SAMPLE_BLUEPRINT_PATH, SAMPLE_ARCHIVE_PATH, STUB_BLUEPRINT_ID, \
    STUB_DIRECTORY_NAME, SAMPLE_ARCHIVE_URL, STUB_BLUEPRINT_FILENAME, \
    SAMPLE_INPUTS_PATH, STUB_DEPLOYMENT_ID, STUB_PARAMETERS, STUB_WORKFLOW, \
    STUB_TIMEOUT


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

    def test_blueprint_validate_definitions_version_true(self):
        self.invoke(
            'cfy blueprints validate '
            '{0}/local/blueprint_validate_definitions_version.yaml'
            .format(BLUEPRINTS_DIR),
            err_str_segment='Failed to validate blueprint description'
        )

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

    def test_create_requirements(self):
        pass


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
            'cfy install {0} -b {1} --validate'\
            .format(SAMPLE_BLUEPRINT_PATH,
                    STUB_BLUEPRINT_ID)

        self.invoke(command, context='manager')
        blueprints_upload_args = blueprints_upload_mock.call_args_list[0][1]
        self.assertDictEqual(
            blueprints_upload_args,
            {
                'blueprint_filename': unicode(DEFAULT_BLUEPRINT_FILE_NAME),
                'blueprint_id': unicode(STUB_BLUEPRINT_ID),
                'blueprint_path': unicode(SAMPLE_BLUEPRINT_PATH),
                'validate': True
            }
        )

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_blueprints_publish_archive_custom_arguments(
            self,
            blueprints_upload_mock,
            *_):

        command = \
            'cfy install {0} -n {1} -b {2}' \
            .format(SAMPLE_ARCHIVE_PATH,
                    DEFAULT_BLUEPRINT_FILE_NAME,
                    STUB_BLUEPRINT_ID)

        self.invoke(command, context='manager')
        blueprints_upload_args = blueprints_upload_mock.call_args_list[0][1]

        self.assertEqual(
            blueprints_upload_args['blueprint_filename'],
            unicode(DEFAULT_BLUEPRINT_FILE_NAME)
        )

        self.assertEqual(
            blueprints_upload_args['blueprint_id'],
            unicode(STUB_BLUEPRINT_ID)
        )

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.blueprints.upload')
    @patch('cloudify_cli.commands.deployments.manager_create')
    def test_deployments_create_custom_arguments(self,
                                                 deployments_create_mock,
                                                 *_):
        # 'blueprints archive location mode' is used to prevent from dealing
        # with the fact that 'upload mode' needs the blueprint_path argument
        # to lead to an existing file
        command = \
            'cfy install {0} -b {1} -d {2} -i {3}' \
            .format(SAMPLE_ARCHIVE_PATH,
                    STUB_BLUEPRINT_ID,
                    STUB_DEPLOYMENT_ID,
                    SAMPLE_INPUTS_PATH)

        self.invoke(command, context='manager')

        deployments_create_mock.assert_called_with(
            blueprint_id=unicode(STUB_BLUEPRINT_ID),
            deployment_id=unicode(STUB_DEPLOYMENT_ID),
            inputs={'key1': 'val1', 'key2': 'val2'}
        )

    @patch('cloudify_cli.commands.deployments.manager_create')
    @patch('cloudify_cli.commands.blueprints.upload')
    @patch('cloudify_cli.commands.executions.manager_start')
    def test_executions_start_custom_parameters(self,
                                                executions_start_mock,
                                                *_):
        # 'blueprints archive location mode' is used to prevent from dealing
        # with the fact that 'upload mode' needs the blueprint_path argument
        # to lead to an existing file
        command = \
            'cfy install {0} ' \
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
            parameters={'key': 'value'},
            json=True
        )

    @patch('cloudify_cli.commands.install.manager')
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
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_mutually_exclusive_arguments(self, *_):

        path_and_filename_cmd = 'cfy install {0} -n {1}'.format(
            SAMPLE_BLUEPRINT_PATH,
            STUB_BLUEPRINT_FILENAME
        )

        self.assertRaises(
            exceptions.CloudifyCliError,
            self.invoke,
            path_and_filename_cmd,
            context='manager'
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