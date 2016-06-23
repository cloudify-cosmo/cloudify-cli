from mock import MagicMock, patch

from ... import env
from .constants import SSL_PORT
from ...constants import API_VERSION
from .test_base import CliCommandTest

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.exceptions import UserUnauthorizedError


class UseTest(CliCommandTest):

    def test_use_command(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={
                'name': 'name',
                'context': {}}
        )
        self.invoke('cfy use 127.0.0.1')
        context = self._read_context()
        self.assertEquals("127.0.0.1", context.manager_ip)

    def test_use_attempt_by_unauthorized_user(self):
        with patch.object(self.client.manager, 'get_status') as mock:
            mock.side_effect = UserUnauthorizedError('Unauthorized user')
            self.invoke('cfy use 127.0.0.1',
                        err_str_segment='User is unauthorized')

    def test_use_command_no_prior_init(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={
                'name': 'name', 'context': {}
            }
        )
        self.invoke('cfy use 127.0.0.1')
        context = self._read_context()
        self.assertEquals('127.0.0.1', context.manager_ip)

    def test_use_with_user_and_port(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={
                'name': 'name', 'context': {}
            }
        )
        self.invoke('cfy use 127.0.0.1 -u test_user --manager-port 22222')
        context = self._read_context()
        self.assertEquals('127.0.0.1', context.manager_ip)
        self.assertEquals('22222', context.manager_port)
        self.assertEquals('test_user', context.manager_user)

    def test_use_with_authorization(self):
        host = '127.0.0.1'
        auth_header = env.get_auth_header('test_username', 'test_password')
        self.client = CloudifyClient(host=host, headers=auth_header)

        self._test_use()

        # assert Authorization in headers
        eventual_request_headers = self.client._client.headers
        self.assertEqual(self.do_request_headers, eventual_request_headers)

    def test_use_with_verify(self):
        host = 'localhost'
        self.client = CloudifyClient(host=host, protocol='https')
        self._test_use()
        self.assertEqual(self.request_url,
                         'https://{0}:{1}/api/{2}/status'.format(host,
                                                                 SSL_PORT,
                                                                 API_VERSION))
        self.assertTrue(self.verify)

    def test_use_trust_all(self):
        host = 'localhost'
        self.client = CloudifyClient(host=host,
                                     protocol='https', trust_all=True)
        self._test_use()
        self.assertEqual(self.request_url,
                         'https://{0}:{1}/api/{2}/status'.format(host,
                                                                 SSL_PORT,
                                                                 API_VERSION))
        self.assertFalse(self.verify)

    def _test_use(self):
        host = 'localhost'
        self.client.manager.get_context = MagicMock(
            return_value={
                'name': 'name',
                'context': {}
            }
        )

        self.headers = None
        self.request_url = None
        self.verify = None

        def mock_do_request(*_, **kwargs):
            self.do_request_headers = kwargs.get('headers')
            self.request_url = kwargs.get('request_url')
            self.verify = kwargs.get('verify')
            return 'success'

        with patch('cloudify_rest_client.client.HTTPClient._do_request',
                   new=mock_do_request):
            self.invoke('cfy use {0} --rest-port {1}'.format(
                host, self.client._client.port))
