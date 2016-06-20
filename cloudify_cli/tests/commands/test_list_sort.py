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
Tests the sorting in all list sub-commands
"""

from cloudify_cli.config.parser_config import parser_config

from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class ListSortTest(CliCommandTest):

    def setUp(self):
        super(ListSortTest, self).setUp()
        self._create_cosmo_wd_settings()
        self.resources_types = {
            'plugins': self.client.plugins,
            'deployments': self.client.deployments,
            'nodes': self.client.nodes,
            'node-instances': self.client.node_instances,
            'blueprints': self.client.blueprints,
            'snapshots': self.client.snapshots,
            'executions': self.client.executions
        }
        self.count_mock_calls = 0

        self.original_lists = {}
        for r in self.resources_types:
            self.original_lists[r] = self.resources_types[r].list

    def tearDown(self):
        for r in self.resources_types:
            self.resources_types[r].list = self.original_lists[r]
        super(ListSortTest, self).tearDown()

    def test_list_sort(self):
        for r in self.resources_types:
            self._set_mock_list(r, 'order')
            cli_runner.run_cli('cfy {0} list --sort-by order'.format(r))
        self.assertEqual(len(self.resources_types), self.count_mock_calls)

    def test_list_sort_reverse(self):
        for r in self.resources_types:
            self._set_mock_list(r, 'order', descending=True)
            cli_runner.run_cli('cfy {0} list -s order --desc'.format(r))
        self.assertEqual(len(self.resources_types), self.count_mock_calls)

    def test_list_sort_default(self):
        for r in self.resources_types:
            self._set_mock_list(
                r,
                parser_config()['commands'][r]['sub_commands']['list']
                ['arguments']['-s,--sort-by']['default']
            )
            cli_runner.run_cli('cfy {0} list'.format(r))
        self.assertEqual(len(self.resources_types), self.count_mock_calls)

    def test_list_sort_default_reverse(self):
        for r in self.resources_types:
            self._set_mock_list(
                r,
                parser_config()['commands'][r]['sub_commands']['list']
                ['arguments']['-s,--sort-by']['default'],
                descending=True
            )
            cli_runner.run_cli('cfy {0} list --desc'.format(r))
        self.assertEqual(len(self.resources_types), self.count_mock_calls)

    def _set_mock_list(self, resource, sort, descending=False):
        def _mock_list(*_, **kwargs):
            self.count_mock_calls += 1
            self.assertEqual(sort, kwargs['sort'])
            self.assertEqual(descending, kwargs['is_descending'])
            return []

        self.resources_types[resource].list = _mock_list
