import os
import json
import shutil

import yaml
from mock import patch

from dsl_parser.exceptions import DSLParsingLogicException

from .. import cfy
from ... import env
from ...config import config
from ...commands import init
from .test_base import CliCommandTest
from .constants import (
    BLUEPRINTS_DIR, SAMPLE_INPUTS_PATH, RESOURCES_DIR,
    DEFAULT_BLUEPRINT_FILE_NAME, SAMPLE_CUSTOM_NAME_ARCHIVE
)


class InitTest(CliCommandTest):
    def setUp(self):
        super(InitTest, self).setUp()
        self.use_local_profile()

    def test_init_initialized_directory(self):
        self.use_manager()
        self.invoke(
            'cfy init',
            err_str_segment='Environment is already initialized')

    def test_init_overwrite(self):
        # Config values shouldn't change between init resets
        with open(config.CLOUDIFY_CONFIG_PATH) as f:
            conf = yaml.safe_load(f.read())

        self.assertFalse(conf['colors'])
        with open(config.CLOUDIFY_CONFIG_PATH, 'w') as f:
            conf['colors'] = True
            f.write(yaml.safe_dump(conf))

        cfy.invoke('init -r')
        with open(config.CLOUDIFY_CONFIG_PATH) as f:
            conf = yaml.safe_load(f.read())

        self.assertTrue(conf['colors'])

    def test_init_overwrite_hard(self):
        # Config values should change between hard init resets
        with open(config.CLOUDIFY_CONFIG_PATH) as f:
            conf = yaml.safe_load(f.read())

        self.assertFalse(conf['colors'])
        with open(config.CLOUDIFY_CONFIG_PATH, 'w') as f:
            conf['colors'] = True
            f.write(yaml.safe_dump(conf))

        self.invoke('cfy init -r --hard')
        with open(config.CLOUDIFY_CONFIG_PATH) as f:
            conf = yaml.safe_load(f.read())

        self.assertFalse(conf['colors'])

    def test_init_overwrite_on_initial_init(self):
        # Simply verifying the overwrite flag doesn't break the first init
        cfy.purge_dot_cloudify()
        self.invoke('cfy init -r')

    def test_init_invalid_blueprint_path(self):
        self.invoke(
            'cfy init idonotexist.yaml',
            err_str_segment='You must provide either a path to a local file',
        )

    def test_init_default_outputs(self):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )
        self.invoke('cfy init {0}'.format(blueprint_path))

        output = json.loads(self.invoke(
            'cfy deployments outputs -b local').output)
        self.assertEqual(output, {
            'key1': 'default_val1',
            'key2': 'default_val2',
            'key3': 'default_val3',
            'param': None,
            'custom_param': None,
            'provider_context': None
        })

    def test_init_default_inputs(self):
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            DEFAULT_BLUEPRINT_FILE_NAME
        )
        command = 'cfy init {0}'.format(blueprint_path)

        self.invoke(command)

        output = json.loads(self.invoke(
            'cfy deployments inputs -b local').output)
        self.assertEqual(output, {
            'key1': 'default_val1',
            'key2': 'default_val2',
            'key3': 'default_val3'
        })

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

        output = json.loads(self.invoke(
            'cfy deployments inputs -b local').output)
        self.assertEqual(output, {
            'key1': 'val1',
            'key2': 'val2',
            'key3': 'val3'
        })

    def test_init_validate_definitions_version_false(self):
        with open(config.CLOUDIFY_CONFIG_PATH) as f:
            conf = yaml.safe_load(f.read())
        with open(config.CLOUDIFY_CONFIG_PATH, 'w') as f:
            conf['validate_definitions_version'] = False
            f.write(yaml.safe_dump(conf))
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
    @patch('cloudify_cli.local._install_plugins')
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
        # TODO: put back possible solutions
        blueprint_path = os.path.join(
            BLUEPRINTS_DIR,
            'local',
            'blueprint_with_plugins.yaml'
        )

        self.invoke(
            'cfy init {0}'.format(blueprint_path),
            err_str_segment='mapping error: No module named tasks',
            exception=ImportError
        )

    def test_no_init(self):
        # make sure no error is thrown
        cfy.purge_dot_cloudify()
        self.invoke('cfy profiles list')

    def test_init_blueprint_archive_default_name(self):
        self.invoke(
            'cfy init {0}'.format(SAMPLE_CUSTOM_NAME_ARCHIVE),
            err_str_segment='Could not find `blueprint.yaml`'
        )

    def test_init_blueprint_archive(self):
        self.invoke(
            'cfy init {0} -b local -n simple_blueprint.yaml'
            .format(SAMPLE_CUSTOM_NAME_ARCHIVE)
        )

        output = json.loads(self.invoke(
            'cfy deployments inputs -b local').output)
        self.assertEqual(output, {
            'key1': 'default_val1',
            'key2': 'default_val2',
            'key3': 'default_val3',
        })

    def test_set_config(self):
        shutil.rmtree(env.CLOUDIFY_WORKDIR)
        os.makedirs(env.CLOUDIFY_WORKDIR, mode=0o700)
        self.assertFalse(os.path.isfile(
            os.path.join(env.CLOUDIFY_WORKDIR, 'config.yaml')))
        init.set_config()
        self.assertTrue(os.path.isfile(
            os.path.join(env.CLOUDIFY_WORKDIR, 'config.yaml')))


class LocalProfileUpdateTest(CliCommandTest):
    def setUp(self):
        shutil.copytree(
            os.path.join(RESOURCES_DIR, 'old_local_profile'),
            os.path.join(env.CLOUDIFY_WORKDIR, 'profiles', 'local')
        )
        super(LocalProfileUpdateTest, self).setUp()
        self.use_local_profile()

    def test_list_blueprints(self):
        out = self.invoke('blueprints list --json')
        blueprints = json.loads(out.output)
        assert len(blueprints) == 1
        assert {'bp1'} == {b['id'] for b in blueprints}

    def test_list_executions(self):
        out = self.invoke('executions list -b bp1 --json')
        executions = json.loads(out.output)
        assert len(executions) == 1

    def test_get_outputs(self):
        out = self.invoke('deployments outputs -b bp1')
        outputs = json.loads(out.output)
        assert outputs['out1'] == 1

    def test_run_execution(self):
        self.invoke('executions start -b bp1 '
                    'execute_operation -p operation=int1.op1')
        out = self.invoke('deployments outputs -b bp1')
        outputs = json.loads(out.output)
        assert outputs['out1'] == 2
