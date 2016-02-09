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

import yaml
from mock import MagicMock, patch

from cloudify_cli import utils
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

    @patch('cloudify_cli.utils.table', autospec=True)
    @patch('cloudify_cli.utils.print_table', autospec=True)
    def test_blueprints_get(self, *args):
        self.client.blueprints.get = MagicMock()
        self.client.deployments.list = MagicMock()

        cli_runner.run_cli('cfy blueprints get -b a-blueprint-id')

    def test_blueprints_upload(self):
        self.client.blueprints.upload = MagicMock()
        cli_runner.run_cli('cfy blueprints upload -p '
                           '{0}/helloworld/blueprint.yaml '
                           '-b my_blueprint_id'.format(BLUEPRINTS_DIR))

    def test_blueprints_upload_invalid(self):
        self.client.blueprints.upload = MagicMock()
        cli_runner.run_cli('cfy blueprints upload -p '
                           '{0}/bad_blueprint/blueprint.yaml '
                           '-b my_blueprint_id'
                           .format(BLUEPRINTS_DIR))

    def test_blueprints_upload_invalid_validate(self):
        self.client.blueprints.upload = MagicMock()
        self._assert_ex('cfy blueprints upload -p '
                        '{0}/bad_blueprint/blueprint.yaml '
                        '-b my_blueprint_id --validate'
                        .format(BLUEPRINTS_DIR),
                        'Failed to validate blueprint')

    def test_blueprints_publish_archive(self):
        self.client.blueprints.publish_archive = MagicMock()
        cli_runner.run_cli('cfy blueprints publish-archive -l '
                           '{0}/helloworld.zip '
                           '-b my_blueprint_id'.format(BLUEPRINTS_DIR))

    def test_blueprints_publish_unsupported_archive_type(self):
        self.client.blueprints.publish_archive = MagicMock()
        # passing in a directory instead of a valid archive type
        self._assert_ex('cfy blueprints publish-archive -l '
                        '{0}/helloworld '
                        '-b my_blueprint_id'.format(BLUEPRINTS_DIR),
                        "unsupported archive type")

    def test_blueprints_publish_archive_bad_file_path(self):
        self.client.blueprints.publish_archive = MagicMock()
        self._assert_ex('cfy blueprints publish-archive -l '
                        '{0}/helloworld.tar.gz '
                        '-b my_blueprint_id'.format(BLUEPRINTS_DIR),
                        "not a valid URL nor a path")

    def test_blueprint_validate(self):
        cli_runner.run_cli('cfy blueprints validate '
                           '-p {0}/helloworld/blueprint.yaml'
                           .format(BLUEPRINTS_DIR))

    def test_blueprint_validate_definitions_version_false(self):
        with open(utils.get_configuration_path()) as f:
            config = yaml.safe_load(f.read())
        with open(utils.get_configuration_path(), 'w') as f:
            config['validate_definitions_version'] = False
            f.write(yaml.safe_dump(config))
        cli_runner.run_cli(
            'cfy blueprints validate '
            '-p {0}/local/blueprint_validate_definitions_version.yaml'
            .format(BLUEPRINTS_DIR))

    def test_validate_bad_blueprint(self):
        self._assert_ex('cfy blueprints validate '
                        '-p {0}/bad_blueprint/blueprint.yaml'
                        .format(BLUEPRINTS_DIR),
                        'Failed to validate blueprint')

    def test_blueprint_inputs(self):

        BLUEPRINT_ID = 'a-blueprint-id'
        NAME = 'test_input'
        TYPE = 'string'
        DESCRIPTION = 'Test input.'

        BLUEPRINT = {
            'plan': {
                'inputs': {
                    NAME: {
                        'type': TYPE,
                        'description': DESCRIPTION
                        # field 'default' intentionally omitted
                    }
                }
            }
        }

        assertEqual = self.assertEqual

        class RestClientMock(object):
            class BlueprintsClientMock(object):
                def __init__(self, blueprint_id, blueprint):
                    self.blueprint_id = blueprint_id
                    self.blueprint = blueprint

                def get(self, blueprint_id):
                    assertEqual(blueprint_id, self.blueprint_id)
                    return self.blueprint

            def __init__(self, blueprint_id, blueprint):
                self.blueprints = self.BlueprintsClientMock(blueprint_id,
                                                            blueprint)

        def get_rest_client_mock(*args, **kwargs):
            return RestClientMock(BLUEPRINT_ID, BLUEPRINT)

        def table_mock(fields, data, *args, **kwargs):
            self.assertEqual(len(data), 1)
            input = data[0]
            self.assertIn('name', input)
            self.assertIn('type', input)
            self.assertIn('default', input)
            self.assertIn('description', input)

            self.assertEqual(input['name'], NAME)
            self.assertEqual(input['type'], TYPE)
            self.assertEqual(input['default'], '-')
            self.assertEqual(input['description'], DESCRIPTION)

        with patch('cloudify_cli.utils.get_rest_client',
                   get_rest_client_mock),\
                patch('cloudify_cli.utils.table', table_mock):
            cli_runner.run_cli('cfy blueprints inputs -b {0}'
                               .format(BLUEPRINT_ID))
