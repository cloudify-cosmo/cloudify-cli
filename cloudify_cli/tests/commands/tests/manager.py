import os
import platform
from distutils import spawn
from mock import patch, MagicMock, call

from cloudify_cli import common, exceptions, env
from cloudify_cli.bootstrap import bootstrap
from cloudify_cli.commands.ssh import _validate_env
from cloudify_cli.constants import DEFAULT_BLUEPRINT_FILE_NAME, API_VERSION
from ... import cfy
from ..constants import BLUEPRINTS_DIR, \
    SAMPLE_BLUEPRINT_PATH, SAMPLE_INPUTS_PATH, TEST_WORK_DIR, SSL_PORT
from ..mocks import mock_activated_status, \
    mock_is_timeout
from ..test_base import CliCommandTest, \
    BaseUpgradeTest
from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.exceptions import UserUnauthorizedError, \
    CloudifyClientError


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
        command = ('cfy bootstrap --skip-validations {0} '
                   '-i "some_input=some_value"'.format(
                    SAMPLE_BLUEPRINT_PATH))

        self.assert_method_called(
            command=command,
            module=common,
            function_name='add_ignore_bootstrap_validations_input',
            args=[{
                u'some_input': u'some_value',
                'key1': 'default_val1',
                'key2': 'default_val2',
                'key3': 'default_val3'
            }]
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

    def test_init_invalid_blueprint_path(self):
        self.invoke(
            'cfy init idonotexist.yaml',
            exception=IOError,
            should_fail=True
        )

    def test_init_with_inputs(self):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )
        command = 'cfy init {0} -i {1} -i key3=val3'.format(
            blueprint_path,
            SAMPLE_INPUTS_PATH
        )

        self.invoke(command)
        self.register_commands()

        output = self.invoke('cfy deployments inputs').logs.split('\n')
        self.assertIn('  "key1": "val1", ', output)
        self.assertIn('  "key2": "val2", ', output)
        self.assertIn('  "key3": "val3"', output)

    def test_no_init(self):
        cfy.purge_dot_cloudify()
        self.invoke('cfy profiles list',
                    err_str_segment='Cloudify environment is not initalized',
                    # TODO: put back
                    # possible_solutions=[
                    #     "Run 'cfy init' in this directory"
                    # ]
                    )


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
        self.use_manager()
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