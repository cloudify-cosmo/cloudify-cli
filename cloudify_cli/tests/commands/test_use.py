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

"""
Tests 'cfy use'
"""
import os
import unittest

from mock import MagicMock
from mock import patch

from cloudify_rest_client import CloudifyClient

from cloudify_cli import utils
from cloudify_cli.constants import CLOUDIFY_USERNAME_ENV, CLOUDIFY_PASSWORD_ENV

from cloudify_cli.tests import cli_runner
from cloudify_cli.tests.commands.test_cli_command import CliCommandTest


class UseTest(CliCommandTest):

    def test_use_command(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={
                'name': 'name',
                'context': {}}
        )
        self._create_cosmo_wd_settings()
        cli_runner.run_cli('cfy use -t 127.0.0.1')
        cwds = self._read_cosmo_wd_settings()
        self.assertEquals("127.0.0.1",
                          cwds.get_management_server())

    def test_use_command_no_prior_init(self):
        self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={
                'name': 'name', 'context': {}
            }
        )
        cli_runner.run_cli('cfy use -t 127.0.0.1')
        cwds = self._read_cosmo_wd_settings()
        self.assertEquals('127.0.0.1', cwds.get_management_server())

    def test_use_secured(self):
        host = '127.0.0.1'
        username = 'test_username'
        password = 'test_password'
        self.client = CloudifyClient(
            host=host, user=username, password=password)
        # self.client.manager.get_status = MagicMock()
        self.client.manager.get_context = MagicMock(
            return_value={
                'name': 'name',
                'context': {}
            }
        )
        with patch('cloudify_rest_client.client.HTTPClient._do_request') \
                as mock_do_request:
            cli_runner.run_cli('cfy use -t {0}'.format(host))

        # assert headers
        call_args_list = mock_do_request.call_args_list[0][0]
        self.assertIn('http://{0}:80/status'.format(host), call_args_list)
        headers = {
            'Content-type': 'application/json',
            'Authorization': self.client._client.encoded_credentials
        }
        self.assertIn(headers, call_args_list)


class TestGetRestClient(unittest.TestCase):
    def test_get_rest_client(self):
        os.environ[CLOUDIFY_USERNAME_ENV] = 'test_username'
        os.environ[CLOUDIFY_PASSWORD_ENV] = 'test_password'
        try:
            client = utils.get_rest_client(
                manager_ip='localhost', rest_port=80)
            self.assertIsNotNone(client._client.encoded_credentials)
        finally:
            del os.environ[CLOUDIFY_USERNAME_ENV]
            del os.environ[CLOUDIFY_PASSWORD_ENV]
