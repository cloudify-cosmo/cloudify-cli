########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

"""
Tests all commands that start with 'cfy plugins'
"""
import tarfile
import os
import tempfile
import shutil

from mock import MagicMock

from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest
from cloudify_rest_client.plugins import Plugin


class PluginsTest(CliCommandTest):

    def setUp(self):
        super(PluginsTest, self).setUp()
        self._create_cosmo_wd_settings()

    def test_plugins_list(self):
        self.client.plugins.list = MagicMock(return_value=[])
        cli_runner.run_cli('cfy plugins list')

    def test_plugin_get(self):
        self.client.plugins.get = MagicMock(
            return_value=Plugin({'id': 'id',
                                 'package_name': 'dummy',
                                 'package_version': '1.2',
                                 'supported_platform': 'any',
                                 'distribution_release': 'trusty',
                                 'distribution': 'ubuntu',
                                 'uploaded_at': 'now'}))

        cli_runner.run_cli('cfy plugins get -p some_id')

    def test_plugins_delete(self):
        self.client.plugins.delete = MagicMock()
        cli_runner.run_cli('cfy plugins delete -p a-plugin-id')

    def test_plugins_upload(self):
        self.client.plugins.upload = MagicMock()
        plugin_dest = os.path.join(tempfile.gettempdir(), 'plugin.tar.gz')
        try:
            self.make_sample_plugin(plugin_dest)
            cli_runner.run_cli('cfy plugins upload -p '
                               '{0}'.format(plugin_dest))
        finally:
            shutil.rmtree(plugin_dest, ignore_errors=True)

    def test_plugins_download(self):
        self.client.plugins.download = MagicMock(return_value='some_file')
        cli_runner.run_cli('cfy plugins download -p a-plugin-id')

    def make_sample_plugin(self, plugin_dest):
        temp_folder = tempfile.mkdtemp()
        with open(os.path.join(temp_folder, 'package.json'), 'w') as f:
            f.write('{}')
        _make_tarfile(plugin_dest, temp_folder)


def _make_tarfile(output_filename, source_dir, write_type='w'):
    with tarfile.open(output_filename, write_type) as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))
