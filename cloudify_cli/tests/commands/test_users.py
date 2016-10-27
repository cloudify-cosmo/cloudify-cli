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


class UsersTest(CliCommandTest):
    def setUp(self):
        super(UsersTest, self).setUp()
        self.use_manager()
        self.client.users = MagicMock()

    def test_users_list(self):
        self.invoke('cfy users list')

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
        self.invoke('cfy users create username -p password -r viewer')
        call_list = self.client.users.method_calls[0][1]
        self.assertEqual(call_list, ('username', 'password', 'viewer'))

    def test_create_users_invalid_role(self):
        outcome = self.invoke(
            'cfy users create username -p password -r invalid_role',
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        self.assertIn(
            'Invalid value for "-r" / "--security-role"',
            outcome.output
        )
