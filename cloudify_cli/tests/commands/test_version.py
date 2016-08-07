import mock

from .test_base import CliCommandTest


def manager_data():
    return {
        'date': '', 'commit': '',
        'version': '3.4.0',
        'build': '85',
        'ip': '10.10.1.10'
    }


class VersionTest(CliCommandTest):

    def test_version(self):
        outcome = self.invoke('cfy --version')
        self.assertIn('Cloudify CLI', outcome.logs)

    @mock.patch('cloudify_cli.env.is_manager_active', return_value=True)
    @mock.patch('cloudify_cli.env.get_manager_version_data',
                return_value=manager_data())
    def test_version_with_manager(self, *_):
        outcome = self.invoke('cfy --version')
        self.assertIn('Cloudify Manager', outcome.logs)
        self.assertIn('ip=10.10.1.10', outcome.logs)
