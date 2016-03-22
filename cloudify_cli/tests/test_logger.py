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

import unittest
import json

from mock import patch

from cloudify_cli import logger
from cloudify_cli.tests.commands import utils


class TestLogger(unittest.TestCase):

    def test_text_events_logger(self):
        events_logger = logger.get_events_logger(json_output=False)
        events = [{'key': 'output'}, {'key': 'hide'}]

        def mock_create_message(event):
            return None if event['key'] == 'hide' else event['key']

        with utils.mock_logger('cloudify_cli.logger._lgr') as output:
            with patch('cloudify.logs.create_event_message_prefix',
                       mock_create_message):
                events_logger(events)
        self.assertEqual(events[0]['key'], output.getvalue())

    def test_json_events_logger(self):
        events_logger = logger.get_events_logger(json_output=True)
        events = [{'key': 'value1'}, {'key': 'value2'}]
        with utils.mock_stdout() as output:
            events_logger(events)
        self.assertEqual('{0}\n{1}\n'.format(json.dumps(events[0]),
                                             json.dumps(events[1])),
                         output.getvalue())
