import os

from mock import patch


from .test_base import CliCommandTest
from .constants import SAMPLE_BLUEPRINT_PATH, \
    SAMPLE_ARCHIVE_PATH, STUB_BLUEPRINT_ID, STUB_DIRECTORY_NAME, \
    SAMPLE_ARCHIVE_URL, STUB_BLUEPRINT_FILENAME, SAMPLE_INPUTS_PATH, \
    STUB_DEPLOYMENT_ID, STUB_PARAMETERS, STUB_WORKFLOW, STUB_TIMEOUT, \
    BLUEPRINTS_DIR, DEFAULT_BLUEPRINT_FILE_NAME


class InstallTest(CliCommandTest):

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.blueprints.upload')
    @patch('cloudify_cli.commands.deployments.manager_create')
    def test_use_blueprints_upload_mode(self,
                                        executions_start_mock,
                                        blueprints_upload_mock,
                                        deployments_create_mock):
        self.invoke(
            'cfy install {0}'.format(SAMPLE_BLUEPRINT_PATH),
            context='manager'
        )

        self.assertTrue(executions_start_mock.called)
        self.assertTrue(blueprints_upload_mock.called)
        self.assertTrue(deployments_create_mock.called)

    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    @patch('cloudify_cli.commands.blueprints.upload')
    def test_blueprint_filename_default_value(self,
                                              blueprints_upload_mock, *_):
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

        self.assertDictEqual(deployment_create_args, {
            'blueprint_id': unicode(STUB_BLUEPRINT_ID),
            'deployment_id': unicode(STUB_BLUEPRINT_ID),
            'inputs': {'key1': 'val1', 'key2': 'val2'},
            'skip_plugins_validation': False,
            'tenant_name': None,
            'visibility': 'tenant'
        }
                             )

    @patch('cloudify_cli.commands.blueprints.upload')
    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_create')
    def test_custom_deployment_id(self, deployment_create_mock, *_):

        command = 'cfy install -n {0} {1} --inputs={2} -b {3} -d {4}'\
            .format(
                STUB_BLUEPRINT_FILENAME,
                SAMPLE_BLUEPRINT_PATH,
                SAMPLE_INPUTS_PATH,
                STUB_BLUEPRINT_ID,
                STUB_DEPLOYMENT_ID
            )

        self.invoke(command, context='manager')
        deployment_create_args = deployment_create_mock.call_args_list[0][1]

        self.assertDictEqual(deployment_create_args, {
            'blueprint_id': unicode(STUB_BLUEPRINT_ID),
            'deployment_id': unicode(STUB_DEPLOYMENT_ID),
            'inputs': {'key1': 'val1', 'key2': 'val2'},
            'skip_plugins_validation': False,
            'tenant_name': None,
            'visibility': 'tenant'
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
                'json_output': False,
                'parameters': {u'key': u'value'},
                'workflow_id': u'install',
                'timeout': 900,
                'tenant_name': None
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
                'validate': True,
                'tenant_name': None,
                'visibility': 'tenant'
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
            inputs={'key1': 'val1', 'key2': 'val2'},
            tenant_name=None,
            visibility='tenant',
            skip_plugins_validation=False
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
            '--json-output' \
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
            json_output=True,
            tenant_name=None
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
                'parameters': {},
                'blueprint_id': 'local',
                'allow_custom_parameters': False,
                'workflow_id': 'install',
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
                'inputs': {},
                'blueprint_id': 'local',
                'blueprint_path': unicode(blueprint_path),
                'install_plugins': False
            }
        )

    @patch('cloudify_cli.commands.executions.local_start')
    @patch('cloudify_cli.commands.init.init')
    def test_local_install_validate(self, *_):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )
        outcome = self.invoke(
            'cfy install {0} --validate'.format(blueprint_path),
            context='local'
        )

        outcome = [o.strip() for o in outcome.logs.split('\n')]
        self.assertIn('Blueprint validated successfully', outcome)

    @patch('cloudify_cli.commands.executions.local_start')
    @patch('cloudify_cli.commands.init.init')
    def test_local_install_custom_values(self, init_mock, _):
        self.invoke(
            'cfy install {0} -i key=value --install-plugins'
            .format(SAMPLE_ARCHIVE_PATH), context='local')

        args = init_mock.call_args_list[0][1]
        self.assertEqual(args['inputs'], {u'key': u'value'})
        self.assertEqual(args['install_plugins'], True)
