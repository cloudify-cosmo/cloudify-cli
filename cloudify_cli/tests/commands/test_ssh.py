import os
import platform
from distutils import spawn

from ... import ssh
from ... import exceptions
from .test_base import CliCommandTest
from ...commands.ssh import _validate_env


class SshTest(CliCommandTest):

    def test_ssh_no_manager(self):
        self.invoke(
            'cfy ssh',
            'This command is only available when using a manager'
        )

    def test_ssh_with_empty_config(self):
        profile = self.use_manager(
            ssh_user=None,
            ssh_key_path=None,
            ssh_port=None
        )
        ssh.profile = profile
        self.invoke('cfy ssh',
                    'Manager `ssh_user` is not set '
                    'in Cloudify CLI settings')

    def test_ssh_with_no_key(self):
        profile = self.use_manager(ssh_key_path=None)
        ssh.profile = profile
        self.invoke('cfy ssh',
                    'Manager `ssh_key` is not set '
                    'in Cloudify CLI settings')

    def test_ssh_with_no_port(self):
        profile = self.use_manager(ssh_port=None)
        ssh.profile = profile
        self.invoke('cfy ssh',
                    'Manager `ssh_port` is not set '
                    'in Cloudify CLI settings')

    def test_ssh_with_no_user(self):
        profile = self.use_manager(ssh_user=None)
        ssh.profile = profile
        self.invoke('cfy ssh',
                    'Manager `ssh_user` is not set '
                    'in Cloudify CLI settings')

    def test_ssh_without_ssh_windows(self):
        platform.system = lambda: 'Windows'
        if os.name != 'nt':
            self.skipTest('Irrelevant on Linux')
        self.use_manager()
        spawn.find_executable = lambda x: None
        self.invoke('cfy ssh', 'ssh.exe not found')

    def test_ssh_without_ssh_linux(self):
        platform.system = lambda: 'Linux'
        if os.name == 'nt':
            self.skipTest('Irrelevant on Windows')
        self.use_manager()
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
