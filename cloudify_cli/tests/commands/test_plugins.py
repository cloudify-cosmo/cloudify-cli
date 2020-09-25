import os
import inspect
import tempfile
import unittest
from collections import namedtuple

from mock import PropertyMock, patch, Mock, call

from .constants import PLUGINS_DIR
from .mocks import MockMetadata, MockListResponse
from .test_base import CliCommandTest
from ..cfy import ClickInvocationException

from cloudify.models_states import PluginInstallationState
from cloudify_rest_client import plugins, plugins_update, manager

from cloudify_cli.constants import DEFAULT_TENANT_NAME
from cloudify_cli.exceptions import (CloudifyCliError,
                                     SuppressedCloudifyCliError)
from cloudify_cli.commands.plugins import _format_installation_state


class MockPaginationWithSize(dict):

    def __init__(self, total=0, size=0):
        self.total = total
        self.size = size


class MockListResponseWithPaginationSize(MockListResponse):

    def __init__(self, items=[], pagination_total=1000, _=None):
        self.items = items
        self.metadata = MockMetadata(pagination=MockPaginationWithSize(
            pagination_total, len(items)))
        self._iter_has_been_called = False
        self._len_has_been_called = False

    def __iter__(self):
        if not self._iter_has_been_called:
            self._iter_has_been_called = True
            return iter(self.items)
        return iter([])

    def __len__(self):
        if not self._len_has_been_called:
            self._len_has_been_called = True
            return len(self.items)
        return 0


class PluginsTest(CliCommandTest):

    def setUp(self):
        super(PluginsTest, self).setUp()
        self.use_manager()

    def test_plugins_list(self):
        self.client.plugins.list = Mock(return_value=MockListResponse())
        self.invoke('cfy plugins list')
        self.invoke('cfy plugins list -t dummy_tenant')
        self.invoke('cfy plugins list -a')

    def test_plugin_get(self):
        self.client.plugins.get = Mock(
            return_value=plugins.Plugin({
                'id': 'id',
                'package_name': 'dummy',
                'package_version': '1.2',
                'supported_platform': 'any',
                'distribution_release': 'trusty',
                'distribution': 'ubuntu',
                'uploaded_at': 'now',
                'visibility': 'private',
                'created_by': 'admin',
                'tenant_name': DEFAULT_TENANT_NAME,
                'installation_state': []
            })
        )

        self.invoke('cfy plugins get some_id')

    def test_plugins_delete(self):
        self.client.plugins.delete = Mock()
        self.invoke('cfy plugins delete a-plugin-id')

    def test_plugins_delete_force(self):
        for flag in ['--force', '-f']:
            mock = Mock()
            self.client.plugins.delete = mock
            self.invoke('cfy plugins delete a-plugin-id {0}'.format(
                flag))
            mock.assert_called_once_with(plugin_id='a-plugin-id', force=True)

    def test_plugins_upload(self):
        self.client.plugins.upload = Mock()
        with tempfile.NamedTemporaryFile() as empty_file:
            self.invoke('plugins upload {0} -y {0}'.format(empty_file.name))

    def test_plugins_download(self):
        self.client.plugins.download = Mock(return_value='some_file')
        self.invoke('cfy plugins download a-plugin-id')

    def test_plugins_set_global(self):
        self.client.plugins.set_global = Mock()
        self.invoke('cfy plugins set-global a-plugin-id')

    def test_plugins_set_visibility(self):
        self.client.plugins.set_visibility = Mock()
        self.invoke('cfy plugins set-visibility a-plugin-id -l global')

    def test_plugins_set_visibility_invalid_argument(self):
        self.invoke('cfy plugins set-visibility a-plugin-id -l private',
                    err_str_segment='Invalid visibility: `private`',
                    exception=CloudifyCliError)

    def test_plugins_set_visibility_missing_argument(self):
        outcome = self.invoke('cfy plugins set-visibility a-plugin-id',
                              err_str_segment='2',
                              exception=SystemExit)
        self.assertIn('missing option', outcome.output.lower())
        self.assertIn('--visibility', outcome.output)

    def test_blueprints_set_visibility_wrong_argument(self):
        outcome = self.invoke('cfy plugins set-visibility a-plugin-id -g',
                              err_str_segment='2',
                              exception=SystemExit)
        self.assertIn('Error: no such option: -g', outcome.output)

    def test_plugins_upload_mutually_exclusive_arguments(self):
        outcome = self.invoke(
            'cfy plugins upload --private-resource -l tenant',
            err_str_segment='2',  # Exit code
            exception=SystemExit
        )
        self.assertIn('mutually exclusive with arguments:', outcome.output)

    def test_plugins_upload_invalid_argument(self):
        yaml_path = os.path.join(PLUGINS_DIR, 'plugin.yaml')
        self.invoke('cfy plugins upload {0} -l bla -y {1}'.
                    format(yaml_path, yaml_path),
                    err_str_segment='Invalid visibility: `bla`',
                    exception=CloudifyCliError)

    def test_plugins_upload_with_visibility(self):
        self.client.plugins.upload = Mock()
        yaml_path = os.path.join(PLUGINS_DIR, 'plugin.yaml')
        self.invoke('cfy plugins upload {0} -l private -y {1}'
                    .format(yaml_path, yaml_path))

    def test_plugins_upload_with_icon(self):
        self.client.plugins.upload = Mock()
        self.client.plugins.upload = Mock()
        with tempfile.NamedTemporaryFile() as empty_file:
            self.invoke('plugins upload {0} -y {0} -i {0}'
                        .format(empty_file.name))

    def test_plugins_upload_with_title(self):
        self.client.plugins.upload = Mock()
        yaml_path = os.path.join(PLUGINS_DIR, 'plugin.yaml')
        self.invoke('cfy plugins upload {0} -y {1} --title "{2}"'
                    .format(yaml_path, yaml_path, 'test title'))


class PluginsInstallTest(CliCommandTest):
    def setUp(self):
        super(PluginsInstallTest, self).setUp()
        self.sleep_mock = patch('cloudify_cli.commands.plugins.time.sleep')
        self.sleep_mock.start()
        self.addCleanup(self.sleep_mock.stop)

    def _make_plugins_state(self, managers=None, agents=None):
        managers = managers or {}
        agents = agents or {}
        states = [
            {'manager': name, 'state': state}
            for name, state in managers.items()
        ] + [
            {'agent': name, 'state': state}
            for name, state in agents.items()
        ]
        return {'installation_state': states}

    def test_plugin_install(self):
        """With no params, we install on all managers"""
        hostname = 'manager1'
        plugin_id = 'plugin-id'
        self.client.manager.get_managers = Mock(return_value=[
            manager.ManagerItem({'hostname': hostname})
        ])
        self.client.plugins.install = Mock(return_value={})
        self.client.plugins.get = Mock(return_value=self._make_plugins_state({
            hostname: PluginInstallationState.INSTALLED
        }))
        self.invoke('plugins install {0}'.format(plugin_id))
        self.client.plugins.install.assert_called_once_with(
            plugin_id,
            agents=(),
            managers=[hostname]
        )

    def test_plugin_install_timeout(self):
        """With no params, we install on all managers"""
        hostname = 'manager1'
        plugin_id = 'plugin-id'
        self.client.manager.get_managers = Mock(return_value=[
            manager.ManagerItem({'hostname': hostname})
        ])
        self.client.plugins.install = Mock(return_value={})
        self.invoke('plugins install {0} --timeout 0'.format(plugin_id),
                    err_str_segment='Timed out')

    def test_plugin_install_managers(self):
        plugin_id = 'plugin-id'
        self.client.plugins.install = Mock(return_value={})
        self.client.plugins.get = Mock(return_value=self._make_plugins_state(
            {'mgr1': PluginInstallationState.INSTALLED,
             'mgr2': PluginInstallationState.INSTALLED}
        ))
        self.invoke('plugins install {0} '
                    '--manager-hostname mgr1 '
                    '--manager-hostname mgr2 '
                    .format(plugin_id))
        self.client.plugins.install.assert_called_once_with(
            'plugin-id',
            agents=(),
            managers=('mgr1', 'mgr2')
        )

    def test_plugin_install_agents(self):
        plugin_id = 'plugin-id'
        self.client.plugins.install = Mock(return_value={})
        self.client.plugins.get = Mock(return_value=self._make_plugins_state(
            None, {'agent1': PluginInstallationState.INSTALLED}
        ))
        self.invoke('plugins install {0} '
                    '--agent-name agent1 '
                    .format(plugin_id))
        self.client.plugins.install.assert_called_once_with(
            'plugin-id',
            agents=('agent1',),
            managers=()
        )

    def test_plugin_install_wait(self):
        plugin_id = 'plugin-id'
        self.client.plugins.install = Mock(return_value={})
        self.client.plugins.get = Mock(side_effect=[
            self._make_plugins_state({
                'mgr1': PluginInstallationState.INSTALLING
            }),
            self._make_plugins_state({
                'mgr1': PluginInstallationState.INSTALLED
            }),
            RuntimeError('should not be called')
        ])
        self.invoke('plugins install {0} --manager-hostname mgr1'
                    .format(plugin_id))
        self.client.plugins.get.assert_has_calls([
            call(plugin_id),
            call(plugin_id)
        ])

    def test_plugin_install_wait_agent_and_manager(self):
        plugin_id = 'plugin-id'
        self.client.plugins.install = Mock(return_value={})
        self.client.plugins.get = Mock(side_effect=[
            # first, both are installing
            self._make_plugins_state(
                {'mgr1': PluginInstallationState.INSTALLING},
                {'ag1': PluginInstallationState.INSTALLING},
            ),
            # then, manager is installed, and agent is still installing
            self._make_plugins_state(
                {'mgr1': PluginInstallationState.INSTALLED},
                {'ag1': PluginInstallationState.INSTALLING},
            ),
            # and then both the agent and the manager are installed
            self._make_plugins_state(
                {'mgr1': PluginInstallationState.INSTALLED},
                {'ag1': PluginInstallationState.INSTALLED},
            ),
            RuntimeError('should not be called')
        ])
        self.invoke('plugins install {0} '
                    '--manager-hostname mgr1 '
                    '--agent-name ag1'
                    .format(plugin_id))
        self.client.plugins.get.assert_has_calls([
            call(plugin_id),
            call(plugin_id),
            call(plugin_id)
        ])

    def test_plugin_install_error(self):
        plugin_id = 'plugin-id'
        self.client.plugins.install = Mock(return_value={})
        self.client.plugins.get = Mock(return_value={
            'installation_state': [{
                'manager': 'mgr1',
                'error': 'error text here',
                'state': PluginInstallationState.ERROR
            }]
        })
        out = self.invoke(
            'plugins install {0} --manager-hostname mgr1'.format(plugin_id),
            err_str_segment='errors')
        assert 'error text here' in out.logs
        self.client.plugins.get.assert_has_calls([
            call(plugin_id),
        ])


class PluginsUpdateTest(CliCommandTest):

    def _mock_wait_for_executions(self, value):
        patcher = patch(
            'cloudify_cli.execution_events_fetcher.wait_for_execution',
            Mock(return_value=PropertyMock(error=value))
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    def setUp(self):
        super(PluginsUpdateTest, self).setUp()
        self.use_manager()
        self.client.executions = Mock()
        self.client.plugins_update = Mock()
        self._mock_wait_for_executions(False)

    def _inspect_calls(self, update_client_mock,
                       arg_name_to_retrieve=None,
                       number_of_calls=1):
        calls = update_client_mock.mock_calls
        self.assertEqual(len(calls), number_of_calls)
        _, args, kwargs = calls[0]
        call_args = inspect.getcallargs(
            plugins_update.PluginsUpdateClient(None).update_plugins,
            *args, **kwargs)
        if arg_name_to_retrieve:
            self.assertIn(arg_name_to_retrieve, call_args)
            return call_args[arg_name_to_retrieve]

    def test_plugins_get(self):
        self.client.plugins_update.get = Mock(
            return_value=plugins_update.PluginsUpdate({
                'id': 'asdf'
            }))
        outcome = self.invoke('cfy plugins get-update asdf')
        self.assertEqual(2, outcome.output.count('asdf'))
        self.assertNotRegex('(?i)error|fail', outcome.output)

    def test_plugins_list(self):
        _plugins = MockListResponse([
            plugins_update.PluginsUpdate({'id': 'asdf'}),
            plugins_update.PluginsUpdate({'id': 'fdsa'})
        ])
        _plugins.metadata.pagination.total = 2
        self.client.plugins_update.list = Mock(return_value=_plugins)
        outcome = self.invoke('cfy plugins history')
        self.assertIn('asdf', outcome.output)
        self.assertIn('fdsa', outcome.output)
        self.assertNotRegex('(?i)error|fail', outcome.output)

    def test_plugins_list_of_blueprint(self):
        plugins_updates = [
            {'blueprint_id': 'b1_blueprint'},
            {'blueprint_id': 'b1_blueprint'},
            {'blueprint_id': 'b2_blueprint'}
        ]

        self.client.plugins_update.list = Mock(
            return_value=MockListResponse(items=plugins_updates)
        )
        outcome = self.invoke('cfy plugins history -b b1_blueprint -v')
        self.assertNotIn('b2_blueprint', outcome.logs)
        self.assertIn('b1_blueprint', outcome.logs)

    def test_plugins_update_successful(self):
        self.client.plugins_update.update_plugins = Mock()
        outcome = self.invoke('cfy plugins update asdf')
        self.assertIn('Updating the plugins of the deployments of the '
                      'blueprint asdf', outcome.logs)
        self.assertIn('Finished executing workflow', outcome.logs)
        self.assertIn('Successfully updated plugins for blueprint asdf.',
                      outcome.logs)

    def test_update_force_flag_is_false(self):
        update_client_mock = Mock()
        self.client.plugins_update.update_plugins = update_client_mock
        self.invoke('cfy plugins update asdf')

        calls = update_client_mock.mock_calls
        self.assertEqual(len(calls), 1)
        _, args, kwargs = calls[0]
        call_args = inspect.getcallargs(
            plugins_update.PluginsUpdateClient(None).update_plugins,
            *args, **kwargs)

        self.assertIn('force', call_args)
        self.assertFalse(call_args['force'])

    def test_update_force_flag_is_true(self):
        update_client_mock = Mock()
        self.client.plugins_update.update_plugins = update_client_mock
        self.invoke('cfy plugins update asdf --force')

        is_force = self._inspect_calls(update_client_mock, 'force')
        self.assertTrue(is_force)

    def test_plugins_update_failure(self):
        self._mock_wait_for_executions(True)
        outcome = self.invoke(
            'cfy plugins update asdf',
            err_str_segment='',
            exception=SuppressedCloudifyCliError)

        logs = outcome.logs.split('\n')
        self.assertIn('Updating the plugins of the deployments of the '
                      'blueprint asdf', logs[-3])
        self.assertIn('Execution of workflow', logs[-2])
        self.assertIn('failed', logs[-2])
        self.assertIn('Failed updating plugins for blueprint asdf', logs[-1])

    def test_params_all_xor_blueprint_id(self):
        update_client_mock = Mock()
        bp_list_client_mock = Mock(
            return_value=MockListResponseWithPaginationSize(items=[]))

        self.client.plugins_update.update_plugins = update_client_mock
        self.client.blueprints.list = bp_list_client_mock
        self.invoke('cfy plugins update --all')
        self.assertEqual(len(update_client_mock.mock_calls), 0)
        self.assertEqual(len(bp_list_client_mock.mock_calls), 1)

        self.invoke('cfy plugins update asdf')
        self.assertEqual(len(update_client_mock.mock_calls), 1)
        self.assertEqual(len(bp_list_client_mock.mock_calls), 1)

        self.assertRaises(ClickInvocationException,
                          self.invoke,
                          'cfy plugins update --all asdf')

        self.assertRaises(ClickInvocationException,
                          self.invoke,
                          'cfy plugins update asdf --all')

    def test_all(self):
        bp = namedtuple('Blueprint', 'id')
        update_client_mock = Mock()
        bp_list_client_mock = Mock(
            return_value=MockListResponseWithPaginationSize(
                items=[bp(id='asdf'), bp(id='zxcv')]))
        self.client.plugins_update.update_plugins = update_client_mock
        self.client.blueprints.list = bp_list_client_mock
        self.invoke('cfy plugins update --all')
        self.assertEqual(len(bp_list_client_mock.mock_calls), 2)
        self.assertEqual(len(update_client_mock.mock_calls), 2)
        self.assertListEqual(
            list(update_client_mock.call_args_list),
            [call('asdf', force=False, plugin_names=[],
                  to_latest=[], all_to_latest=True,
                  to_minor=[], all_to_minor=False,
                  mapping=None),
             call('zxcv', force=False, plugin_names=[],
                  to_latest=[], all_to_latest=True,
                  to_minor=[], all_to_minor=False,
                  mapping=None)])

    def test_params_plugin_name_syntax_error(self):
        update_client_mock = Mock()
        self.client.plugins_update.update_plugins = update_client_mock
        self.assertRaises(ClickInvocationException,
                          self.invoke,
                          'cfy plugins update --plugin-name asdf')

    def test_params_plugin_name(self):
        update_plugin_name = 'plugin-name'
        update_client_mock = Mock()
        self.client.plugins_update.update_plugins = update_client_mock
        self.invoke('cfy plugins update --plugin-name {0} asdf'.format(
            update_plugin_name))

        a_plugin_names = self._inspect_calls(update_client_mock,
                                             'plugin_names')
        self.assertListEqual(a_plugin_names, [update_plugin_name])

    def test_params_all_to_minor(self):
        update_client_mock = Mock()
        self.client.plugins_update.update_plugins = update_client_mock
        self.invoke('cfy plugins update --all-to-minor asdf')

        is_minor = self._inspect_calls(update_client_mock, 'all_to_minor')
        self.assertTrue(is_minor)

    def test_params_to_minor_multiple(self):
        update_client_mock = Mock()
        self.client.plugins_update.update_plugins = update_client_mock
        self.invoke('cfy plugins update --to-minor plugin1-name '
                    '--to-minor plugin2-name asdf')

        to_minor_list = self._inspect_calls(update_client_mock, 'to_minor')
        self.assertListEqual(to_minor_list, ['plugin1-name', 'plugin2-name'])

    def test_params_to_minor_comma_separated(self):
        update_client_mock = Mock()
        self.client.plugins_update.update_plugins = update_client_mock
        self.invoke('cfy plugins update --to-minor '
                    'plugin1-name,plugin2-name asdf')

        to_minor_list = self._inspect_calls(update_client_mock, 'to_minor')
        self.assertListEqual(to_minor_list, ['plugin1-name', 'plugin2-name'])

    def test_params_all_to_latest(self):
        update_client_mock = Mock()
        self.client.plugins_update.update_plugins = update_client_mock
        self.invoke('cfy plugins update --all-to-latest asdf')

        is_latest = self._inspect_calls(update_client_mock, 'all_to_latest')
        self.assertTrue(is_latest)

    def test_params_to_latest_multiple(self):
        update_client_mock = Mock()
        self.client.plugins_update.update_plugins = update_client_mock
        self.invoke('cfy plugins update --all-to-minor '
                    '--to-latest plugin1-name --to-latest plugin2-name asdf')

        latest_list = self._inspect_calls(update_client_mock, 'to_latest')
        self.assertListEqual(latest_list, ['plugin1-name', 'plugin2-name'])

    def test_params_to_latest_comma_separated(self):
        update_client_mock = Mock()
        self.client.plugins_update.update_plugins = update_client_mock
        self.invoke('cfy plugins update --all-to-minor '
                    '--to-latest plugin1-name,plugin2-name asdf')

        latest_list = self._inspect_calls(update_client_mock, 'to_latest')
        self.assertListEqual(latest_list, ['plugin1-name', 'plugin2-name'])

    def test_params_all_to_minor_xor_to_minor(self):
        update_client_mock = Mock()
        self.client.plugins_update.update_plugins = update_client_mock
        self.assertRaises(ClickInvocationException,
                          self.invoke,
                          'cfy plugins update --all-to-minor '
                          '--to-minor plugin1-name asdf')

    def test_params_all_to_latest_xor_to_latest(self):
        update_client_mock = Mock()
        self.client.plugins_update.update_plugins = update_client_mock
        self.assertRaises(ClickInvocationException,
                          self.invoke,
                          'cfy plugins update --all-to-latest '
                          '--to-latest plugin1-name asdf')

    def test_params_all_to_latest_xor_all_to_minor(self):
        update_client_mock = Mock()
        self.client.plugins_update.update_plugins = update_client_mock
        self.assertRaises(ClickInvocationException,
                          self.invoke,
                          'cfy plugins update '
                          '--all-to-latest --all-to-minor asdf')


class TestFormatInstallationState(unittest.TestCase):
    """Tests for the _format_installation_state util"""
    def test_empty(self):
        assert _format_installation_state({}) == ''
        assert _format_installation_state({
            'installation_state': []
        }) == ''

    def test_managers(self):
        assert _format_installation_state({
            'installation_state': [
                {
                    'manager': 'mgr1',
                    'state': PluginInstallationState.INSTALLED
                },
                {
                    'manager': 'mgr2',
                    'state': PluginInstallationState.INSTALLED
                }
            ]
        }) == '2 managers'

    def test_other_states(self):
        assert _format_installation_state({
            'installation_state': [
                {
                    'manager': 'mgr1',
                    'state': PluginInstallationState.INSTALLING
                },
                {
                    'manager': 'mgr2',
                    'state': PluginInstallationState.UNINSTALLED
                },
                {
                    'manager': 'mgr3',
                    'state': 'some unknown state'
                }
            ]
        }) == ''

    def test_managers_agents(self):
        assert _format_installation_state({
            'installation_state': [
                {
                    'manager': 'mgr1',
                    'state': PluginInstallationState.INSTALLED
                },
                {
                    'agent': 'ag1',
                    'state': PluginInstallationState.INSTALLED
                }
            ]
        }) == '1 managers, 1 agents'

    def test_managers_agents_errors(self):
        assert _format_installation_state({
            'installation_state': [
                {
                    'manager': 'mgr1',
                    'state': PluginInstallationState.INSTALLED
                },
                {
                    'agent': 'ag1',
                    'state': PluginInstallationState.INSTALLED
                },
                {
                    'state': PluginInstallationState.ERROR
                }
            ]
        }) == '1 managers, 1 agents, 1 errors'
