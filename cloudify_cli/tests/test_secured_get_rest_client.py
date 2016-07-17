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
import unittest

from cloudify_rest_client.client import DEFAULT_API_VERSION

from . import cfy
from .. import utils
from .. import constants

TRUST_ALL = 'non-empty-value'
CERT_PATH = 'path-to-certificate'


class TestGetRestClient(unittest.TestCase):

    def setUp(self):
        cfy.invoke('init -r')

        os.environ[constants.CLOUDIFY_USERNAME_ENV] = 'test_username'
        os.environ[constants.CLOUDIFY_PASSWORD_ENV] = 'test_password'
        os.environ[constants.CLOUDIFY_SSL_TRUST_ALL] = TRUST_ALL
        os.environ[constants.CLOUDIFY_SSL_CERT] = CERT_PATH

    def tearDown(self):

        del os.environ[constants.CLOUDIFY_USERNAME_ENV]
        del os.environ[constants.CLOUDIFY_PASSWORD_ENV]
        del os.environ[constants.CLOUDIFY_SSL_TRUST_ALL]
        del os.environ[constants.CLOUDIFY_SSL_CERT]

        cfy.purge_dot_cloudify()

    def test_get_rest_client(self):
        client = utils.get_rest_client(manager_ip='localhost',
                                       skip_version_check=True)
        self.assertIsNotNone(client._client.headers[
            constants.CLOUDIFY_AUTHENTICATION_HEADER])

    def test_get_secured_rest_client(self):
        protocol = 'https'
        host = 'localhost'
        port = 443
        skip_version_check = True

        client = utils.get_rest_client(
            manager_ip=host, rest_port=port, protocol=protocol,
            skip_version_check=skip_version_check)

        self.assertEqual(CERT_PATH, client._client.cert)
        self.assertTrue(client._client.trust_all)
        self.assertEqual('{0}://{1}:{2}/api/{3}'.format(
            protocol, host, port, DEFAULT_API_VERSION),
            client._client.url)
