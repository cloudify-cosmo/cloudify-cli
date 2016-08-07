import os

from mock import patch


from ... import utils, exceptions
from .test_base import CliCommandTest
from .constants import SAMPLE_BLUEPRINT_PATH, \
    SAMPLE_ARCHIVE_PATH, STUB_BLUEPRINT_ID, STUB_DIRECTORY_NAME, \
    SAMPLE_ARCHIVE_URL, STUB_BLUEPRINT_FILENAME, SAMPLE_INPUTS_PATH, \
    STUB_DEPLOYMENT_ID, STUB_PARAMETERS, STUB_WORKFLOW, STUB_TIMEOUT, \
    BLUEPRINTS_DIR, DEFAULT_BLUEPRINT_FILE_NAME
from ...constants import DEFAULT_INPUTS_PATH_FOR_INSTALL_COMMAND, \
    DEFAULT_TIMEOUT


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

        tmp_blueprint_path = os.path.join('/tmp',
                                          DEFAULT_BLUEPRINT_FILE_NAME)

        install_upload_mode_command = \
            'cfy install -n {0}'.format(DEFAULT_BLUEPRINT_FILE_NAME)

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
        # TODO: supposed to fail, because we're providing a YAML path
        # and a filename - should be mutually exclusive
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
        self.invoke(
            'cfy install',
            context='manager',
            err_str_segment='Could not find `blueprint.yaml` in the cwd'
        )

        self.invoke(
            'cfy install',
            context='local',
            err_str_segment='Could not find `blueprint.yaml` in the cwd'
        )

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    def test_default_blueprint_path_bad_blueprint(self, *_):

        # TODO: This doesn't really put the blueprint in the same folder
        # and trying to put it there is dangerous (as cfy install uses
        # shutil.rmtree to clean up, and will likely remove actual code)
        tmp_blueprint_path = os.path.join(utils.get_cwd(),
                                          DEFAULT_BLUEPRINT_FILE_NAME)
        open(tmp_blueprint_path, 'w').close()
        os.chmod(tmp_blueprint_path, 0)

        self.invoke(
            'cfy install',
            context='manager',
            err_str_segment='A problem was encountered while trying to open'
        )

        self.invoke(
            'cfy install',
            context='local',
            err_str_segment='A problem was encountered while trying to open'
        )

    @patch('cloudify_cli.commands.executions.local_start')
    def test_local_install_default_start_values(self, local_start_mock):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )
        self.invoke('cfy install {0}'.format(blueprint_path), context='local')

        args = local_start_mock.call_args_list[0][1]
        self.assertDictEqual(
            args,
            {
                'parameters': None,
                'blueprint_id': u'local',
                'allow_custom_parameters': False,
                'workflow_id': u'install',
                'task_retries': 5,
                'task_retry_interval': 3,
                'task_thread_pool_size': 1
            }
        )

    @patch('cloudify_cli.commands.executions.local_start')
    def test_local_install_custom_start_values(self, local_start_mock):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )
        self.invoke('cfy install {0}'
                    ' -w my_install'
                    ' --parameters key=value'
                    ' --allow-custom-parameters'
                    ' --task-retries 14'
                    ' --task-retry-interval 7'
                    ' --task-thread-pool-size 87'
                    .format(blueprint_path), context='local')

        args = local_start_mock.call_args_list[0][1]
        self.assertDictEqual(
            args,
            {
                'parameters': {u'key': u'value'},
                'blueprint_id': u'local',
                'allow_custom_parameters': True,
                'workflow_id': u'my_install',
                'task_retries': 14,
                'task_retry_interval': 7,
                'task_thread_pool_size': 87
            }
        )

    @patch('cloudify_cli.commands.executions.local_start')
    @patch('cloudify_cli.commands.init.init')
    def test_local_install_default_values(self, init_mock, _):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )
        self.invoke('cfy install {0}'.format(blueprint_path), context='local')

        args = init_mock.call_args_list[0][1]
        self.assertDictEqual(
            args,
            {
                'inputs': None,
                'blueprint_id': u'local',
                'blueprint_path': unicode(blueprint_path),
                'install_plugins': False
            }
        )

    @patch('cloudify_cli.commands.executions.local_start')
    @patch('cloudify_cli.commands.init.init')
    def test_local_install_custom_values(self, init_mock, _):
        self.invoke(
            'cfy install {0} -i key=value --install-plugins'
            .format(SAMPLE_ARCHIVE_PATH), context='local')

        args = init_mock.call_args_list[0][1]
        self.assertEqual(args['inputs'], {u'key': u'value'})
        self.assertEqual(args['install_plugins'], True)