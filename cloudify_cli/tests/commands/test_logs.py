from ... import ssh
from .test_base import CliCommandTest


class LogsTest(CliCommandTest):
    def test_with_empty_config(self):
        profile = self.use_manager(ssh_user=None, ssh_port=None, ssh_key_path=None)
        ssh.profile = profile
        self.invoke('cfy logs download',
                    'Manager User is not set '
                    'in working directory settings')

    def test_with_no_key(self):
        profile = self.use_manager(ssh_key_path=None)
        ssh.profile = profile
        self.invoke('cfy logs download',
                    'Manager Key is not set '
                    'in working directory settings')

    def test_with_no_port(self):
        settings = utils.CloudifyWorkingDirectorySettings()
        settings.set_management_user('test')
        settings.set_management_server('127.0.0.1')
        settings.set_management_key('/tmp/test.pem')
        self._create_cosmo_wd_settings(settings)
        self._assert_ex('cfy logs download',
                        'Management Port is not set '
                        'in working directory settings')

    def test_with_no_user(self):
        profile = self.use_manager(ssh_user=None)
        ssh.profile = profile
        self.invoke('cfy logs download',
                    'Manager User is not set '
                    'in working directory settings')

    def test_with_no_port(self):
        profile = self.use_manager(ssh_port=None)
        ssh.profile = profile
        self.invoke('cfy logs download',
                    'Manager Port is not set '
                    'in working directory settings')

    def test_purge_no_force(self):
        profile = self.use_manager()
        ssh.profile = profile
        # unlike the other tests, this drops on argparse raising
        # that the `-f` flag is required for purge, which is why
        # the exception message is actually the returncode from argparse.
        self.invoke('cfy logs purge', 'You must supply the `-f, --force`')