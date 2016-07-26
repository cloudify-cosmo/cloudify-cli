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
from collections import namedtuple

from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


# Holds all information relevant for executing a a command
_resource = namedtuple('Resource', 'name,class_type,sort_order,context')


class ListSortTest(CliCommandTest):
    def setUp(self):
        super(ListSortTest, self).setUp()
        self.use_manager()
        self.resources = [
            _resource('plugins', self.client.plugins, 'uploaded_at', None),
            _resource(
                'deployments',
                self.client.deployments,
                'created_at',
                None
            ),
            _resource('nodes', self.client.nodes, 'deployment_id', None),
            _resource(
                'node-instances',
                self.client.node_instances,
                'node_id',
                'manager'
            ),
            _resource('blueprints', self.client.blueprints, 'created_at', None),
            _resource('snapshots', self.client.snapshots, 'created_at', None),
            _resource('executions', self.client.executions, 'created_at', None),
        ]

        self.count_mock_calls = 0

        self.original_lists = {}
        for r in self.resources:
            self.original_lists[r.name] = r.class_type.list

    def tearDown(self):
        for r in self.resources:
            r.class_type.list= self.original_lists[r.name]
        super(ListSortTest, self).tearDown()

    def test_list_sort(self):
        for r in self.resources:
            self._set_mock_list(r, 'order')
            self.invoke(
                'cfy {0} list --sort-by order'
                .format(r.name), context=r.context
            )
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def test_list_sort_reverse(self):
        for r in self.resources:
            self._set_mock_list(r, 'order', descending=True)
            self.invoke(
                'cfy {0} list --sort-by order --descending'
                .format(r.name), context=r.context
            )
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def test_list_sort_default(self):
        for r in self.resources:
            self._set_mock_list(r, r.sort_order)
            self.invoke('cfy {0} list'.format(r.name), context=r.context)
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def test_list_sort_default_reverse(self):
        for r in self.resources:
            self._set_mock_list(r, r.sort_order, descending=True)
            self.invoke('cfy {0} list --descending'
                        .format(r.name), context=r.context)
        self.assertEqual(len(self.resources), self.count_mock_calls)

    def _set_mock_list(self, resource, sort, descending=False):
        def _mock_list(*_, **kwargs):
            self.count_mock_calls += 1
            self.assertEqual(sort, kwargs['sort'])
            self.assertEqual(descending, kwargs['is_descending'])
            return []

        resource.class_type.list = _mock_list
