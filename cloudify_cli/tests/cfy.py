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


default_manager_params = dict(
    manager_ip='10.10.1.10',
    alias=None,
    ssh_key_path='key',
    ssh_user='key',
    ssh_port='22',
    provider_context={},
    rest_port=80,
    rest_protocol='http')


@log_capture()
def invoke(command, capture, context=None):
    # For each invocation we should use a temporary directory
    # for the cfy workdir.
    env.CLOUDIFY_WORKDIR = '/tmp/.cloudify-test'
    env.CLOUDIFY_CONFIG_PATH = os.path.join(
        env.CLOUDIFY_WORKDIR, 'config.yaml')
    env.PROFILES_DIR = os.path.join(
        env.CLOUDIFY_WORKDIR, 'profiles')
    env.ACTIVE_PRO_FILE = os.path.join(
        env.CLOUDIFY_WORKDIR, 'active.profile')

    logger.configure_loggers()
    logger.set_global_verbosity_level(verbose=logger.NO_VERBOSE)

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


# TODO: Use a tempdir under /tmp/ for .cloudify-something
def purge_dot_cloudify():
    dot_cloudify_dir = env.CLOUDIFY_WORKDIR
    if os.path.isdir(dot_cloudify_dir):
        shutil.rmtree(dot_cloudify_dir)


def purge_profile(profile_name='test'):
    if not profile_name:
        return
    profile_path = os.path.join(env.CLOUDIFY_WORKDIR, profile_name)
    if os.path.isdir(profile_path):
        shutil.rmtree(profile_path)


def use_manager(**manager_params):
    provider_context = manager_params['provider_context'] or {}
    settings = env.ProfileContext()
    settings.set_manager_ip(manager_params['manager_ip'])
    settings.set_manager_key(manager_params['ssh_key_path'])
    settings.set_manager_user(manager_params['ssh_user'])
    settings.set_manager_port(manager_params['ssh_port'])
    settings.set_rest_port(manager_params['rest_port'])
    settings.set_rest_protocol(manager_params['rest_protocol'])
    settings.set_provider_context(provider_context)

    purge_profile(manager_params['manager_ip'])
    env.set_profile_context(
        profile_name=manager_params['manager_ip'],
        context=settings,
        update=False)
    env.set_cfy_config()
    env.set_active_profile(manager_params['manager_ip'])
    register_commands()


def register_commands():
    from cloudify_cli.cli import _register_commands
    _register_commands()
