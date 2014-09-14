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

from cloudify_cli import cli


def run_cli_expect_system_exit_0(command):
    try:
        run_cli(command)
    except SystemExit as e:
        assert e.code == 0
    else:
        raise RuntimeError("Expected SystemExit with 0 return code")


def run_cli_expect_system_exit_1(command):
    try:
        run_cli(command)
    except SystemExit as e:
        assert e.code == 1
    else:
        raise RuntimeError("Expected SystemExit with 1 return code")


def run_cli(command):
    sys.argv = command.split()
    cli.main()

    # Return the content of the log file
    # this enables making assertions on the output
    from cloudify_cli.config.logger_config import LOGGER
    log_file_path = LOGGER['handlers']['file']['filename']
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r') as f:
            return f.read()
    return ''
