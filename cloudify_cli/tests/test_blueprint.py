import os

from mock import patch
from testtools import TestCase
from testtools.matchers import Equals

from .commands.constants import (
    SAMPLE_ARCHIVE_PATH,
    SAMPLE_ARCHIVE_URL,
    SAMPLE_BLUEPRINT_PATH,
    SAMPLE_CUSTOM_NAME_ARCHIVE,
    STUB_DIRECTORY_NAME,
)
from cloudify_cli import blueprint
from cloudify_cli.exceptions import CloudifyCliError


class TestGet(TestCase):

    """Test get a blueprint."""

    def test_yaml_path(self):
        """Get a blueprint from a yaml file."""
        self.assertThat(
            blueprint.get(SAMPLE_BLUEPRINT_PATH),
            Equals(SAMPLE_BLUEPRINT_PATH),
        )

    @patch('cloudify_cli.blueprint.os.path.isfile')
    @patch('cloudify_cli.blueprint.os.listdir')
    @patch('cloudify_cli.blueprint.utils.extract_archive')
    def test_archive_default_name(self, extract_archive, listdir, isfile):
        """Get a blueprint from a zip file."""
        extract_archive.return_value = '/tmp'
        listdir.return_value = ['directory']
        isfile.return_value = True
        self.assertThat(
            blueprint.get(SAMPLE_ARCHIVE_PATH),
            Equals('/tmp/directory/blueprint.yaml'),
        )

    @patch('cloudify_cli.blueprint.os.path.isfile')
    @patch('cloudify_cli.blueprint.os.listdir')
    @patch('cloudify_cli.blueprint.utils.extract_archive')
    def test_archive_custom_name(self, extract_archive, listdir, isfile):
        """Get a blueprint with a custom name from a zip file."""
        extract_archive.return_value = '/tmp'
        listdir.return_value = ['directory']
        isfile.return_value = True
        self.assertThat(
            blueprint.get(SAMPLE_CUSTOM_NAME_ARCHIVE, 'simple_blueprint.yaml'),
            Equals('/tmp/directory/simple_blueprint.yaml'),
        )

    @patch('cloudify_cli.blueprint.os.path.isfile')
    @patch('cloudify_cli.blueprint.os.listdir')
    @patch('cloudify_cli.blueprint.utils.extract_archive')
    def test_archive_custom_name_no_default(
            self, extract_archive, listdir, isfile):
        """Fail to get blueprint with a custom name from a zip file."""
        extract_archive.return_value = '/tmp'
        listdir.return_value = ['directory']
        isfile.return_value = False
        self.assertRaises(
            CloudifyCliError,
            blueprint.get,
            SAMPLE_CUSTOM_NAME_ARCHIVE
        )

    def test_url_default_name(self):
        """Skip URL download."""
        self.assertThat(
            blueprint.get(SAMPLE_ARCHIVE_URL),
            Equals(SAMPLE_ARCHIVE_URL),
        )

    def test_url_custom_name(self):
        """Ignore custom name in URL."""
        self.assertThat(
            blueprint.get(SAMPLE_ARCHIVE_URL, 'ec2-blueprint.yaml'),
            Equals(SAMPLE_ARCHIVE_URL),
        )

    def test_bad_filename(self):
        """Fail to get blueprint from a yaml file that doesn't exist."""
        self.assertRaises(
            CloudifyCliError,
            blueprint.get,
            'bad_filename.yaml'
        )

    def test_github_path(self):
        """Map github repository path to URL."""
        # Can't check the whole path here, as it's a randomly generated temp
        self.assertThat(
            blueprint.get('cloudify-cosmo/cloudify-hello-world-example'),
            Equals(
                'https://github.com/cloudify-cosmo/'
                'cloudify-hello-world-example/archive/master.tar.gz'
            ),
        )

    def test_github_path_custom_name(self):
        """Map github repository path to URL and ignore custom name."""
        self.assertThat(
            blueprint.get(
                'cloudify-cosmo/cloudify-hello-world-example',
                'ec2-blueprint.yaml'
            ),
            Equals(
                'https://github.com/cloudify-cosmo/'
                'cloudify-hello-world-example/archive/master.tar.gz'
            ),
        )


class TestGenerateId(TestCase):

    """Test generate blueprint id."""

    def test_generate_id_default(self):
        """Generate blueprint id from directory."""
        self.assertThat(
            blueprint.generate_id(SAMPLE_BLUEPRINT_PATH),
            Equals(STUB_DIRECTORY_NAME),
        )

    def test_generate_id_custom(self):
        """Generate blueprint id from directory and custom filename."""
        self.assertThat(
            blueprint.generate_id(SAMPLE_BLUEPRINT_PATH, 'test.yaml'),
            Equals('{0}.test'.format(STUB_DIRECTORY_NAME)),
        )

    def test_generate_id_in_blueprint_folder(self):
        """Generate blueprint id from relative directory."""
        self.assertThat(
            blueprint.generate_id(os.path.join('.', SAMPLE_BLUEPRINT_PATH)),
            Equals('helloworld'),
        )
