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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############
from .test_base import CliCommandTest
from mock import MagicMock


class LdapTest(CliCommandTest):

    def setUp(self):
        super(LdapTest, self).setUp()
        self.use_manager()

    def test_ldap_set(self):
        self.client.ldap.set = MagicMock(return_value='')
        self.invoke('ldap set -s server -u user -p pass -d name -a '
                    '-e extra')
