from ... import ssh
from .test_base import CliCommandTest


class LogsTest(CliCommandTest):
    def test_with_empty_config(self):
        profile = self.use_manager(
            ssh_user=None, ssh_port=None, ssh_key_path=None)
        ssh.profile = profile
        self.invoke('cfy logs download',
                    'Manager `ssh_user` is not set '
                    'in Cloudify CLI settings')

    def test_with_no_key(self):
        profile = self.use_manager(ssh_key_path=None)
        ssh.profile = profile
        self.invoke('cfy logs download',
                    'Manager `ssh_key` is not set '
                    'in Cloudify CLI settings')

    def test_with_no_user(self):
        profile = self.use_manager(ssh_user=None)
        ssh.profile = profile
        self.invoke('cfy logs download',
                    'Manager `ssh_user` is not set '
                    'in Cloudify CLI settings')

    def test_with_no_port(self):
        profile = self.use_manager(ssh_port=None)
        ssh.profile = profile
        self.invoke('cfy logs download',
                    'Manager `ssh_port` is not set '
                    'in Cloudify CLI settings')

    def test_purge_no_force(self):
        profile = self.use_manager()
        ssh.profile = profile
        # unlike the other tests, this drops on argparse raising
        # that the `-f` flag is required for purge, which is why
        # the exception message is actually the returncode from argparse.
        self.invoke('cfy logs purge', 'You must supply the `-f, --force`')
