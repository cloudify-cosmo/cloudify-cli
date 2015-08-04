########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import os
import tempfile
import unittest
import shutil

from cloudify_cli import utils
from cloudify_cli import constants
from cloudify_cli.tests import cli_runner

TRUST_ALL = 'non-empty-value'
CERT_PATH = 'path-to-certificate'
API_VERSION = 'v2'


class TestGetRestClient(unittest.TestCase):

    def setUp(self):

        self.test_dir = os.path.join('/tmp', 'cloudify-cli-unit-tests')
        os.makedirs(self.test_dir)
        test_workdir = tempfile.mkdtemp(dir=self.test_dir)
        utils.get_cwd = lambda: test_workdir
        os.chdir(test_workdir)

        cli_runner.run_cli('cfy init -r')

        os.environ[constants.CLOUDIFY_USERNAME_ENV] = 'test_username'
        os.environ[constants.CLOUDIFY_PASSWORD_ENV] = 'test_password'
        os.environ[constants.CLOUDIFY_SSL_TRUST_ALL] = TRUST_ALL
        os.environ[constants.CLOUDIFY_SSL_CERT] = CERT_PATH

    def tearDown(self):

        del os.environ[constants.CLOUDIFY_USERNAME_ENV]
        del os.environ[constants.CLOUDIFY_PASSWORD_ENV]
        del os.environ[constants.CLOUDIFY_SSL_TRUST_ALL]
        del os.environ[constants.CLOUDIFY_SSL_CERT]

        shutil.rmtree(self.test_dir)

    def test_get_rest_client(self):
        client = utils.get_rest_client(manager_ip='localhost')
        self.assertIsNotNone(client._client.headers[
            constants.CLOUDIFY_AUTHENTICATION_HEADER])

    def test_get_secured_rest_client(self):
        protocol = 'https'
        host = 'localhost'
        port = 443

        client = utils.get_rest_client(
            manager_ip=host, rest_port=port, protocol=protocol)

        self.assertEqual(CERT_PATH, client._client.cert)
        self.assertTrue(client._client.trust_all)
        self.assertEqual('{0}://{1}:{2}/api/{3}'.format(
            protocol, host, port, API_VERSION),
            client._client.url)
