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

import fabric.api as fab

from .logger import get_global_verbosity
from .exceptions import CloudifyCliError
from .env import profile, build_manager_host_string


def get_manager_date():
    # output here should be hidden anyway.
    with fab.settings(fab.hide('running', 'stdout')):
        return run_command_on_manager('date +%Y%m%dT%H%M%S').stdout


def get_file_from_manager(remote_source_path, destination_path):
    key_filename = os.path.expanduser(profile.ssh_key)
    with fab.settings(
            fab.hide('running', 'stdout'),
            host_string=build_manager_host_string(),
            key_filename=key_filename,
            port=profile.ssh_port):
        fab.get(remote_source_path, destination_path)


def put_file_in_manager(source_path,
                        remote_source_path,
                        use_sudo=True,
                        key_filename=None,
                        user=None,
                        port=''):
    port = port or profile.ssh_port
    if not key_filename:
        key_filename = os.path.expanduser(profile.ssh_key)
    with fab.settings(
            fab.hide('running', 'stdout'),
            host_string=build_manager_host_string(ssh_user=user),
            key_filename=key_filename,
            port=port):
        fab.put(use_sudo=use_sudo,
                local_path=source_path,
                remote_path=remote_source_path)


def run_command_on_manager(command,
                           use_sudo=False,
                           open_shell=False,
                           host_string='',
                           force_output=False):
    """Runs an SSH command on a Manager.

    `open_shell` opens an interactive shell to the server.
    `host_string` can be explicitly provided to save on REST calls.
    `force_output` forces all output as if running in verbose.
    """
    test_profile()

    host_string = host_string or build_manager_host_string()
    port = int(profile.ssh_port)

    def execute():
        key_filename = os.path.expanduser(profile.ssh_key)
        with fab.settings(
                host_string=host_string,
                key_filename=key_filename,
                port=port,
                warn_only=True):
            if use_sudo:
                output = fab.sudo(command)
            elif open_shell:
                fab.open_shell(command)
                return None
            else:
                output = fab.run(command)
            if output.failed:
                raise CloudifyCliError(
                    'Failed to execute: {0} ({1})'.format(
                        output.real_command, output.stderr))
            return output

    if get_global_verbosity() or force_output:
        return execute()
    else:
        with fab.hide('running', 'stdout', 'stderr', 'warnings'):
            return execute()


def test_profile():
    msg = 'Manager `ssh_{0}` is not set in Cloudify CLI settings'
    missing_config = False
    missing_part = ''

    if not profile.ssh_user:
        missing_config = True
        missing_part = 'user'
    elif not profile.ssh_key:
        missing_config = True
        missing_part = 'key'
    elif not profile.ssh_port:
        missing_config = True
        missing_part = 'port'

    if missing_config:
        raise CloudifyCliError(msg.format(missing_part))
