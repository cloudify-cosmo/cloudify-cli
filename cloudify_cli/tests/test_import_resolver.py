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

import mock
import yaml

import cloudify
from cloudify.workflows import local
from cloudify_rest_client.nodes import Node
from cloudify_rest_client.node_instances import NodeInstance
import dsl_parser
from dsl_parser.constants import IMPORT_RESOLVER_KEY, \
    RESOLVER_IMPLEMENTATION_KEY, RESLOVER_PARAMETERS_KEY
from dsl_parser.import_resolver.default_import_resolver import \
    DefaultImportResolver

from cloudify_cli.bootstrap import bootstrap
from cloudify_cli.tests import cli_runner
from cloudify_cli import utils
from cloudify_cli.tests.commands.test_cli_command import \
    CliCommandTest, BLUEPRINTS_DIR


class CustomImportResolver(DefaultImportResolver):
    def __init__(self, param):
        if not param:
            raise ValueError('failed to initialize resolver')
        self.param = param


def update_config_file(resolver_configuration):
    config_path = utils.get_configuration_path()
    with open(config_path, 'a') as f:
        yaml.dump(resolver_configuration, f)


def create_resolver_configuration(implementation=None, parameters=None):
    import_resolver_config = {IMPORT_RESOLVER_KEY: {}}
    if implementation:
        import_resolver_config[IMPORT_RESOLVER_KEY][
            RESOLVER_IMPLEMENTATION_KEY] = implementation
    if parameters:
        import_resolver_config[IMPORT_RESOLVER_KEY][
            RESLOVER_PARAMETERS_KEY] = parameters
    return import_resolver_config


class GetImportResolverTests(CliCommandTest):

    def setUp(self):
        super(GetImportResolverTests, self).setUp()
        self._create_cosmo_wd_settings()

    def test_get_resolver(self):
        cli_runner.run_cli('cfy init -r')
        resolver_configuration = create_resolver_configuration(
            implementation='mock implementation',
            parameters='mock parameters')
        update_config_file(resolver_configuration=resolver_configuration)
        with mock.patch('dsl_parser.utils.create_import_resolver') as \
                mock_create_import_resolver:
            utils.get_import_resolver()
            mock_create_import_resolver.assert_called_once_with(
                resolver_configuration[IMPORT_RESOLVER_KEY])

    def test_get_custom_resolver(self):
        cli_runner.run_cli('cfy init -r')
        parameters = {'param': 'custom-parameter'}
        custom_resolver_class_path = "%s:%s" % (
            CustomImportResolver.__module__, CustomImportResolver.__name__)
        import_resolver_config = create_resolver_configuration(
            implementation=custom_resolver_class_path, parameters=parameters)
        update_config_file(resolver_configuration=import_resolver_config)
        resolver = utils.get_import_resolver()
        self.assertEqual(type(resolver), CustomImportResolver)
        self.assertEqual(resolver.param, 'custom-parameter')


class ImportResolverLocalUseTests(CliCommandTest):

    def setUp(self):
        super(ImportResolverLocalUseTests, self).setUp()
        self._create_cosmo_wd_settings()

    @mock.patch('cloudify_cli.utils.get_import_resolver')
    def _test_using_import_resolver(self,
                                    command,
                                    blueprint_path,
                                    mocked_module,
                                    mock_get_resolver):
        cli_runner.run_cli('cfy init -r')

        # create an import resolver
        parameters = {
            'rules':
                [{'rule1prefix': 'rule1replacement'}]
        }
        resolver = DefaultImportResolver(**parameters)
        # set the return value of mock_get_resolver -
        # this is the resolver we expect to be passed to
        # the parse_from_path method.
        mock_get_resolver.return_value = resolver

        # run the cli command and check that
        # parse_from_path was called with the expected resolver
        cli_command = 'cfy {0} -p {1}'.format(command, blueprint_path)
        kwargs = {
            'dsl_file_path': blueprint_path,
            'resolver': resolver,
            'validate_version': True
        }
        self.assert_method_called(
            cli_command, mocked_module, 'parse_from_path', kwargs)

    def test_validate_blueprint_uses_import_resolver(self):
        from cloudify_cli.commands import blueprints
        blueprint_path = '{0}/local/blueprint.yaml'.format(BLUEPRINTS_DIR)
        self._test_using_import_resolver(
            'blueprints validate', blueprint_path, blueprints)

    @mock.patch.object(local._Environment, 'execute')
    @mock.patch.object(dsl_parser.tasks, 'prepare_deployment_plan')
    def test_bootstrap_uses_import_resolver_for_parsing(self, *_):
        blueprint_path = '{0}/local/{1}.yaml'.format(
            BLUEPRINTS_DIR, 'blueprint')

        old_load_env = bootstrap.load_env
        old_init = cloudify.workflows.local.FileStorage.init
        old_get_nodes = cloudify.workflows.local.FileStorage.get_nodes
        old_get_node_instances = \
            cloudify.workflows.local.FileStorage.get_node_instances

        def mock_load_env(name):
            raise IOError('mock load env')
        bootstrap.load_env = mock_load_env

        def mock_init(self, name, plan, nodes, node_instances, blueprint_path,
                      provider_context):
            return 'mock init'
        bootstrap.local.FileStorage.init = mock_init

        def mock_get_nodes(self):
            return [
                Node({'id': 'mock_node',
                      'type_hierarchy': 'cloudify.nodes.CloudifyManager'})
            ]
        cloudify.workflows.local.FileStorage.get_nodes = mock_get_nodes

        def mock_get_node_instances(self):
            return [
                NodeInstance({'node_id': 'mock_node',
                              'runtime_properties': {
                                  'provider': 'mock_provider',
                                  'manager_ip': 'mock_manager_ip',
                                  'manager_user': 'mock_manager_user',
                                  'manager_key_path': 'mock_manager_key_path',
                                  'rest_port': 'mock_rest_port'}})
            ]
        cloudify.workflows.local.FileStorage.get_node_instances = \
            mock_get_node_instances

        try:
            self._test_using_import_resolver(
                'bootstrap', blueprint_path, dsl_parser.parser)
        finally:
            bootstrap.load_env = old_load_env
            bootstrap.local.FileStorage.init = old_init
            cloudify.workflows.local.FileStorage.get_nodes = old_get_nodes
            cloudify.workflows.local.FileStorage.get_node_instances = \
                old_get_node_instances

    @mock.patch('cloudify_cli.commands.local._storage', new=mock.MagicMock)
    @mock.patch('cloudify.workflows.local._prepare_nodes_and_instances')
    @mock.patch('dsl_parser.tasks.prepare_deployment_plan')
    def test_local_init(self, *_):
        blueprint_path = '{0}/local/{1}.yaml'.format(BLUEPRINTS_DIR,
                                                     'blueprint')
        self._test_using_import_resolver(
            'local init', blueprint_path, dsl_parser.parser)
