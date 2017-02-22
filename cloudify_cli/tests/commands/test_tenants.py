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


class TenantsTest(CliCommandTest):
    def setUp(self):
        super(TenantsTest, self).setUp()
        self.use_manager()
        self.client.tenants = MagicMock()

    def test_empty_tenant_name(self):
        self.invoke(
            'cfy tenants create ""',
            err_str_segment='ERROR: The `tenant_name` argument is empty',
            exception=CloudifyValidationError
        )

    def test_illegal_characters_in_tenant_name(self):
        self.invoke(
            'cfy tenants create "#&*"',
            err_str_segment='ERROR: The `tenant_name` argument contains '
                            'illegal characters',
            exception=CloudifyValidationError
        )
