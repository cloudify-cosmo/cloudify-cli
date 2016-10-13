import os

from testtools import TestCase

from .commands.constants import (
    SAMPLE_ARCHIVE_PATH,
    SAMPLE_ARCHIVE_URL,
    SAMPLE_BLUEPRINT_PATH,
    SAMPLE_CUSTOM_NAME_ARCHIVE,
)
from cloudify_cli import blueprint
from cloudify_cli.exceptions import CloudifyCliError


class TestGetBlueprint(TestCase):

    """Test get a blueprint."""

    def test_yaml_path(self):
        self.assertEqual(
            SAMPLE_BLUEPRINT_PATH,
            blueprint.get(SAMPLE_BLUEPRINT_PATH)
        )

    def test_archive_default_name(self):
        # Can't check the whole path here, as it's a randomly generated temp
        self.assertIn(
            'helloworld/blueprint.yaml',
            blueprint.get(SAMPLE_ARCHIVE_PATH)
        )

    def test_archive_custom_name(self):
        # Can't check the whole path here, as it's a randomly generated temp
        self.assertIn(
            'helloworld/simple_blueprint.yaml',
            blueprint.get(SAMPLE_CUSTOM_NAME_ARCHIVE, 'simple_blueprint.yaml')
        )

    def test_archive_custom_name_no_default(self):
        # There's no `blueprint.yaml` in the archive, so it should fail here
        self.assertRaises(
            CloudifyCliError,
            blueprint.get,
            SAMPLE_CUSTOM_NAME_ARCHIVE
        )

    def test_url_default_name(self):
        # Can't check the whole path here, as it's a randomly generated temp
        self.assertEqual(
            blueprint.get(SAMPLE_ARCHIVE_URL),
            SAMPLE_ARCHIVE_URL,
        )

    def test_url_custom_name(self):
        # Can't check the whole path here, as it's a randomly generated temp
        self.assertTrue(
            blueprint.get(SAMPLE_ARCHIVE_URL, 'ec2-blueprint.yaml'),
            SAMPLE_ARCHIVE_URL,
        )

    def test_bad_filename(self):
        self.assertRaises(
            CloudifyCliError,
            blueprint.get,
            'bad_filename.yaml'
        )

    def test_github_path(self):
        # Can't check the whole path here, as it's a randomly generated temp
        self.assertTrue(
            blueprint.get(
                'cloudify-cosmo/cloudify-hello-world-example'
            ).endswith(
                'cloudify-hello-world-example-master/blueprint.yaml',
            )
        )

    def test_github_path_custom_name(self):
        # Can't check the whole path here, as it's a randomly generated temp
        self.assertTrue(
            blueprint.get(
                'cloudify-cosmo/cloudify-hello-world-example',
                'ec2-blueprint.yaml'
            ).endswith(
                'cloudify-hello-world-example-master/ec2-blueprint.yaml',
            )
        )

    def test_generate_id_default(self):
        self.assertEqual(
            'helloworld',
            blueprint.generate_id(SAMPLE_BLUEPRINT_PATH)
        )

    def test_generate_id_custom(self):
        self.assertEqual(
            'helloworld.test',
            blueprint.generate_id(SAMPLE_BLUEPRINT_PATH, 'test')
        )

    def test_generate_id_in_blueprint_folder(self):
        self.assertEqual(
            'helloworld',
            blueprint.generate_id(os.path.join('.', SAMPLE_BLUEPRINT_PATH)))
