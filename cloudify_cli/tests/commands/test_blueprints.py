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
Tests all commands that start with 'cfy blueprints'
"""

from mock import MagicMock
from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest
from cloudify_cli.tests.commands.test_cli_command import BLUEPRINTS_DIR


class BlueprintsTest(CliCommandTest):

    def setUp(self):
        super(BlueprintsTest, self).setUp()
        self._create_cosmo_wd_settings()

    def test_blueprints_list(self):
        self.client.blueprints.list = MagicMock(return_value=[])
        cli_runner.run_cli('cfy blueprints list')

    def test_blueprints_delete(self):
        self.client.blueprints.delete = MagicMock()
        cli_runner.run_cli('cfy blueprints delete -b a-blueprint-id')

    def test_blueprints_upload(self):
        self.client.blueprints.upload = MagicMock()
        cli_runner.run_cli('cfy blueprints upload -bp '
                           '{0}/helloworld/blueprint.yaml '
                           '-b my_blueprint_id'.format(BLUEPRINTS_DIR))

    def test_blueprint_validate(self):
        cli_runner.run_cli('cfy blueprints validate '
                           '-bp {0}/helloworld/blueprint.yaml'
                           .format(BLUEPRINTS_DIR))

    def test_validate_bad_blueprint(self):
        self._assert_ex('cfy blueprints validate '
                        '-bp {0}/bad_blueprint/blueprint.yaml'
                        .format(BLUEPRINTS_DIR),
                        'Failed to validate blueprint')
