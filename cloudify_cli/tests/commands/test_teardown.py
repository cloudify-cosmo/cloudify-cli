from mock import patch, MagicMock

from .. import env
from .test_base import CliCommandTest
from ...constants import DEFAULT_TENANT_NAME

from cloudify_rest_client.exceptions import CloudifyClientError


class TeardownTest(CliCommandTest):

    def _use_manager(self):
        self.invoke('cfy profiles use 10.0.0.1 -u admin -p admin '
                    '-t {0}'.format(DEFAULT_TENANT_NAME))

    def test_teardown_no_force(self):
        self.use_manager()
        self.invoke('cfy teardown',
                    'This action requires additional confirmation.')

    @patch('cloudify_cli.bootstrap.bootstrap.teardown')
    def test_teardown_has_existing_deployments_ignore_deployments(self, mock_teardown):  # NOQA
        self.client.manager.get_status = MagicMock()
        self.client.deployments.list = MagicMock(return_value=[{}])
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        self._use_manager()
        env.profile = env.get_profile_context(suppress_error=True)
        self.invoke('cfy teardown -f --ignore-deployments')
        mock_teardown.assert_called_once_with(
            task_retries=0,
            task_retry_interval=1,
            task_thread_pool_size=1
        )

    def test_teardown_has_existing_deployments_dont_ignore_deployments(self):
        self.client.manager.get_status = MagicMock()
        self.client.deployments.list = MagicMock(return_value=[{}])
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        self._use_manager()
        env.profile = env.get_profile_context(suppress_error=True)
        self.invoke('cfy teardown -f',
                    'has existing deployments')

    def test_teardown_manager_down_dont_ignore_deployments(self):
        self.client.manager.get_status = MagicMock()

        def raise_client_error():
            raise CloudifyClientError('CloudifyClientError')

        self.client.deployments.list = raise_client_error
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )
        self._use_manager()
        env.profile = env.get_profile_context(suppress_error=True)
        self.invoke('cfy teardown -f',
                    'The manager may be down')

    @patch('cloudify_cli.bootstrap.bootstrap.teardown')
    def test_teardown_manager_down_ignore_deployments(self, mock_teardown):
        def raise_client_error():
            raise CloudifyClientError('this is an IOError')

        self.client.deployments.list = raise_client_error
        self.client.manager.get_context = MagicMock(
            return_value={'name': 'mock_provider', 'context': {'key': 'value'}}
        )

        self.use_manager(manager_ip='10.0.0.1')
        env.profile = env.get_profile_context(suppress_error=True)
        self.invoke('cfy teardown -f --ignore-deployments')
        mock_teardown.assert_called_once_with(
            task_retries=0,
            task_retry_interval=1,
            task_thread_pool_size=1
        )

    @patch('cloudify_cli.bootstrap.bootstrap.teardown')
    def test_teardown_default_values(self, mock_teardown):

        self.client.deployments.list = MagicMock(return_value=[])
        self.use_manager(manager_ip='10.0.0.1')

        self.invoke('cfy teardown -f')
        mock_teardown.assert_called_once_with(
            task_retries=0,
            task_retry_interval=1,
            task_thread_pool_size=1
        )

    @patch('cloudify_cli.bootstrap.bootstrap.teardown')
    def test_teardown_custom_values(self, mock_teardown):

        self.client.deployments.list = MagicMock(return_value=[])
        self.use_manager(host='10.0.0.1')

        self.invoke('cfy teardown -f '
                    '--task-retries 7 '
                    '--task-retry-interval 14 '
                    '--task-thread-pool-size 87')
        mock_teardown.assert_called_once_with(
            task_retries=7,
            task_retry_interval=14,
            task_thread_pool_size=87
        )
