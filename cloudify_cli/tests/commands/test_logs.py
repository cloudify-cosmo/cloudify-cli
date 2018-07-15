from ... import ssh
from mock import patch
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

    def __side_effect_mock_function__(self, *args, **kwargs):
        pass

    @patch('cloudify_cli.ssh.get_file_from_manager')
    @patch('cloudify_cli.ssh.run_command_on_manager')
    @patch('cloudify_cli.commands.logs._archive_logs',
           return_value='../resources/mocks/mock_tar.tar')
    def test_download_with_no_output_path(self,
                                          _archive_logs_mock,
                                          run_command_on_manager_mock,
                                          get_file_from_manager_mock):
        profile = self.use_manager()
        ssh.profile = profile
        run_command_on_manager_mock.side_effect = \
            self.__side_effect_mock_function__
        get_file_from_manager_mock.side_effect = \
            self.__side_effect_mock_function__
        outcome = self.invoke('cfy logs download')
        self.assertNotIn('Downloading archive to: None', outcome.logs)

    @patch('cloudify_cli.ssh.get_file_from_manager')
    @patch('cloudify_cli.ssh.run_command_on_manager')
    @patch('cloudify_cli.commands.logs._archive_logs',
           return_value='../resources/mocks/mock_tar.tar')
    def test_download_with_no_output_path_all_nodes(
            self,
            _archive_logs_mock,
            run_command_on_manager_mock,
            get_file_from_manager_mock):
        cluster = [
            {"manager_ip": "10.0.0.1", "ssh_user": "test", "ssh_key": "key"},
            {"manager_ip": "10.0.0.2", "ssh_user": "test", "ssh_key": "key"}
        ]
        profile = self.use_manager(cluster=cluster)
        ssh.profile = profile
        run_command_on_manager_mock.side_effect = \
            self.__side_effect_mock_function__
        get_file_from_manager_mock.side_effect = \
            self.__side_effect_mock_function__
        outcome = self.invoke('cfy logs download --all-nodes')
        self.assertNotIn('Downloading archive to: None', outcome.logs)
