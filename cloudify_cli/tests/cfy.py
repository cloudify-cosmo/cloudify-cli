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

from .. import main  # NOQA
from .. import env
from .. import logger
from .. import commands
from .. import constants


WORKDIR = os.path.join(tempfile.gettempdir(), '.cloudify-tests')
runner_lgr = setup_logger('cli_runner')


default_manager_params = dict(
    name='10.10.1.10',
    manager_ip='10.10.1.10',
    ssh_key_path='key',
    ssh_user='test',
    ssh_port='22',
    provider_context={},
    rest_port=80,
    rest_protocol='http',
    rest_certificate=None,
    manager_username='admin',
    manager_password='admin',
    manager_tenant=constants.DEFAULT_TENANT_NAME,
    cluster=[]
)


@log_capture()
def invoke(command, capture, context=None):

    logger.set_global_verbosity_level(verbose=logger.NO_VERBOSE)

    cfy = clicktest.CliRunner()

    lexed_command = shlex.split(command)
    # Safety measure in case someone wrote `cfy` at the beginning
    # of the command
    if lexed_command[0] == 'cfy':
        del lexed_command[0]

    is_version = False
    global_flags = []
    if lexed_command[0] == '--version':
        func = lexed_command[0]
        is_version = True
    elif lexed_command[0].startswith('--'):
        # for --json and --format
        while lexed_command[0].startswith('--'):
            global_flags.append(lexed_command.pop(0))

    if not is_version:
        # For commands which contain a dash (like maintenance-mode)
        func = lexed_command[0].replace('-', '_')
    params = lexed_command[1:]

    sub_func = context or func
    # If we call `cfy init`, what we actually want to do is get the
    # init module from `commands` and then get the `init` command
    # from that module, hence the attribute getting.
    if is_version:
        outcome = cfy.invoke(getattr(main, '_cfy'), ['--version'])
    else:
        outcome = cfy.invoke(getattr(
            getattr(commands, func), sub_func), global_flags + params)
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


def purge_profile(profile_name='test'):
    if not profile_name:
        return
    profile_path = os.path.join(env.CLOUDIFY_WORKDIR, profile_name)
    if os.path.isdir(profile_path):
        shutil.rmtree(profile_path)


def use_manager(**manager_params):
    provider_context = manager_params['provider_context'] or {}
    profile = env.ProfileContext()
    profile.manager_ip = manager_params['manager_ip']
    profile.ssh_key = manager_params['ssh_key_path']
    profile.ssh_user = manager_params['ssh_user']
    profile.ssh_port = manager_params['ssh_port']
    profile.rest_port = manager_params['rest_port']
    profile.rest_protocol = manager_params['rest_protocol']
    profile.manager_username = manager_params['manager_username']
    profile.manager_password = manager_params['manager_password']
    profile.manager_tenant = manager_params['manager_tenant']
    profile.cluster = manager_params['cluster']
    profile.provider_context = provider_context

    purge_profile(manager_params['manager_ip'])
    profile.save()
    env.profile = profile

    commands.init.set_config()
    env.set_active_profile(manager_params['manager_ip'])
    register_commands()

    return profile


def register_commands():
    from cloudify_cli.main import _register_commands
    _register_commands()
