import os

from mock import MagicMock, patch

from ...commands import recover 
from ... import exceptions, env
from .test_base import CliCommandTest


class RecoverTest(CliCommandTest):

    def test_recover_no_force(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        fake_snapshot_path = os.path.join(env.CLOUDIFY_WORKDIR, 'sn.zip')
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
        key_path = os.path.join(env.CLOUDIFY_WORKDIR, 'key.pem')
        open(key_path, 'w').close()

        profile = self.use_manager(ssh_key_path=key_path)
        recover.profile = profile

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
        key_path = os.path.join(env.CLOUDIFY_WORKDIR, 'key.pem')
        fake_snapshot_path = os.path.join(env.CLOUDIFY_WORKDIR, 'sn.zip')
        open(fake_snapshot_path, 'w').close()

        self.use_manager(ssh_key_path=key_path)

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

        key_path = os.path.join(env.CLOUDIFY_WORKDIR, 'key.pem')
        fake_snapshot_path = os.path.join(env.CLOUDIFY_WORKDIR, 'sn.zip')
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
        fake_snapshot_path = os.path.join(env.CLOUDIFY_WORKDIR, 'sn.zip')
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

        key_path = os.path.join(env.CLOUDIFY_WORKDIR, 'key.pem')
        open(key_path, 'w').close()

        self.use_manager(ssh_key_path=key_path)

        try:
            os.environ['CLOUDIFY_MANAGER_PRIVATE_KEY_PATH'] = key_path
            self.invoke('cfy recover -f {0}'.format(key_path))
        finally:
            del os.environ['CLOUDIFY_MANAGER_PRIVATE_KEY_PATH']