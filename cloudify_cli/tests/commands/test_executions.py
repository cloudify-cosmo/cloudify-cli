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
Tests all commands that start with 'cfy executions'
"""

import datetime
from uuid import uuid4

from mock import MagicMock
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest
from cloudify_rest_client.executions import Execution


class ExecutionsTest(CliCommandTest):

    def setUp(self):
        super(ExecutionsTest, self).setUp()
        self._create_cosmo_wd_settings()

    def test_executions_get(self):

        execution = Execution({
            'status': 'terminated',
            'workflow_id': 'mock_wf',
            'deployment_id': 'deployment-id',
            'blueprint_id': 'blueprint-id',
            'error': '',
            'id': uuid4(),
            'created_at': datetime.datetime.now(),
            'parameters': {}
        })

        self.client.executions.get = MagicMock(return_value=execution)
        cli_runner.run_cli('cfy executions get -e execution-id')

    def test_executions_list(self):
        self.client.executions.list = MagicMock(return_value=[])
        cli_runner.run_cli('cfy executions list -d deployment-id')

    def test_executions_cancel(self):
        self.client.executions.cancel = MagicMock()
        cli_runner.run_cli('cfy executions cancel -e e_id')
