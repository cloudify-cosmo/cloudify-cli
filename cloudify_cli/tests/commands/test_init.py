import os

import yaml
from mock import patch

from dsl_parser.exceptions import DSLParsingLogicException

from .. import cfy
from ... import env
from .test_base import CliCommandTest
from .constants import BLUEPRINTS_DIR, SAMPLE_INPUTS_PATH, \
    DEFAULT_BLUEPRINT_FILE_NAME


class InitTest(CliCommandTest):

    def test_init_initialized_directory(self):
        self.use_manager()
        self.invoke(
            'cfy init',
            err_str_segment='Environment is already initialized')

    def test_init_overwrite(self):
        # Config values shouldn't change between init resets
        with open(env.CLOUDIFY_CONFIG_PATH) as f:
            config = yaml.safe_load(f.read())

        self.assertFalse(config['colors'])
        with open(env.CLOUDIFY_CONFIG_PATH, 'w') as f:
            config['colors'] = True
            f.write(yaml.safe_dump(config))

        self.invoke('cfy init -r')
        with open(env.CLOUDIFY_CONFIG_PATH) as f:
            config = yaml.safe_load(f.read())

        self.assertTrue(config['colors'])

    def test_init_overwrite_hard(self):
        # Config values should change between hard init resets
        with open(env.CLOUDIFY_CONFIG_PATH) as f:
            config = yaml.safe_load(f.read())

        self.assertFalse(config['colors'])
        with open(env.CLOUDIFY_CONFIG_PATH, 'w') as f:
            config['colors'] = True
            f.write(yaml.safe_dump(config))

        self.invoke('cfy init -r --hard')
        with open(env.CLOUDIFY_CONFIG_PATH) as f:
            config = yaml.safe_load(f.read())

        self.assertFalse(config['colors'])

    def test_init_overwrite_on_initial_init(self):
        # Simply verifying the overwrite flag doesn't break the first init
        cfy.purge_dot_cloudify()
        self.invoke('cfy init -r')

    def test_init_invalid_blueprint_path(self):
        self.invoke(
            'cfy init idonotexist.yaml',
            exception=IOError,
            should_fail=True
        )

    def test_init_default_outputs(self):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )
        command = 'cfy init {0}'.format(blueprint_path)

        self.invoke(command)
        cfy.register_commands()

        output = self.invoke('cfy deployments outputs').logs.split('\n')
        self.assertIn('  "key1": "default_val1", ', output)
        self.assertIn('  "key2": "default_val2", ', output)
        self.assertIn('  "key3": "default_val3", ', output)
        self.assertIn('  "param": null, ', output)
        self.assertIn('  "custom_param": null, ', output)
        self.assertIn('  "provider_context": null', output)

    def test_init_default_inputs(self):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )
        command = 'cfy init {0}'.format(blueprint_path)

        self.invoke(command)
        cfy.register_commands()

        output = self.invoke('cfy deployments inputs').logs.split('\n')
        self.assertIn('  "key1": "default_val1", ', output)
        self.assertIn('  "key2": "default_val2", ', output)
        self.assertIn('  "key3": "default_val3"', output)

    def test_init_with_inputs(self):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )
        command = 'cfy init {0} -i {1} -i key3=val3'.format(
            blueprint_path,
            SAMPLE_INPUTS_PATH
        )

        self.invoke(command)
        cfy.register_commands()

        output = self.invoke('cfy deployments inputs').logs.split('\n')
        self.assertIn('  "key1": "val1", ', output)
        self.assertIn('  "key2": "val2", ', output)
        self.assertIn('  "key3": "val3"', output)

    def test_init_validate_definitions_version_false(self):
        with open(env.CLOUDIFY_CONFIG_PATH) as f:
            config = yaml.safe_load(f.read())
        with open(env.CLOUDIFY_CONFIG_PATH, 'w') as f:
            config['validate_definitions_version'] = False
            f.write(yaml.safe_dump(config))
        self.invoke(
            'cfy init {0}/local/blueprint_validate_definitions_version.yaml'
            .format(BLUEPRINTS_DIR)
        )

    def test_init_validate_definitions_version_true(self):
        self.invoke(
            'cfy init {0}/local/blueprint_validate_definitions_version.yaml'
            .format(BLUEPRINTS_DIR),
            err_str_segment='description not supported in version',
            exception=DSLParsingLogicException
        )

    @patch('cloudify.workflows.local.init_env')
    @patch('cloudify_cli.local.install_plugins')
    def test_init_install_plugins(self, install_plugins_mock, *_):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            'blueprint_with_plugins.yaml'
        )
        command = 'cfy init {0} --install-plugins'.format(blueprint_path)

        self.invoke(command)
        install_plugins_mock.assert_called_with(blueprint_path=blueprint_path)

    @patch('cloudify.workflows.local.init_env')
    def test_init_with_empty_requirements(self, *_):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            'blueprint_without_plugins.yaml'
        )
        command = 'cfy init {0} --install-plugins'.format(blueprint_path)

        self.invoke(command)

    def test_init_missing_plugins(self):
        # TODO: this test was supposed to check possible solutions as well
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            'blueprint_with_plugins.yaml'
        )
        command = 'cfy init {0}'.format(blueprint_path)

        # Expecting to fail with an ImportError - when trying to access "tasks"
        output = self.invoke(command, should_fail=True)
        self.assertEqual(type(output.exception), ImportError)

    def test_no_init(self):
        cfy.purge_dot_cloudify()
        self.invoke('cfy profiles list',
                    err_str_segment='Cloudify environment is not initialized',
                    # TODO: put back
                    # possible_solutions=[
                    #     "Run 'cfy init' in this directory"
                    # ]
                    )
