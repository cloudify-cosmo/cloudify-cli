from .test_base import CliCommandTest


class LogsTest(CliCommandTest):
    def test_with_empty_config(self):
        self.use_manager(ssh_user=None, ssh_port=None, ssh_key_path=None)
        self.invoke('cfy logs download',
                    'Manager User is not set '
                    'in working directory settings')

    def test_with_no_key(self):
        self.use_manager(ssh_key_path=None)
        self.invoke('cfy logs download',
                    'Manager Key is not set '
                    'in working directory settings')

    def test_with_no_user(self):
        self.use_manager(ssh_user=None)
        self.invoke('cfy logs download',
                    'Manager User is not set '
                    'in working directory settings')

    def test_with_no_port(self):
        self.use_manager(ssh_port=None)
        self.invoke('cfy logs download',
                    'Manager Port is not set '
                    'in working directory settings')

    def test_with_no_server(self):
        # TODO: this fails on use_manager...
        self.use_manager(manager_ip=None)
        self.invoke(
            'cfy logs download',
            err_str_segment='provide a profile name or activate a profile')

    def test_purge_no_force(self):
        self.use_manager()
        # unlike the other tests, this drops on argparse raising
        # that the `-f` flag is required for purge, which is why
        # the exception message is actually the returncode from argparse.
        self.invoke('cfy logs purge', 'You must supply the `-f, --force`')