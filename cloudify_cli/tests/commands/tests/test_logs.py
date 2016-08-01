from ..test_base import CliCommandTest


class LogsTest(CliCommandTest):
    def test_with_empty_config(self):
        self.use_manager(user=None, port=None, key=None)
        self.invoke('cfy logs download',
                    'Manager User is not set '
                    'in working directory settings')

    def test_with_no_key(self):
        self.use_manager(user='test', port='22', host='127.0.0.1', key=None)
        self.invoke('cfy logs download',
                    'Manager Key is not set '
                    'in working directory settings')

    def test_with_no_user(self):
        self.use_manager(port='22', key='/tmp/test.pem', user=None)
        self.invoke('cfy logs download',
                    'Manager User is not set '
                    'in working directory settings')

    def test_with_no_port(self):
        self.use_manager(user='test', key='/tmp/test.pem', host='127.0.0.1', port=None)
        self.invoke('cfy logs download',
                    'Manager Port is not set '
                    'in working directory settings')

    def test_with_no_server(self):
        self.use_manager(user='test', key='/tmp/test.pem', host=None)
        self.invoke(
            'cfy logs download',
            err_str_segment='command is only available when using a manager')

    def test_purge_no_force(self):
        self.use_manager()
        # unlike the other tests, this drops on argparse raising
        # that the `-f` flag is required for purge, which is why
        # the exception message is actually the returncode from argparse.
        self.invoke('cfy logs purge', 'You must supply the `-f, --force`')