########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
########

import os
import unittest
import tempfile

import mock
import yaml

from .. import env


@mock.patch('cloudify_cli.env.is_initialized', lambda: True)
class TestCLIConfig(unittest.TestCase):

    def setUp(self):
        self.config_file_path = tempfile.mkstemp()[1]

        with open(self.config_file_path, 'w') as f:
            yaml.dump({'colors': True, 'auto_generate_ids': True}, f)

        patcher = mock.patch('cloudify_cli.env.CLOUDIFY_CONFIG_PATH',
                             self.config_file_path)
        self.addCleanup(patcher.stop)
        patcher.start()

    def tearDown(self):
        os.remove(self.config_file_path)

    def test_colors_configuration(self):
        self.assertTrue(env.is_use_colors())

    def test_missing_colors_configuration(self):
        # when colors configuration is missing, default should be false
        with open(self.config_file_path, 'w') as f:
            yaml.dump({}, f)
        self.assertFalse(env.is_use_colors())

    def test_auto_generate_ids_configuration(self):
        self.assertTrue(env.is_auto_generate_ids())

    def test_missing_auto_generate_ids_configuration(self):
        # when auto_generate_ids configuration is missing,
        # default should be false
        with open(self.config_file_path, 'w') as f:
            yaml.dump({}, f)
        self.assertFalse(env.is_auto_generate_ids())
