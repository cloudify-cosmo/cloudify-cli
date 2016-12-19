import os
import shutil
import tempfile

from mock import MagicMock

from .mocks import make_tarfile
from .test_base import CliCommandTest

from cloudify_rest_client import plugins


class PluginsTest(CliCommandTest):

    def setUp(self):
        super(PluginsTest, self).setUp()
        self.use_manager()

    def test_plugins_list(self):
        self.client.plugins.list = MagicMock(return_value=[])
        self.invoke('cfy plugins list')
        self.invoke('cfy plugins list -t dummy_tenant')

    def test_plugin_get(self):
        self.client.plugins.get = MagicMock(
            return_value=plugins.Plugin({'id': 'id',
                                         'package_name': 'dummy',
                                         'package_version': '1.2',
                                         'supported_platform': 'any',
                                         'distribution_release': 'trusty',
                                         'distribution': 'ubuntu',
                                         'uploaded_at': 'now',
                                         'permission': 'creator',
                                         'tenant_name': 'default_tenant'}))

        self.invoke('cfy plugins get some_id')

    def test_plugins_delete(self):
        self.client.plugins.delete = MagicMock()
        self.invoke('cfy plugins delete a-plugin-id')

    def test_plugins_delete_force(self):
        for flag in ['--force', '-f']:
            mock = MagicMock()
            self.client.plugins.delete = mock
            self.invoke('cfy plugins delete a-plugin-id {0}'.format(
                flag))
            mock.assert_called_once_with(plugin_id='a-plugin-id', force=True)

    def test_plugins_upload(self):
        self.client.plugins.upload = MagicMock()
        plugin_dest = os.path.join(tempfile.gettempdir(), 'plugin.tar.gz')
        try:
            self.make_sample_plugin(plugin_dest)
            self.invoke('cfy plugins upload {0}'.format(plugin_dest))
        finally:
            shutil.rmtree(plugin_dest, ignore_errors=True)

    def test_plugins_download(self):
        self.client.plugins.download = MagicMock(return_value='some_file')
        self.invoke('cfy plugins download a-plugin-id')

    def make_sample_plugin(self, plugin_dest):
        temp_folder = tempfile.mkdtemp()
        with open(os.path.join(temp_folder, 'package.json'), 'w') as f:
            f.write('{}')
        make_tarfile(plugin_dest, temp_folder)
