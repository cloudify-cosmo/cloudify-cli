########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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
Tests 'cfy bootstrap'
"""

from mock import patch

from cloudify_cli import common
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest, BLUEPRINTS_DIR


class BootstrapTest(CliCommandTest):

    def test_bootstrap(self):

        provider_context = {}
        provider_name = None

        def mock_create_context(_name, _context):
            global provider_context
            provider_context = _context
            global provider_name
            provider_name = _name

        def mock_get_context(_include=None):
            global provider_name
            global provider_context
            return {
                'name': provider_name,
                'context': provider_context
            }

        self.client.manager.create_context = mock_create_context
        self.client.manager.get_context = mock_get_context

        cli_runner.run_cli(
            'cfy init -p cloudify_mock_provider_with_cloudify_prefix'
        )
        cli_runner.run_cli('cfy bootstrap')

        context = self.client.manager.get_context()

        # see provision @cloudify_mock_provider_with_cloudify_prefix.py
        self.assertEquals('cloudify_mock_provider_with_cloudify_prefix',
                          context['name'])
        self.assertEquals('value', context['context']['key'])

    def test_bootstrap_install_plugins(self):

        cli_runner.run_cli('cfy init')
        blueprint_path = '{0}/local/{1}.yaml'\
                         .format(BLUEPRINTS_DIR,
                                 'blueprint_with_plugins')
        self.assert_method_called(
            cli_command='cfy bootstrap --install-plugins -p {0}'
                        .format(blueprint_path),
            module=common,
            function_name='install_blueprint_plugins',
            kwargs={'blueprint_path': blueprint_path}
        )