########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

import unittest
import mock

from cloudify_cli.provider_common import BaseProviderClass


class ProviderCommonTest(unittest.TestCase):

    def test_resources_names_updater(self):
        provider_config = self._create_provider_config_with_prefix()
        pm = SomeProvider(provider_config, False)
        self.assertEquals(pm.get_updated_resource_name('x'), 'PFX_x')

    def test_files_names_updater(self):
        provider_config = self._create_provider_config_with_prefix()
        pm = SomeProvider(provider_config, False)
        self.assertEquals(
            pm.get_updated_file_name('/home/my/file.ext'),
            '/home/my/PFX_file.ext'
        )

    def _create_provider_config_with_prefix(self):
        from cloudify_cli.utils import ProviderConfig
        provider_config = ProviderConfig({
            'cloudify': {
                'resources_prefix': 'PFX_'
            }
        })
        return provider_config


class SomeProvider(BaseProviderClass):

    provision = mock.Mock()
    teardown = mock.Mock()
    validate = mock.Mock()
