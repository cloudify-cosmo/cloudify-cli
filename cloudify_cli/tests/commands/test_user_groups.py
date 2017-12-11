########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

from mock import MagicMock

from .test_base import CliCommandTest
from cloudify_cli.exceptions import CloudifyValidationError


class UserGroupsTest(CliCommandTest):
    def setUp(self):
        super(UserGroupsTest, self).setUp()
        self.use_manager()
        self.client.user_groups = MagicMock()

    def test_user_groups_create(self):
        self.client.user_groups.create = MagicMock()
        self.invoke('cfy user-groups create my_group_name')
        self.assertEquals(1, len(self.client.user_groups.method_calls))
        self.assertEquals('create', self.client.user_groups.method_calls[0][0])
        self.assertEquals(('my_group_name', 'default'),
                          self.client.user_groups.method_calls[0][1])

    def test_user_groups_get(self):
        self.client.user_groups.get = MagicMock(
            return_value={'name': '', 'tenants': [], 'users': []})
        self.invoke('cfy user-groups get my_group_name')
        self.assertEquals(1, len(self.client.user_groups.method_calls))
        self.assertEquals('get', self.client.user_groups.method_calls[0][0])
        self.assertEquals(
            ('my_group_name',), self.client.user_groups.method_calls[0][1])

    def test_user_groups_add_user(self):
        self.client.user_groups = MagicMock()
        self.client.user_groups.add_user = MagicMock()
        self.invoke('cfy user-groups add-user my_username -g my_group_name')
        self.assertEquals(1, len(self.client.user_groups.method_calls))
        self.assertEquals(
            'add_user', self.client.user_groups.method_calls[0][0])
        self.assertEquals(('my_username', 'my_group_name',),
                          self.client.user_groups.method_calls[0][1])

    def test_user_groups_remove_user(self):
        self.client.user_groups = MagicMock()
        self.client.user_groups.remove_user = MagicMock()
        self.invoke('cfy user-groups remove-user my_username -g my_group_name')
        self.assertEquals(1, len(self.client.user_groups.method_calls))
        self.assertEquals(
            'remove_user', self.client.user_groups.method_calls[0][0])
        self.assertEquals(('my_username', 'my_group_name',),
                          self.client.user_groups.method_calls[0][1])

    def test_group_create(self):
        self.invoke('cfy user-groups create group1 -l ldap_dn')

    def test_empty_user_group_name(self):
        self.invoke(
            'cfy user-groups create ""',
            err_str_segment='ERROR: The `user_group_name` argument is empty',
            exception=CloudifyValidationError
        )

    def test_illegal_characters_in_user_group_name(self):
        self.invoke(
            'cfy user-groups create "#&*"',
            err_str_segment='ERROR: The `user_group_name` argument contains '
                            'illegal characters',
            exception=CloudifyValidationError
        )
