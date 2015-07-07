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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import os
import unittest
import tempfile

import mock
import yaml

from cloudify_cli import utils, logger
from cloudify_cli.colorful_event import ColorfulEvent
from cloudify import logs


@mock.patch('cloudify_cli.utils.is_initialized', lambda: True)
class TestCLIColors(unittest.TestCase):

    def setUp(self):
        self.config_file_path = tempfile.mkstemp()[1]

        with open(self.config_file_path, 'w') as f:
            yaml.dump({'colors': True}, f)

        patcher = mock.patch('cloudify_cli.utils.get_configuration_path',
                             lambda: self.config_file_path)
        self.addCleanup(patcher.stop)
        patcher.start()

    def tearDown(self):
        os.remove(self.config_file_path)

    def test_colors_configuration(self):
        self.assertEquals(True, utils.is_use_colors())

    def test_missing_colors_configuration(self):
        # when colors configuration is missing, default should be false
        with open(self.config_file_path, 'w') as f:
            yaml.dump({}, f)
        self.assertEquals(False, utils.is_use_colors())

    @mock.patch('cloudify_cli.logger._configure_from_file', mock.MagicMock())
    def test_configure_colors_for_events_and_logs(self):
        self.assertNotEquals(ColorfulEvent, logs.EVENT_CLASS)

        with mock.patch('colorama.init') as m:
            # calling logs configuration method
            logger.configure_loggers()
            # verifying that colorama was initialized and
            # ColorfulEvent is used for events and logs output
            self.assertEquals(ColorfulEvent, logs.EVENT_CLASS)
            m.assert_called_once_with(autoreset=True)


class TestColorfulEvent(unittest.TestCase):

    def test_simple_property_color(self):
        event = {
            'timestamp': 'mock-timestamp'
        }
        timestamp_out = ColorfulEvent(event).timestamp
        self.assertIn(ColorfulEvent.TIMESTAMP_COLOR, timestamp_out)
        self.assertIn(ColorfulEvent.RESET_COLOR, timestamp_out)

    def test_property_with_nested_color(self):
        operation = 'mock-operation'
        node_id = 'mock-node-id'

        event = {
            'context': {
                'operation': operation,
                'node_id': node_id
            }
        }
        operation_info_out = ColorfulEvent(event).operation_info

        # verifying output is in the format:
        # [operation.node_id]
        # where operation and node_id each has its own color,
        # and the brackets and dot use the color for "operation info"
        self.assertEquals(
            '{op_info_clr}[{node_id_clr}{node_id}{op_info_clr}.{op_clr}{op}'
            '{op_info_clr}]{reset_clr}'.format(
                op_info_clr=ColorfulEvent.OPERATION_INFO_COLOR,
                node_id_clr=ColorfulEvent.NODE_ID_COLOR,
                op_clr=ColorfulEvent.OPERATION_COLOR,
                reset_clr=ColorfulEvent.RESET_COLOR,
                node_id=node_id,
                op=operation),
            operation_info_out)
