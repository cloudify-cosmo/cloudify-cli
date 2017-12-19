import shutil
import tempfile

import wagon
from mock import MagicMock

from .test_base import CliCommandTest

from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.constants import DEFAULT_TENANT_NAME

from cloudify_rest_client import plugins


class PluginsTest(CliCommandTest):

    def setUp(self):
        super(PluginsTest, self).setUp()
        self.use_manager()

    def test_plugins_list(self):
        self.client.plugins.list = MagicMock(return_value=[])
        self.invoke('cfy plugins list')
        self.invoke('cfy plugins list -t dummy_tenant')
        self.invoke('cfy plugins list -a')

    def test_plugin_get(self):
        self.client.plugins.get = MagicMock(
            return_value=plugins.Plugin({'id': 'id',
                                         'package_name': 'dummy',
                                         'package_version': '1.2',
                                         'supported_platform': 'any',
                                         'distribution_release': 'trusty',
                                         'distribution': 'ubuntu',
                                         'uploaded_at': 'now',
                                         'resource_availability': 'private',
                                         'created_by': 'admin',
                                         'tenant_name': DEFAULT_TENANT_NAME}))

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
        plugin_dest_dir = tempfile.mkdtemp()
        try:
            plugin_path = wagon.create(
                'pip',
                archive_destination_dir=plugin_dest_dir
            )
            self.invoke('cfy plugins upload {0}'.format(plugin_path))
        finally:
            shutil.rmtree(plugin_dest_dir, ignore_errors=True)

    def test_plugins_download(self):
        self.client.plugins.download = MagicMock(return_value='some_file')
        self.invoke('cfy plugins download a-plugin-id')

    def test_plugins_set_global(self):
        self.client.plugins.set_global = MagicMock()
        self.invoke('cfy plugins set-global a-plugin-id')

    def test_plugins_set_availability(self):
        self.client.plugins.set_availability = MagicMock()
        self.invoke('cfy plugins set-availability a-plugin-id -a global')

    def test_plugins_set_availability_invalid_argument(self):
        self.invoke('cfy plugins set-availability a-plugin-id -a private',
                    err_str_segment='Invalid availability: `private`',
                    exception=CloudifyCliError)

    def test_plugins_set_availability_missing_argument(self):
        outcome = self.invoke('cfy plugins set-availability a-plugin-id',
                              err_str_segment='2',
                              exception=SystemExit)
        self.assertIn('Missing option "-a" / "--availability"', outcome.output)

    def test_blueprints_set_availability_wrong_argument(self):
        outcome = self.invoke('cfy plugins set-availability a-plugin-id -g',
                              err_str_segment='2',
                              exception=SystemExit)
        self.assertIn('Error: no such option: -g', outcome.output)

    def test_plugins_upload_mutually_exclusive_arguments(self):
        outcome = self.invoke(
            'cfy plugins upload --private-resource -a tenant',
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        self.assertIn('mutually exclusive with arguments:', outcome.output)

    def test_plugins_upload_invalid_argument(self):
        self.invoke('cfy plugins upload -a bla plugin_path',
                    err_str_segment='Invalid availability: `bla`',
                    exception=CloudifyCliError)

    def test_plugins_upload_with_availability(self):
        self.client.plugins.upload = MagicMock()
        self.invoke('cfy plugins upload -a private plugin_path')
