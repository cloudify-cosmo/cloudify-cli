########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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
from cloudify_cli.tests.commands.base_upgrade_test import BaseUpgradeTest


class ManagerUpgradeTest(BaseUpgradeTest):

    def setUp(self):
        super(ManagerUpgradeTest, self).setUp()
        self._create_cosmo_wd_settings()

    def test_not_in_maintenance_upgrade(self):
        self._test_not_in_maintenance(action='upgrade')

    def test_upgrade_no_bp(self):
        self._test_no_bp(action='upgrade')

    def _test_upgrade_no_private_ip(self):
        self._test_no_private_ip(action='upgrade')

    def _test_upgrade_no_inputs(self):
        self._test_no_inputs(action='upgrade')
