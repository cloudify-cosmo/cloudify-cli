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

import logging
import unittest

from mock import patch

from cloudify import logs

from cloudify_cli import cli
from cloudify_cli import logger
from cloudify_cli.cli import longest_command_length
from cloudify_cli.tests import cli_runner


class TestCLI(unittest.TestCase):

    def tearDown(self):
        self._reset_verbosity_and_loggers()

    @patch('argparse.ArgumentParser.print_help')
    def test_help_shows_if_no_cli_arguments(self, print_help_mock):

        # SystemExit is raised when sys.exit is called
        self.assertRaises(SystemExit, cli_runner.run_cli, 'cfy')
        self.assertTrue(print_help_mock.called)

    def test_longest_longest_command_length(self):

        sample_dict = {'a': 'v1', 'ab': 'v2'}

        self.assertEqual(longest_command_length(sample_dict), 2)

    def test_verbosity(self):
        def test(flag, expected):
            self._reset_verbosity_and_loggers()
            with patch('cloudify_cli.commands.status'):
                cli_runner.run_cli('cfy status {0}'.format(flag))
            self.assertEqual(cli.verbosity_level, expected)
            self.assertEqual(logs.EVENT_VERBOSITY_LEVEL, expected)
            if expected >= cli.HIGH_VERBOSE:
                expected_logging_level = logging.DEBUG
            else:
                expected_logging_level = logging.INFO
            self.assertTrue(logger.all_loggers())
            for logger_name in logger.all_loggers():
                log = logging.getLogger(logger_name)
                self.assertEqual(log.level, expected_logging_level)

        test('', cli.NO_VERBOSE)
        test('-v', cli.LOW_VERBOSE)
        test('-vv', cli.MEDIUM_VERBOSE)
        test('-vvv', cli.HIGH_VERBOSE)
        test('--debug', cli.HIGH_VERBOSE)
        test('--debug -v', cli.HIGH_VERBOSE)

    def _reset_verbosity_and_loggers(self):
        cli.verbosity_level = cli.NO_VERBOSE
        logs.EVENT_VERBOSITY_LEVEL = cli.NO_VERBOSE
        logger.configure_loggers()
