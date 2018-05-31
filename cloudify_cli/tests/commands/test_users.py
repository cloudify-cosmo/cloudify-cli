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


class UsersTest(CliCommandTest):
    def setUp(self):
        super(UsersTest, self).setUp()
        self.use_manager()
        self.client.users = MagicMock()

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
