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

from cloudify_cli.cli import longest_command_length


class TestCLI(unittest.TestCase):

    def test_longest_longest_command_length(self):

        sample_dict = {'a': 'v1', 'ab': 'v2'}

        self.assertEqual(longest_command_length(sample_dict), 2)
