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


class BaseUsersTest(CliCommandTest):
    def setUp(self):
        super(BaseUsersTest, self).setUp()
        self.use_manager()
        self.client.users = MagicMock()


class UsersTest(BaseUsersTest):
    def setUp(self):
        super(UsersTest, self).setUp()

    def test_create_users_missing_username(self):
        outcome = self.invoke(
            'cfy users create',
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        self.assertIn('Missing argument "username"', outcome.output)

    def test_create_users_missing_password(self):
        outcome = self.invoke(
            'cfy users create username',
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        self.assertIn('Missing option "-p" / "--password"', outcome.output)

    def test_create_users_default_role(self):
        self.invoke('cfy users create username -p password')
        call_list = self.client.users.method_calls[0][1]
        self.assertEqual(call_list, ('username', 'password', 'default'))

    def test_create_users_custom_role(self):
        self.invoke('cfy users create username -p password -r admin')
        call_list = self.client.users.method_calls[0][1]
        self.assertEqual(call_list, ('username', 'password', 'admin'))

    def test_empty_username(self):
        self.invoke(
            'cfy users create "" -p password',
            err_str_segment='ERROR: The `username` argument is empty',
            exception=CloudifyValidationError
        )

    def test_illegal_characters_in_username(self):
        self.invoke(
            'cfy users create "#&*" -p password',
            err_str_segment='ERROR: The `username` argument contains '
                            'illegal characters',
            exception=CloudifyValidationError
        )

    def test_empty_password(self):
        self.invoke(
            'cfy users create user -p ""',
            err_str_segment='ERROR: The password is empty',
            exception=CloudifyValidationError
        )

    def test_unlock_user(self):
        self.invoke('cfy users unlock user1')
        call_list = self.client.users.method_calls[0][1][0]
        self.assertEqual(call_list, 'user1')


class CreateUsersWithTenantTest(BaseUsersTest):
    def setUp(self):
        super(CreateUsersWithTenantTest, self).setUp()
        self.client.tenants = MagicMock()

    def test_create_users_without_tenant_info(self):
        self.invoke('cfy users create username -p password')
        call_list = self.client.users.method_calls[0][1]
        self.assertEqual(call_list, ('username', 'password', 'default'))
        adding_to_tenant_call_list = self.client.tenants.method_calls
        self.assertEqual(adding_to_tenant_call_list, [])

    def test_create_users_with_full_tenant_info(self):
        self.invoke('cfy users create username -p password -t\
                    test_tenant -l test_user')
        user_create_call_list = self.client.users.method_calls[0][1]
        self.assertEqual(user_create_call_list,
                         ('username', 'password', 'default'))
        adding_to_tenant_call_list = self.client.tenants.method_calls[0][1]
        self.assertEqual(adding_to_tenant_call_list,
                         ('username', 'test_tenant', 'test_user'))

    def test_create_users_with_full_tenant_info_long_flags_names(self):
        self.invoke('cfy users create username -p password --tenant-name\
                    test_tenant --user-tenant-role test_user')
        user_create_call_list = self.client.users.method_calls[0][1]
        self.assertEqual(user_create_call_list,
                         ('username', 'password', 'default'))
        adding_to_tenant_call_list = self.client.tenants.method_calls[0][1]
        self.assertEqual(adding_to_tenant_call_list,
                         ('username', 'test_tenant', 'test_user'))

    def test_create_fail_users_with_tenant_name_only(self):
        self.invoke('cfy users create username -p password -t default')
        user_create_call_list = self.client.users.method_calls[0][1]
        self.assertEqual(user_create_call_list,
                         ('username', 'password', 'default'))
        adding_to_tenant_call_list = self.client.tenants.method_calls
        self.assertEqual(adding_to_tenant_call_list, [])

    def test_create_fail_users_with_user_tenant_role_only(self):
        self.invoke('cfy users create username -p password -l user')
        user_create_call_list = self.client.users.method_calls[0][1]
        self.assertEqual(user_create_call_list,
                         ('username', 'password', 'default'))
        adding_to_tenant_call_list = self.client.tenants.method_calls
        self.assertEqual(adding_to_tenant_call_list, [])
