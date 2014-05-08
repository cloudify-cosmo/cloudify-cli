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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

__author__ = 'dan'

import unittest

from cosmo_cli.cosmo_cli import (
    _create_event_message_prefix
)


class CliUnitTests(unittest.TestCase):

    def test_create_event_message_prefix_with_unicode(self):

        unicode_message = u'\u2018'

        event = {
            'context': {'deployment_id': 'deployment'},
            'message': {'text': unicode_message},
            'type': 'cloudify_log',
            'level': 'INFO',
            '@timestamp': 'NOW'
        }

        _create_event_message_prefix(event)
