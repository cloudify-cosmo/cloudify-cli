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

import yaml
from mock import MagicMock, patch

from ... import utils
from .test_cli_command import CliCommandTest
from .test_cli_command import BLUEPRINTS_DIR


class BlueprintsTest(CliCommandTest):

    def setUp(self):
        super(BlueprintsTest, self).setUp()
        self.create_cosmo_wd_settings()

    def test_blueprints_list(self):
        self.client.blueprints.list = MagicMock(return_value=[])
        self.cfy_check('blueprints list')

    def test_blueprints_delete(self):
        self.client.blueprints.delete = MagicMock()
        self.cfy_check('blueprints delete a-blueprint-id')

    @patch('cloudify_cli.utils.table', autospec=True)
    @patch('cloudify_cli.common.print_table', autospec=True)
    def test_blueprints_get(self, *args):
        self.client.blueprints.get = MagicMock()
        self.client.deployments.list = MagicMock()
        self.cfy_check('blueprints get a-blueprint-id')

    def test_blueprints_upload(self):
        self.client.blueprints.upload = MagicMock()
        self.cfy_check(
            'blueprints upload {0}/helloworld/blueprint.yaml'.format(
                BLUEPRINTS_DIR))

    def test_blueprints_upload_invalid(self):
        self.client.blueprints.upload = MagicMock()
        self.cfy_check(
            'cfy blueprints upload {0}/bad_blueprint/blueprint.yaml '
            '-b my_blueprint_id'.format(BLUEPRINTS_DIR))

    def test_blueprints_upload_invalid_validate(self):
        self.client.blueprints.upload = MagicMock()
        self.cfy_check(
            'cfy blueprints upload {0}/bad_blueprint/blueprint.yaml '
            '-b my_blueprint_id --validate'.format(BLUEPRINTS_DIR),
            err_str_segment='Failed to validate blueprint',
            should_fail=True)

    def test_blueprints_publish_archive(self):
        self.client.blueprints.publish_archive = MagicMock()
        self.cfy_check(
            'cfy blueprints upload {0}/helloworld.zip '
            '-b my_blueprint_id --blueprint-filename blueprint.yaml'
            .format(BLUEPRINTS_DIR))

    def test_blueprints_publish_unsupported_archive_type(self):
        self.client.blueprints.publish_archive = MagicMock()
        # passing in a directory instead of a valid archive type
        self.cfy_check(
            'cfy blueprints upload {0}/helloworld -b my_blueprint_id'.format(
                BLUEPRINTS_DIR),
            'You must either provide a path to a local blueprint file')

    def test_blueprints_publish_archive_bad_file_path(self):
        self.client.blueprints.publish_archive = MagicMock()
        self.cfy_check(
            'cfy blueprints upload {0}/helloworld.tar.gz -n blah'
            .format(BLUEPRINTS_DIR),
            err_str_segment="not a valid URL nor a path")

    def test_blueprints_publish_archive_no_filename(self):
        self.client.blueprints.publish_archive = MagicMock()
        self.cfy_check(
            'cfy blueprints upload {0}/helloworld.tar.gz -b my_blueprint_id'
            .format(BLUEPRINTS_DIR),
            err_str_segment="Supplying an archive requires that the name of")

    def test_blueprint_validate(self):
        self.cfy_check(
            'cfy blueprints validate {0}/helloworld/blueprint.yaml'.format(
                BLUEPRINTS_DIR))

    def test_blueprint_validate_definitions_version_false(self):
        with open(utils.CLOUDIFY_CONFIG_PATH) as f:
            config = yaml.safe_load(f.read())
        with open(utils.CLOUDIFY_CONFIG_PATH, 'w') as f:
            config['validate_definitions_version'] = False
            f.write(yaml.safe_dump(config))
        self.cfy_check(
            'cfy blueprints validate '
            '{0}/local/blueprint_validate_definitions_version.yaml'
            .format(BLUEPRINTS_DIR))

    def test_validate_bad_blueprint(self):
        self.cfy_check(
            'cfy blueprints validate {0}/bad_blueprint/blueprint.yaml'
            .format(BLUEPRINTS_DIR),
            err_str_segment='Failed to validate blueprint')

    def test_blueprint_inputs(self):

        blueprint_id = 'a-blueprint-id'
        name = 'test_input'
        type = 'string'
        description = 'Test input.'

        blueprint = {
            'plan': {
                'inputs': {
                    name: {
                        'type': type,
                        'description': description
                        # field 'default' intentionally omitted
                    }
                }
            }
        }

        class RestClientMock(object):
            class BlueprintsClientMock(object):
                def __init__(self, blueprint_id, blueprint):
                    self.blueprint_id = blueprint_id
                    self.blueprint = blueprint

                def get(self, blueprint_id):
                    self.assertEqual(blueprint_id, self.blueprint_id)
                    return self.blueprint

            def __init__(self, blueprint_id, blueprint):
                self.blueprints = self.BlueprintsClientMock(blueprint_id,
                                                            blueprint)

        def get_rest_client_mock(*args, **kwargs):
            return RestClientMock(blueprint_id, blueprint)

        def table_mock(fields, data, *args, **kwargs):
            self.assertEqual(len(data), 1)
            input = data[0]
            self.assertIn('name', input)
            self.assertIn('type', input)
            self.assertIn('default', input)
            self.assertIn('description', input)

            self.assertEqual(input['name'], name)
            self.assertEqual(input['type'], type)
            self.assertEqual(input['default'], '-')
            self.assertEqual(input['description'], description)

        with patch('cloudify_cli.utils.get_rest_client',
                   get_rest_client_mock),\
                patch('cloudify_cli.utils.table', table_mock):
            self.cfy_check('cfy blueprints inputs {0}'.format(blueprint_id))
