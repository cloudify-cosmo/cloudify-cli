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
Tests all commands that start with 'cfy events'
"""

from mock import MagicMock

from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class EventsTest(CliCommandTest):

    def setUp(self):
        super(EventsTest, self).setUp()
        self._create_cosmo_wd_settings()

    def test_events(self):
        self.client.executions.get = MagicMock()
        self.client.events.get = MagicMock(return_value=([], 0))
        cli_runner.run_cli('cfy events list --execution-id execution-id')
