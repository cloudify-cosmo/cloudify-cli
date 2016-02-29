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

from mock import patch

from cloudify_cli.cli import longest_command_length
from cloudify_cli.tests import cli_runner


class TestCLI(unittest.TestCase):

    @patch('argparse.ArgumentParser.print_help')
    def test_help_shows_if_no_cli_arguments(self, print_help_mock):

        # SystemExit is raised when sys.exit is called
        self.assertRaises(SystemExit, cli_runner.run_cli, 'cfy')
        self.assertTrue(print_help_mock.called)

    def test_longest_longest_command_length(self):

        sample_dict = {'a': 'v1', 'ab': 'v2'}

        self.assertEqual(longest_command_length(sample_dict), 2)
