import os

from mock import patch

from cloudify_rest_client import deployments

from ... import local
from .test_base import CliCommandTest
from ...constants import DEFAULT_UNINSTALL_WORKFLOW, \
    DEFAULT_TIMEOUT, DEFAULT_PARAMETERS
from .constants import BLUEPRINTS_DIR, DEFAULT_BLUEPRINT_FILE_NAME


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
            deployment_id='did',
            timeout=DEFAULT_TIMEOUT,
            force=False,
            include_logs=True,
            allow_custom_parameters=False,
            parameters=DEFAULT_PARAMETERS,
            json_output=False,
            tenant_name=None
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
                            '--json-output ' \
                            '--tenant-name tenant_name'

        self.invoke(uninstall_command, context='manager')

        executions_start_mock.assert_called_with(
            workflow_id=u'my_uninstall',
            deployment_id=u'did',
            timeout=1987,
            force=False,
            include_logs=True,
            allow_custom_parameters=True,
            parameters={'key': 'value'},
            json_output=True,
            tenant_name='tenant_name'
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
        mock_blueprints_delete.assert_called_with(blueprint_id=u'bid',
                                                  tenant_name=None)

    @patch('cloudify_cli.commands.blueprints.delete')
    @patch('cloudify_cli.env.get_rest_client')
    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_delete')
    def test_deployments_delete_arguments(self, deployments_delete_mock, *_):

        self.invoke('cfy uninstall did', context='manager')

        deployments_delete_mock.assert_called_with(
            deployment_id=u'did',
            force=False,
            tenant_name=None
        )

    @patch('cloudify_cli.env.get_rest_client')
    @patch('cloudify_cli.commands.executions.manager_start')
    @patch('cloudify_cli.commands.deployments.manager_delete')
    @patch('cloudify_cli.commands.blueprints.delete')
    def test_blueprint_is_deleted(self, blueprints_delete_mock, *_):

        self.invoke('cfy uninstall did', context='manager')
        self.assertTrue(blueprints_delete_mock.called)

    @patch('cloudify_cli.commands.executions.local_start')
    def test_local_uninstall_default_values(self, local_start_mock):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )
        self.invoke('cfy init {0}'.format(blueprint_path))
        self.invoke('cfy uninstall -b local', context='local')

        args = local_start_mock.call_args_list[0][1]
        self.assertDictEqual(
            args,
            {
                'parameters': DEFAULT_PARAMETERS,
                'blueprint_id': 'local',
                'allow_custom_parameters': False,
                'workflow_id': 'uninstall',
                'task_retries': 0,
                'task_retry_interval': 1,
                'task_thread_pool_size': 1
            }
        )

    @patch('cloudify_cli.commands.executions.local_start')
    def test_local_uninstall_custom_values(self, local_start_mock):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )
        self.invoke('cfy init {0}'.format(blueprint_path))
        self.invoke('cfy uninstall'
                    ' -b local'
                    ' -w my_uninstall'
                    ' --parameters key=value'
                    ' --allow-custom-parameters'
                    ' --task-retries 14'
                    ' --task-retry-interval 7'
                    ' --task-thread-pool-size 87',
                    context='local')

        args = local_start_mock.call_args_list[0][1]
        self.assertDictEqual(
            args,
            {
                'parameters': {u'key': u'value'},
                'blueprint_id': 'local',
                'allow_custom_parameters': True,
                'workflow_id': u'my_uninstall',
                'task_retries': 14,
                'task_retry_interval': 7,
                'task_thread_pool_size': 87
            }
        )

    def test_uninstall_removes_local_storage_dir(self):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )
        storage_dir = os.path.join(local.storage_dir(), 'local')

        # Using run_test_op_on_nodes because the blueprint doesn't have
        # install/uninstall workflows
        self.invoke(
            'cfy install {0} -b local -w run_test_op_on_nodes'
            .format(blueprint_path),
            context='local'
        )
        self.assertTrue(os.path.isdir(storage_dir))

        self.invoke(
            'cfy uninstall -b local -w run_test_op_on_nodes',
            context='local',
        )
        self.assertFalse(os.path.isdir(storage_dir))
