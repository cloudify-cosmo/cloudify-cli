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

import os
import sys

from cloudify.utils import setup_logger

from cloudify_cli import cli
from cloudify_cli.utils import DEFAULT_LOG_FILE

runner_lgr = setup_logger('cli_runner')


def run_cli_expect_system_exit_0(command):
    run_cli_expect_system_exit_code(command, expected_code=0)


def run_cli_expect_system_exit_1(command):
    run_cli_expect_system_exit_code(command, expected_code=1)


def run_cli_expect_system_exit_code(command, expected_code):
    try:
        run_cli(command)
    except SystemExit as e:
        assert e.code == expected_code
    else:
        raise RuntimeError("Expected SystemExit with {0} return code"
                           .format(expected_code))


def run_cli(command):
    runner_lgr.info(command)
    sys.argv = command.split()
    cli.main()

    # Return the content of the log file
    # this enables making assertions on the output
    if os.path.exists(DEFAULT_LOG_FILE):
        with open(DEFAULT_LOG_FILE, 'r') as f:
            return f.read()
    return ''
