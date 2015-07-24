########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
Tests all commands that start with 'cfy instances'
"""

from uuid import uuid4

from mock import MagicMock

from cloudify_rest_client.node_instances import NodeInstance
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class InstancesTest(CliCommandTest):

    def setUp(self):
        super(InstancesTest, self).setUp()
        self._create_cosmo_wd_settings()

    def test_instances_get(self):
        self.client.node_instances.get = \
            MagicMock(return_value=node_instance_get_mock())
        cli_runner.run_cli('cfy node-instances get '
                           '--node-instance-id instance_id')

    def test_instance_get_no_instance_id(self):
        with self.assertRaises(SystemExit) as sys_exit:
            cli_runner.run_cli('cfy node-instances get')
        self.assertNotEquals(sys_exit.exception.code, 0)

    def test_instances_list(self):
        self.client.node_instances.list = MagicMock(
            return_value=[node_instance_get_mock(), node_instance_get_mock()])
        cli_runner.run_cli('cfy node-instances list')
        cli_runner.run_cli('cfy node-instances list -d nodecellar')


def node_instance_get_mock():
    return NodeInstance({
        'id': uuid4(),
        'deployment_id': 'deployment_id',
        'host_id': 'host_id',
        'node_id': 'node_id',
        'state': 'started',
        'runtime_properties': {
            'floating_ip': '127.0.0.1'
        }
    })
