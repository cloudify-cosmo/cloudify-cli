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
import shlex
import shutil
import tempfile

import click.testing as clicktest
from testfixtures import log_capture

from cloudify.utils import setup_logger

from .. import cli  # NOQA
from .. import env
from .. import logger
from .. import commands


WORKDIR = os.path.join(tempfile.gettempdir(), '.cloudify-tests')
runner_lgr = setup_logger('cli_runner')


@log_capture()
def invoke(command, capture, context=None):
    # For each invocation we should use a temporary directory
    # for the cfy workdir.
    env.CLOUDIFY_WORKDIR = '/tmp/.cloudify'
    env.CLOUDIFY_CONFIG_PATH = os.path.join(
        env.CLOUDIFY_WORKDIR, 'config.yaml')
    env.PROFILES_DIR = os.path.join(
        env.CLOUDIFY_WORKDIR, 'profiles')
    env.ACTIVE_PRO_FILE = os.path.join(
        env.CLOUDIFY_WORKDIR, 'active.profile')

    logger.configure_loggers()
    logger.set_global_verbosity_level(verbose=True)

    cfy = clicktest.CliRunner()

    lexed_command = shlex.split(command)
    # Safety measure in case someone wrote `cfy` at the beginning
    # of the command
    if lexed_command[0] == 'cfy':
        del lexed_command[0]
    # For commands which contain a dash (like maintenance-mode)
    func = lexed_command[0].replace('-', '_')
    params = lexed_command[1:]

    sub_func = context or func

    # If we call `cfy init`, what we actually want to do is get the
    # init module from `commands` and then get the `init` command
    # from that module, hence the attribute getting.
    outcome = cfy.invoke(getattr(getattr(commands, func), sub_func), params)
    outcome.command = command

    logs = [capture.records[m].msg for m in range(len(capture.records))]
    outcome.logs = '\n'.join(logs)

    return outcome


class ClickInvocationException(Exception):
    def __init__(self,
                 message,
                 output=None,
                 logs=None,
                 exit_code=1,
                 exception=None,
                 exc_info=None):
        self.message = message
        self.output = output
        self.logs = logs
        self.exit_code = exit_code
        self.exception = exception
        self.exc_info = exc_info

    def __str__(self):
        string = '\nMESSAGE: {0}\n'.format(self.message)
        string += 'STDOUT: {0}\n'.format(self.output)
        string += 'EXIT_CODE: {0}\n'.format(self.exit_code)
        string += 'LOGS: {0}\n'.format(self.logs)
        string += 'EXCEPTION: {0}\n'.format(self.exception)
        string += 'EXC_INFO: {0}\n'.format(self.exc_info)
        return string


def purge_dot_cloudify():
    dot_cloudify_dir = env.CLOUDIFY_WORKDIR
    if os.path.isdir(dot_cloudify_dir):
        shutil.rmtree(dot_cloudify_dir)
