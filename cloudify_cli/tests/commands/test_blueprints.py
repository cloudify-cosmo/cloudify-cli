import os
import yaml
import tempfile
from mock import MagicMock, patch

from cloudify.exceptions import CommandExecutionException

from ... import env
from ...config import config
from .test_base import CliCommandTest
from .constants import BLUEPRINTS_DIR, SAMPLE_BLUEPRINT_PATH, \
    SAMPLE_ARCHIVE_PATH


class BlueprintsTest(CliCommandTest):

    def setUp(self):
        super(BlueprintsTest, self).setUp()
        self.use_manager()

    def test_blueprints_list(self):
        self.client.blueprints.list = MagicMock(return_value=[])
        self.invoke('blueprints list')

    @patch('cloudify_cli.table.generate')
    def test_blueprints_list_with_values(self, table_generate_mock):
        self.client.blueprints.list = MagicMock(
            return_value=[
                {'description': '12345678901234567890123'},
                {'description': 'abcdefg'}
            ]
        )
        self.invoke('blueprints list')

        table_generate_mock.assert_called_with(
            [
                'id',
                'description',
                'main_file_name',
                'created_at',
                'updated_at'
            ],
            data=[{'description': '123456789012345678..'},
                  {'description': 'abcdefg'}]
        )

    def test_blueprints_delete(self):
        self.client.blueprints.delete = MagicMock()
        self.invoke('blueprints delete a-blueprint-id')

    def test_blueprints_download(self):
        self.client.blueprints.download = MagicMock(return_value='test')
        outcome = self.invoke('blueprints download a-blueprint-id')
        self.assertIn('Blueprint downloaded as test', outcome.logs)

    @patch('cloudify_cli.table.generate', autospec=True)
    @patch('cloudify_cli.table.log', autospec=True)
    def test_blueprints_get(self, *args):
        self.client.blueprints.get = MagicMock()
        self.client.deployments.list = MagicMock()
        self.invoke('blueprints get a-blueprint-id')

    def test_blueprints_upload(self):
        self.client.blueprints.upload = MagicMock()
        self.invoke(
            'blueprints upload {0}'.format(SAMPLE_BLUEPRINT_PATH))

    def test_blueprints_upload_invalid(self):
        self.client.blueprints.upload = MagicMock()
        self.invoke(
            'cfy blueprints upload {0}/bad_blueprint/blueprint.yaml '
            '-b my_blueprint_id'.format(BLUEPRINTS_DIR))

    def test_blueprints_upload_invalid_validate(self):
        self.client.blueprints.upload = MagicMock()
        self.invoke(
            'cfy blueprints upload {0}/bad_blueprint/blueprint.yaml '
            '-b my_blueprint_id --validate'.format(BLUEPRINTS_DIR),
            err_str_segment='Failed to validate blueprint'
        )

    def test_blueprints_upload_archive(self):
        self.client.blueprints.upload = MagicMock()
        self.invoke(
            'cfy blueprints upload {0} '
            '-b my_blueprint_id --blueprint-filename blueprint.yaml'
            .format(SAMPLE_ARCHIVE_PATH))

    def test_blueprints_upload_unsupported_archive_type(self):
        self.client.blueprints.upload = MagicMock()
        # passing in a directory instead of a valid archive type
        self.invoke(
            'cfy blueprints upload {0}/helloworld -b my_blueprint_id'.format(
                BLUEPRINTS_DIR),
            'You must provide either a path to a local file')

    def test_blueprints_upload_archive_bad_file_path(self):
        self.client.blueprints.upload = MagicMock()
        self.invoke(
            'cfy blueprints upload {0}/helloworld.tar.gz -n blah'
            .format(BLUEPRINTS_DIR),
            err_str_segment="You must provide either a path to a local file")

    def test_blueprints_upload_archive_no_filename(self):
        # TODO: The error message here should be different - something to
        # do with the filename provided being incorrect
        self.client.blueprints.upload = MagicMock()
        self.invoke(
            'cfy blueprints upload {0}/helloworld.tar.gz -b my_blueprint_id'
            .format(BLUEPRINTS_DIR),
            err_str_segment="You must provide either a path to a local file")

    def test_blueprints_upload_from_url(self):
        self.client.blueprints.publish_archive = MagicMock()
        self.invoke(
                'cfy blueprints upload https://aaa.com/maste.tar.gz -n b.yaml '
                '-b blueprint3')

    def test_blueprint_validate(self):
        self.invoke(
            'cfy blueprints validate {0}'.format(
                SAMPLE_BLUEPRINT_PATH))

    def test_blueprint_validate_definitions_version_false(self):
        with open(config.CLOUDIFY_CONFIG_PATH) as f:
            conf = yaml.safe_load(f.read())
        with open(config.CLOUDIFY_CONFIG_PATH, 'w') as f:
            conf['validate_definitions_version'] = False
            f.write(yaml.safe_dump(conf))
        self.invoke(
            'cfy blueprints validate '
            '{0}/local/blueprint_validate_definitions_version.yaml'
            .format(BLUEPRINTS_DIR))

    def test_blueprint_validate_definitions_version_true(self):
        self.invoke(
            'cfy blueprints validate '
            '{0}/local/blueprint_validate_definitions_version.yaml'
            .format(BLUEPRINTS_DIR),
            err_str_segment='Failed to validate blueprint description'
        )

    def test_validate_bad_blueprint(self):
        self.invoke(
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

        assert_equal = self.assertEqual

        class RestClientMock(object):
            class BlueprintsClientMock(object):
                def __init__(self, blueprint_id, blueprint):
                    self.blueprint_id = blueprint_id
                    self.blueprint = blueprint

                def get(self, blueprint_id):
                    assert_equal(blueprint_id, self.blueprint_id)
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

        with patch('cloudify_cli.env.get_rest_client',
                   get_rest_client_mock),\
                patch('cloudify_cli.table.generate', table_mock):
            self.invoke('cfy blueprints inputs {0}'.format(blueprint_id))

    def test_create_requirements(self):
        local_dir = os.path.join(BLUEPRINTS_DIR, 'local')
        blueprint_path = os.path.join(local_dir, 'blueprint_with_plugins.yaml')
        expected_requirements = {
            'http://localhost/plugin.zip',
            os.path.join(local_dir, 'plugins', 'local_plugin'),
            'http://localhost/host_plugin.zip'
        }
        tmp_requirements_path = os.path.join(
            env.CLOUDIFY_WORKDIR, 'requirements.txt')

        self.invoke('cfy blueprints create-requirements {0} -o {1}'
                    .format(blueprint_path, tmp_requirements_path))

        with open(tmp_requirements_path, 'r') as f:
            actual_requirements = set(f.read().split())
            self.assertEqual(actual_requirements, expected_requirements)

    def test_create_requirements_existing_output_file(self):
        blueprint_path = '{0}/local/blueprint_with_plugins.yaml'\
            .format(BLUEPRINTS_DIR)
        file_path = tempfile.mktemp()
        with open(file_path, 'w') as f:
            f.write('')

        self.invoke(
            'cfy blueprints create-requirements {0} -o {1}'
            .format(blueprint_path, file_path),
            err_str_segment='Path {0} already exists'
            .format(file_path)
        )

    def test_create_requirements_output_to_screen(self):
        local_dir = os.path.join(BLUEPRINTS_DIR, 'local')
        blueprint_path = os.path.join(local_dir, 'blueprint_with_plugins.yaml')
        expected_requirements = {
            'http://localhost/plugin.zip',
            os.path.join(local_dir, 'plugins', 'local_plugin'),
            'http://localhost/host_plugin.zip'
        }

        output = self.invoke('cfy blueprints create-requirements {0}'
                             .format(blueprint_path)).logs.split('\n')

        for requirement in expected_requirements:
            self.assertIn(requirement, output)

    def test_install_plugins(self):
        self.invoke('cfy use local')
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            'blueprint_with_plugins.yaml'
        )

        output = self.invoke(
            'cfy blueprints install-plugins {0}'.format(blueprint_path),
            err_str_segment='Invalid requirement',
            exception=CommandExecutionException
        )

        self.assertIn('pip install -r', output.exception.command)
